from typing import Annotated, Optional
from pydantic import BaseModel, Field, computed_field, field_validator, model_validator


class SolarPVAssumptions(BaseModel):
    capacity_mw: Annotated[float, Field(ge=1, le=1000, title="Capacity (MW)")] = 30
    capacity_factor: Annotated[
        float,
        Field(
            ge=0,
            le=0.6,
            title="Capacity factor (%)",
            description="Capacity factor as a decimal, e.g., 0.2 for 20%",
        ),
    ] = 0.10
    capital_expenditure_per_mw: Annotated[
        float, Field(ge=1e5, le=1e7, title="Capital expenditure per MW ($/MW)")
    ] = 670_000
    o_m_cost_pct_of_capital_cost: Annotated[
        float,
        Field(
            ge=0,
            le=0.5,
            title="O&M Cost Percentage (%)",
            description="O&M cost as a percentage of capital expenditure",
        ),
    ] = 0.02
    debt_pct_of_capital_cost: Annotated[
        Optional[float],
        Field(
            ge=0,
            le=1,
            title="Debt Percentage (%)",
            description="Debt as a percentage of capital expenditure",
        ),
    ] = None
    cost_of_debt: Annotated[
        float,
        Field(
            ge=0,
            le=0.5,
            title="Cost of Debt (%)",
            description="Cost of debt (as a decimal, e.g., 0.05 for 5%)",
        ),
    ] = 0.05
    cost_of_equity: Annotated[
        float,
        Field(
            ge=0,
            le=0.5,
            title="Cost of Equity (%)",
            description="Cost of equity (as a decimal, e.g., 0.1 for 10%)",
        ),
    ] = 0.10
    tax_rate: Annotated[
        float,
        Field(
            ge=0,
            le=0.5,
            title="Tax Rate (%)",
            description="Tax rate (as a decimal, e.g., 0.3 for 30%)",
        ),
    ] = 0.30
    project_lifetime_years: Annotated[
        int,
        Field(
            ge=5,
            le=50,
            title="Project Lifetime (years)",
            description="Project lifetime in years",
        ),
    ] = 25
    dcsr: Annotated[
        float,
        Field(
            ge=1,
            le=2,
            title="Debt Service Coverage Ratio",
            description="Debt service coverage ratio",
        ),
    ]

    @model_validator(mode="after")
    def check_sum_of_parts(self):
        if self.debt_pct_of_capital_cost is not None and self.equity_pct_of_capital_cost is not None:
            if self.debt_pct_of_capital_cost + self.equity_pct_of_capital_cost != 1:
                raise ValueError("Debt and equity percentages must sum to 1")
        return self

    @computed_field
    @property
    def capital_cost(self) -> Annotated[float,
                                        Field(title="Capital Cost ($)", description="Total capital cost")]:
        return self.capacity_mw * self.capital_expenditure_per_mw

    @computed_field
    @property
    def tax_adjusted_WACC(self) -> Annotated[Optional[float],
                                             Field(title="Tax Adjusted WACC (%)",
                                                   description="Tax adjusted weighted average cost of capital")]:
        if (self.debt_pct_of_capital_cost is not None) and (self.equity_pct_of_capital_cost is not None):
            return (self.debt_pct_of_capital_cost * self.cost_of_debt * (1 - self.tax_rate) +
                    self.equity_pct_of_capital_cost * self.cost_of_equity)

    @computed_field
    @property
    def wacc(self) -> Annotated[Optional[float], Field(title="WACC (%)", description="Weighted average cost of capital")]:
        if self.debt_pct_of_capital_cost is not None:
            return self.debt_pct_of_capital_cost * self.cost_of_debt + self.equity_pct_of_capital_cost * self.cost_of_equity

    @computed_field
    @property
    def equity_pct_of_capital_cost(self) -> Annotated[Optional[float],
                                                     Field(title="Equity Percentage (%)",
                                                           description="Equity as a percentage of capital expenditure")]:
        if self.debt_pct_of_capital_cost is not None:
            return 1 - self.debt_pct_of_capital_cost

    # @model_validator(mode='after')
    # def check_dcsr_or_debt_pct(self):
    #     """
    #     Check that either dcsr or debt_pct_of_capital_cost is provided, and not both.
    #     """
    #     if (self.dcsr and self.debt_pct_of_capital_cost) or (not self.dcsr and not self.debt_pct_of_capital_cost):
    #         raise ValueError("""Either dcsr or debt_pct_of_capital_cost must be provided, not both.
    #                          If target dcsr is provided, debt_pct_of_capital_cost will be calculated as
    #                             `debt_pct_of_capital_cost = npv(cost_of_debt, debt_service) / capital_cost`
    #                          """)
    #     return self
