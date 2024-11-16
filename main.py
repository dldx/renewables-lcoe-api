from typing import Annotated, Dict
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from schema import SolarPVAssumptions
from model import calculate_cashflow_for_renewable_project, calculate_lcoe

app = FastAPI()

import gradio as gr

CUSTOM_PATH = "/"

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def process_inputs(
    capacity_mw,
    capacity_factor,
    capital_expenditure_per_mw,
    o_m_cost_pct_of_capital_cost,
    debt_pct_of_capital_cost,
    equity_pct_of_capital_cost,
    cost_of_debt,
    cost_of_equity,
    tax_rate,
    project_lifetime_years,
    dcsr
) -> Dict:
    try:
        # Convert inputs to SolarPVAssumptions model using named parameters
        assumptions = SolarPVAssumptions(
            capacity_mw=capacity_mw,
            capacity_factor=capacity_factor,
            capital_expenditure_per_mw=capital_expenditure_per_mw,
            o_m_cost_pct_of_capital_cost=o_m_cost_pct_of_capital_cost,
            debt_pct_of_capital_cost=debt_pct_of_capital_cost,
            equity_pct_of_capital_cost=equity_pct_of_capital_cost,
            cost_of_debt=cost_of_debt,
            cost_of_equity=cost_of_equity,
            tax_rate=tax_rate,
            project_lifetime_years=project_lifetime_years,
            dcsr=dcsr
        )

        # Calculate the LCOE for the project
        lcoe = calculate_lcoe(assumptions)
        cashflow_model, post_tax_equity_irr, breakeven_tariff = calculate_cashflow_for_renewable_project(assumptions, lcoe, return_model=True)
        return { "lcoe": lcoe,
                "post_tax_equity_irr": post_tax_equity_irr,
                "breakeven_tariff": breakeven_tariff,
                 "cashflow_model": cashflow_model}


    except Exception as e:
        return str(e)

with gr.Blocks() as interface:
    with gr.Row():
        with gr.Column():
            # Input components
            capacity_mw = gr.Number(value=30, label="Capacity (MW)", minimum=1, maximum=1000)
            capacity_factor = gr.Number(value=0.10, label="Capacity factor (%)", minimum=0, maximum=0.6)
            capital_expenditure_per_mw = gr.Number(value=670000, label="Capital expenditure per MW ($/MW)", minimum=1e5, maximum=1e6)
            o_m_cost_pct_of_capital_cost = gr.Number(value=0.02, label="O&M Cost Percentage (%)", minimum=0, maximum=0.5)
            debt_pct_of_capital_cost = gr.Number(value=0.8, label="Debt Percentage (%)", minimum=0, maximum=1)
            equity_pct_of_capital_cost = gr.Number(value=0.2, label="Equity Percentage (%)", minimum=0, maximum=1)
            cost_of_debt = gr.Number(value=0.05, label="Cost of Debt (%)", minimum=0, maximum=0.2)
            cost_of_equity = gr.Number(value=0.10, label="Cost of Equity (%)", minimum=0, maximum=0.3)
            tax_rate = gr.Number(value=0.30, label="Tax Rate (%)", minimum=0, maximum=0.5)
            project_lifetime_years = gr.Number(value=25, label="Project Lifetime (years)", minimum=5, maximum=50)
            dcsr = gr.Number(value=1.3, label="Debt Service Coverage Ratio", minimum=1, maximum=2)

        with gr.Column():
            # Output components
            output = gr.JSON()

    submit_btn = gr.Button("Calculate")

    submit_btn.click(
        fn=process_inputs,
        inputs=[
            capacity_mw, capacity_factor, capital_expenditure_per_mw,
            o_m_cost_pct_of_capital_cost, debt_pct_of_capital_cost, equity_pct_of_capital_cost, cost_of_debt,
            cost_of_equity, tax_rate, project_lifetime_years, dcsr
        ],
        outputs=output,
        api_name="calculate"
    )


app = gr.mount_gradio_app(app, interface, path=CUSTOM_PATH)

@app.get("/")
def read_main():
    return {"message": "This is your main app"}

@app.get("/solarpv/")
def get_lcoe(pv_assumptions: Annotated[SolarPVAssumptions, Query()]):
    return calculate_lcoe(pv_assumptions)