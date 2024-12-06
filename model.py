from typing import Annotated, Iterable, Literal, Optional, Tuple
import numpy as np
import polars as pl
from pyxirr import irr, npv
from functools import partial
import pyxirr
from scipy.optimize import fsolve

from schema import SolarPVAssumptions


def calculate_cashflow_for_renewable_project(
    assumptions: SolarPVAssumptions, tariff: float | Iterable, return_model=False, errors: Literal["raise", "ignore"] = "raise"
) -> (
    Annotated[float | None, "Post-tax equity IRR - Cost of equity"]
    | Tuple[
        Annotated[pl.DataFrame, "Cashflow model"],
        Annotated[float | None, "Post-tax equity IRR"],
        Annotated[float, "Breakeven tariff"],
        Annotated[SolarPVAssumptions, "Assumptions"],
    ]
):
    """Calculate the cashflow for a renewable energy project

    Args:
        assumptions (SolarPVAssumptions): The assumptions for the project
        tariff (float): The tariff for the project
        return_model (bool, optional): Whether to return the model. Defaults to False.

    Returns:
        float: post-tax equity IRR - cost of equity (if return_model is False)
        pl.DataFrame: Cashflow model (if return_model is True)
        float: Post-tax equity IRR (if return_model is True)
        float: Breakeven tariff (if return_model is True)
        SolarPVAssumptions: Assumptions (if return_model is True)
    """

    # Tariff must be a number
    assert tariff is not None, "Tariff must be provided"

    assumptions = assumptions.model_copy(deep=True)
    # Create a dataframe, starting with the period
    model = pl.DataFrame(
        {
            "Period": [i for i in range(assumptions.project_lifetime_years + 1)],
        }
    )

    model = (
        model.with_columns(
            Capacity_MW=pl.when(pl.col("Period") > 0)
            .then(assumptions.capacity_mw)
            .otherwise(0),
            Capacity_Factor=pl.when(pl.col("Period") > 0)
            .then(assumptions.capacity_factor)
            .otherwise(0),
            Tariff_per_MWh=pl.when(pl.col("Period") > 0).then(tariff).otherwise(0),
        )
        # Take into account degradation
        .with_columns(
            Capacity_Factor=pl.when(pl.col("Period") > 0)
            .then(
                pl.col("Capacity_Factor")
                * (1 - assumptions.degradation_rate) ** (pl.col("Period") - 1)
            )
            .otherwise(0),
        )
        .with_columns(
            Total_Generation_MWh=pl.col("Capacity_MW")
            * pl.col("Capacity_Factor")
            * 8760,
        )
        .with_columns(
            Total_Revenues_mn=pl.col("Total_Generation_MWh")
            * pl.col("Tariff_per_MWh")
            / 1000,
            O_M_Costs_mn=pl.when(pl.col("Period") > 0)
            .then(
                assumptions.capital_cost
                / 1000
                * assumptions.o_m_cost_pct_of_capital_cost
            )
            .otherwise(0),
        )
        .with_columns(
            Total_Operating_Costs_mn=pl.col("O_M_Costs_mn"),
        )
        .with_columns(
            EBITDA_mn=pl.col("Total_Revenues_mn") - pl.col("Total_Operating_Costs_mn"),
        )
        .with_columns(
            CFADS_mn=pl.col("EBITDA_mn"),
        ))
    # Calculate DSCR-sculpted debt % of capital cost if debt % is not provided
    if (assumptions.debt_pct_of_capital_cost is None) or assumptions.targetting_dscr:
        model = (
            model.with_columns(
                Target_Debt_Service_mn=pl.when((pl.col("Period") == 0) | (pl.col("Period") > assumptions.loan_tenor_years))
                .then(0)
                .otherwise(pl.col("CFADS_mn") / assumptions.dscr),
            )
        )
        # Calculate debt % of capital cost by calculating NPV of debt service, and then dividing by capital cost
        assumptions.debt_pct_of_capital_cost = min(1, pyxirr.npv(
            assumptions.cost_of_debt,
            model.select("Target_Debt_Service_mn").__array__()[0:assumptions.loan_tenor_years+1, 0],
        ) / (assumptions.capital_cost / 1000))
        assert (
            assumptions.debt_pct_of_capital_cost
            + assumptions.equity_pct_of_capital_cost
            == 1
        ), f"Debt and equity percentages do not add up to 100%. Debt: {assumptions.debt_pct_of_capital_cost:.0%}, Equity: {assumptions.equity_pct_of_capital_cost:.0%}"
        assert (
            assumptions.debt_pct_of_capital_cost >= 0
            and assumptions.debt_pct_of_capital_cost <= 1
        ), f"Debt percentage is not between 0 and 100%: {assumptions.debt_pct_of_capital_cost:.0%}"
        assert (
            assumptions.equity_pct_of_capital_cost >= 0
            and assumptions.equity_pct_of_capital_cost <= 1
        ), f"Equity percentage is not between 0 and 100%: {assumptions.equity_pct_of_capital_cost:.0%}"

    model = (
        model.with_columns(
            Debt_Outstanding_EoP_mn=pl.when(pl.col("Period") == 0)
            .then(
                assumptions.debt_pct_of_capital_cost * assumptions.capital_cost / 1000
            )
            .otherwise(0),
        )
        .with_columns(
            Interest_Expense_mn=pl.when(pl.col("Period") == 0)
            .then(0)
            .otherwise(
                pl.col("Debt_Outstanding_EoP_mn").shift(1) * assumptions.cost_of_debt
            ),
        ))
    # Calculate amortization, assuming a target DSCR
    if assumptions.targetting_dscr:
        model = (
            model.with_columns(
                Amortization_mn=pl.when(pl.col("Period") == 0)
                .then(0)
                .otherwise(
                    pl.min_horizontal(
                        pl.col("Target_Debt_Service_mn") - pl.col("Interest_Expense_mn"),
                        pl.col("Debt_Outstanding_EoP_mn").shift(1),
                    )
                ),
            ))
    else:
        # Calculate amortization, assuming equal amortization over the project lifetime
        model = (
            model.with_columns(
                Amortization_mn=pl.when((pl.col("Period") == 0) | (pl.col("Period") > assumptions.loan_tenor_years))
                .then(0)
                .otherwise(
                    assumptions.debt_pct_of_capital_cost
                    * assumptions.capital_cost
                    / 1000
                    / assumptions.loan_tenor_years
                ),
            ))
    model = (
        model.with_columns(
            Debt_Outstanding_EoP_mn=pl.when(pl.col("Period") == 0)
            .then(pl.col("Debt_Outstanding_EoP_mn"))
            .otherwise(
                pl.col("Debt_Outstanding_EoP_mn").shift(1) - pl.col("Amortization_mn")
            )
        )
        .with_columns(
            Debt_Outstanding_BoP_mn=pl.col("Debt_Outstanding_EoP_mn").shift(1),
        )
    )
    model = model.to_pandas()

    for period in model["Period"]:
        if period > 1 and period <= assumptions.loan_tenor_years:
            model.loc[period, "Interest_Expense_mn"] = (
                model.loc[period, "Debt_Outstanding_BoP_mn"] * assumptions.cost_of_debt
            )
            if assumptions.targetting_dscr:
                model.loc[period, "Amortization_mn"] = min(
                    model.loc[period, "Target_Debt_Service_mn"]
                    - model.loc[period, "Interest_Expense_mn"],
                    model.loc[period, "Debt_Outstanding_BoP_mn"],
                )
            model.loc[period, "Debt_Outstanding_EoP_mn"] = (
                model.loc[period, "Debt_Outstanding_BoP_mn"]
                - model.loc[period, "Amortization_mn"]
            )
            if period < assumptions.loan_tenor_years:
                model.loc[period + 1, "Debt_Outstanding_BoP_mn"] = model.loc[
                    period, "Debt_Outstanding_EoP_mn"
                ]
    model = pl.DataFrame(model)
    if not assumptions.targetting_dscr:
        # Target debt service = Amortization + Interest
        model = (
            model.with_columns(
                Target_Debt_Service_mn=pl.when(pl.col("Period") == 0)
                .then(0)
                .otherwise(
                    pl.col("Amortization_mn") + pl.col("Interest_Expense_mn")
                ),
            )
        )
        # Calculate DSCR
        assumptions.dscr = (
            model["EBITDA_mn"] / model["Target_Debt_Service_mn"]
        ).min()

    model = (
        model.with_columns(
            # Straight line depreciation
            Depreciation_mn=pl.when(pl.col("Period") > 0)
            .then(assumptions.capital_cost / 1000 / assumptions.project_lifetime_years)
            .otherwise(0),
        )
        .with_columns(
            Taxable_Income_mn=pl.col("EBITDA_mn")
            - pl.col("Depreciation_mn")
            - pl.col("Interest_Expense_mn"),
        )
        .with_columns(
            Tax_Liability_mn=pl.max_horizontal(
                0, assumptions.tax_rate * pl.col("Taxable_Income_mn")
            )
        )
        .with_columns(
            Post_Tax_Net_Equity_Cashflow_mn=pl.when(pl.col("Period") == 0)
            .then(
                -assumptions.capital_cost
                / 1000
                * assumptions.equity_pct_of_capital_cost
            )
            .otherwise(
                pl.col("EBITDA_mn")
                - pl.col("Target_Debt_Service_mn")
                - pl.col("Tax_Liability_mn")
            )
        )
    )

    # Rearrange columns so that they are always in the same order
    model = model[
        [
            "Period",
            "Capacity_MW",
            "Capacity_Factor",
            "Tariff_per_MWh",
            "Total_Generation_MWh",
            "Total_Revenues_mn",
            "O_M_Costs_mn",
            "Total_Operating_Costs_mn",
            "EBITDA_mn",
            "CFADS_mn",
            "Debt_Outstanding_EoP_mn",
            "Interest_Expense_mn",
            "Amortization_mn",
            "Debt_Outstanding_BoP_mn",
            "Target_Debt_Service_mn",
            "Depreciation_mn",
            "Taxable_Income_mn",
            "Tax_Liability_mn",
            "Post_Tax_Net_Equity_Cashflow_mn",
        ]
    ]

    ## Do some sanity checks
    # Check that the debt outstanding at the end of the loan period is zero
    assert (
        (model["Debt_Outstanding_EoP_mn"].slice(assumptions.loan_tenor_years,) < 0.0001).all() # type: ignore
    ), f"Debt outstanding at the end of the loan period is not zero: {model['Debt_Outstanding_EoP_mn'].slice(assumptions.loan_tenor_years,)}" # type: ignore


    # Calculate Post-Tax Equity IRR
    try:
        post_tax_equity_irr = irr(model["Post_Tax_Net_Equity_Cashflow_mn"].to_numpy())
    except pyxirr.InvalidPaymentsError as e:
        if errors == "ignore":
            post_tax_equity_irr = None
        else:
            if assumptions.debt_pct_of_capital_cost == 1:
                raise AssertionError(
                    "The project is fully financed by debt so equity IRR is infinite."
                )
            else:
                raise AssertionError(
                    f"The power tariff is too low so the project never breaks even. Please increase it from {tariff}."
                )

    if return_model:
        return model, post_tax_equity_irr, tariff, assumptions
    assert post_tax_equity_irr is not None, "Post-tax equity IRR could not be calculated"
    return post_tax_equity_irr - assumptions.cost_of_equity  # type: ignore


def calculate_lcoe(
    assumptions: SolarPVAssumptions, LCOE_guess: float = 20, iter_count: int = 0
) -> Annotated[float, "LCOE"]:
    """The LCOE is the breakeven tariff that makes the project NPV zero"""
    # Define the objective function
    objective_function = partial(calculate_cashflow_for_renewable_project, assumptions)
    if iter_count > 5000:
        raise ValueError(
            f"LCOE could not be calculated due to iteration limit (tariff guess: {LCOE_guess})"
        )

    try:
        lcoe = fsolve(objective_function, LCOE_guess)[0] + 0.0001
    except ValueError as e:
        # Set LCOE lower so that fsolve can find a solution
        LCOE_guess = 1
        lcoe = calculate_lcoe(assumptions, LCOE_guess, iter_count=iter_count + 1)
    except AssertionError as e:
        # LCOE is too low
        LCOE_guess += 5
        lcoe = calculate_lcoe(assumptions, LCOE_guess, iter_count=iter_count + 1)
    return float(lcoe)
