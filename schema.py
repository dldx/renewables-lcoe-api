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
    capital_expenditure_per_kw: Annotated[
        float, Field(ge=1e2, le=1e4, title="Capital expenditure ($/kW)")
    ] = 670
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
    degradation_rate: Annotated[
        float,
        Field(
            ge=0,
            le=0.05,
            title="Degradation Rate (%)",
            description="Annual degradation rate as a decimal, e.g., 0.01 for 1%",
        ),
    ] = 0.005
    dcsr: Annotated[
        float,
        Field(
            ge=1,
            le=10,
            title="Debt Service Coverage Ratio",
            description="Debt service coverage ratio",
        ),
    ] = 1.3
    targetting_dcsr: Annotated[
        bool,
        Field(
            title="Target DSCR?",
            description="Whether to target the DSCR or the debt percentage. If True, the DCSR will be used to calculate the debt percentage.",
        )
    ] = True

    @model_validator(mode="after")
    def check_sum_of_parts(self):
        if not self.targetting_dcsr:
            assert self.debt_pct_of_capital_cost is not None, "Debt percentage must be provided"
            if self.debt_pct_of_capital_cost + self.equity_pct_of_capital_cost != 1:
                raise ValueError("Debt and equity percentages must sum to 1")
        return self

    @computed_field
    @property
    def capital_cost(self) -> Annotated[float,
                                        Field(title="Capital Cost ($)", description="Total capital cost")]:
        return self.capacity_mw * self.capital_expenditure_per_kw * 1000

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
        if self.debt_pct_of_capital_cost is not None and self.equity_pct_of_capital_cost is not None:
            return self.debt_pct_of_capital_cost * self.cost_of_debt + self.equity_pct_of_capital_cost * self.cost_of_equity

    @computed_field
    @property
    def equity_pct_of_capital_cost(self) -> Annotated[Optional[float],
                                                     Field(title="Equity Percentage (%)",
                                                           description="Equity as a percentage of capital expenditure")]:
        if self.debt_pct_of_capital_cost is not None:
            return 1 - self.debt_pct_of_capital_cost

    @model_validator(mode="before")
    @classmethod
    def empty_str_to_none(cls, values):
        if isinstance(values, dict):
            return {k: (None if v == '' or v == "None" else v) for k, v in values.items()}
        return values

