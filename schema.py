from typing import Annotated
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
        float, Field(ge=1e5, le=1e6, title="Capital expenditure per MW ($/MW)")
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
        float,
        Field(
            ge=0,
            le=1,
            title="Debt Percentage (%)",
            description="Debt as a percentage of capital expenditure",
        ),
    ] = 0.8
    equity_pct_of_capital_cost: Annotated[
        float,
        Field(
            ge=0,
            le=1,
            title="Equity Percentage (%)",
            description="Equity as a percentage of capital expenditure",
        ),
    ] = 0.2
    cost_of_debt: Annotated[
        float,
        Field(
            ge=0,
            le=0.2,
            title="Cost of Debt (%)",
            description="Cost of debt (as a decimal, e.g., 0.05 for 5%)",
        ),
    ] = 0.05
    cost_of_equity: Annotated[
        float,
        Field(
            ge=0,
            le=0.3,
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
    ] = 1.3

    @model_validator(mode="after")
    def check_sum_of_parts(self):
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
    def tax_adjusted_WACC(self) -> Annotated[float,
                                             Field(title="Tax Adjusted WACC (%)",
                                                   description="Tax adjusted weighted average cost of capital")]:
        return (self.debt_pct_of_capital_cost * self.cost_of_debt * (1 - self.tax_rate) +
                self.equity_pct_of_capital_cost * self.cost_of_equity)

    @computed_field
    @property
    def wacc(self) -> Annotated[float, Field(title="WACC (%)", description="Weighted average cost of capital")]:
        return self.debt_pct_of_capital_cost * self.cost_of_debt + self.equity_pct_of_capital_cost * self.cost_of_equity
