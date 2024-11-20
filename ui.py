import pandas as pd
import gradio as gr

from typing import Annotated, Dict, List, Tuple
from urllib.parse import urlencode
import plotly.express as px
import plotly.graph_objects as go
from schema import SolarPVAssumptions
from model import calculate_cashflow_for_renewable_project, calculate_lcoe


def process_inputs(
    capacity_mw,
    capacity_factor,
    capital_expenditure_per_kw,
    o_m_cost_pct_of_capital_cost,
    debt_pct_of_capital_cost,
    cost_of_debt,
    cost_of_equity,
    tax_rate,
    project_lifetime_years,
    degradation_rate,
    dcsr,
    financing_mode,
    request: gr.Request,
) -> Tuple[Dict, pd.DataFrame]:
    try:
        # Convert inputs to SolarPVAssumptions model using named parameters
        assumptions = SolarPVAssumptions(
            capacity_mw=capacity_mw,
            capacity_factor=capacity_factor,
            capital_expenditure_per_kw=capital_expenditure_per_kw,
            o_m_cost_pct_of_capital_cost=o_m_cost_pct_of_capital_cost,
            debt_pct_of_capital_cost=(
                debt_pct_of_capital_cost
                if financing_mode == "Manual Debt/Equity Split"
                else None
            ),
            cost_of_debt=cost_of_debt,
            cost_of_equity=cost_of_equity,
            tax_rate=tax_rate,
            project_lifetime_years=project_lifetime_years,
            degradation_rate=degradation_rate,
            dcsr=dcsr,
            targetting_dcsr=(financing_mode == "Target DSCR"),
        )

        # Calculate the LCOE for the project
        lcoe = calculate_lcoe(assumptions)
        cashflow_model, post_tax_equity_irr, breakeven_tariff, adjusted_assumptions = (
            calculate_cashflow_for_renewable_project(
                assumptions, lcoe, return_model=True
            )
        )
        cashflow_model = cashflow_model.to_pandas()
        styled_model = cashflow_model.T
        styled_model.columns = styled_model.loc["Period"].astype(int).astype(str)
        styled_model = (
            styled_model.drop(["Period"]).map(lambda x: f"{x:,.5g}").reset_index()
        )
        return (
            {
                "lcoe": lcoe,
                "api_call": f"{request.request.url.scheme}://{request.request.url.netloc}/solarpv/?{urlencode(assumptions.model_dump())}",
            },
            (
                px.bar(
                    cashflow_model.assign(
                        **{
                            "Debt Outstanding EoP": lambda x: x[
                                "Debt_Outstanding_EoP_mn"
                            ]
                            * 1000
                        }
                    ),
                    x="Period",
                    y="Debt Outstanding EoP",
                )
                .add_trace(
                    go.Scatter(
                        x=cashflow_model["Period"], y=cashflow_model["EBITDA_mn"] * 1000,
                        name="EBITDA",
                    ),

                )
                .update_layout(xaxis_title="Year")
            ),
            adjusted_assumptions.debt_pct_of_capital_cost,
            adjusted_assumptions.equity_pct_of_capital_cost,
            adjusted_assumptions.dcsr,
            styled_model,
        )

    except Exception as e:
        return str(e)


def update_equity_from_debt(debt_pct):
    return gr.update(value=1 - debt_pct)


def get_params(request: gr.Request) -> Dict:
    params = SolarPVAssumptions.model_validate(dict(request.query_params))
    return {
        capacity_mw: params.capacity_mw,
        capacity_factor: params.capacity_factor,
        capital_expenditure_per_kw: params.capital_expenditure_per_kw,
        o_m_cost_pct_of_capital_cost: params.o_m_cost_pct_of_capital_cost,
        cost_of_debt: params.cost_of_debt,
        cost_of_equity: params.cost_of_equity,
        tax_rate: params.tax_rate,
        project_lifetime_years: params.project_lifetime_years,
        degradation_rate: params.degradation_rate,
        dcsr: params.dcsr,
        financing_mode: "Target DSCR" if params.targetting_dcsr else "Manual Debt/Equity Split",
    }


def get_share_url(
    capacity_mw,
    capacity_factor,
    capital_expenditure_per_kw,
    o_m_cost_pct_of_capital_cost,
    debt_pct_of_capital_cost,
    cost_of_debt,
    cost_of_equity,
    tax_rate,
    project_lifetime_years,
    degradation_rate,
    dcsr,
    financing_mode,
    request: gr.Request,
):
    params = {
        "capacity_mw": capacity_mw,
        "capacity_factor": capacity_factor,
        "capital_expenditure_per_kw": capital_expenditure_per_kw,
        "o_m_cost_pct_of_capital_cost": o_m_cost_pct_of_capital_cost,
        "debt_pct_of_capital_cost": debt_pct_of_capital_cost,
        "cost_of_debt": cost_of_debt,
        "cost_of_equity": cost_of_equity,
        "tax_rate": tax_rate,
        "project_lifetime_years": project_lifetime_years,
        "degradation_rate": degradation_rate,
        "dcsr": dcsr,
        "targetting_dcsr": financing_mode == "Target DSCR",
    }
    base_url = "?"
    return gr.Button(link=base_url + urlencode(params))


with gr.Blocks(theme="citrus", title="Renewable LCOE API") as interface:
    results_state = gr.State()
    with gr.Row():
        with gr.Column(scale=8):
            gr.Markdown("# Solar PV Project Cashflow Model [API](/docs)")
        with gr.Column(scale=1):
            submit_btn = gr.Button("Calculate", variant="primary")
            share_url = gr.Button(
                icon="share.svg",
                value="Share assumptions",
                size="sm",
                variant="secondary",
            )
    with gr.Row():
        with gr.Column():
            with gr.Row():
                capacity_mw = gr.Slider(value=30,
                    minimum=1,
                    maximum=1000,
                    step=10,
                    label="Capacity (MW)",
                )
                capacity_factor = gr.Slider(value=0.1,
                    label="Capacity factor (%)",
                    minimum=0,
                    maximum=0.6,
                    step=0.01,
                )
                project_lifetime_years = gr.Slider(value=25,
                    label="Project Lifetime (years)",
                    minimum=5,
                    maximum=50,
                    step=1,
                )
                degradation_rate = gr.Slider(value=0.005,
                    label="Degradation Rate (%)",
                    minimum=0,
                    maximum=0.05,
                    step=0.005,
                )
            with gr.Row():
                capital_expenditure_per_kw = gr.Slider(value=670,
                    label="Capital expenditure ($/kW)",
                    minimum=1e2,
                    maximum=1e3,
                    step=10,
                )
                o_m_cost_pct_of_capital_cost = gr.Slider(value=0.02,
                    label="O&M as % of total cost (%)",
                    minimum=0,
                    maximum=0.5,
                    step=0.01,
                )
            with gr.Row():
                cost_of_debt = gr.Slider(value=0.05,
                    label="Cost of Debt (%)", minimum=0, maximum=0.5, step=0.01
                )
                cost_of_equity = gr.Slider(value=0.10,
                    label="Cost of Equity (%)",
                    minimum=0,
                    maximum=0.5,
                    step=0.01,
                )
                tax_rate = gr.Slider(value=0.3,
                    label="Corporate Tax Rate (%)", minimum=0, maximum=0.5, step=0.01
                )
            with gr.Row():
                with gr.Row():
                    debt_pct_of_capital_cost = gr.Slider(
                        label="Debt Percentage (%)",
                        value=0.8,
                        minimum=0,
                        maximum=1,
                        step=0.01,
                        visible=True,
                        interactive=False,
                    )
                    equity_pct_of_capital_cost = gr.Number(
                        label="Equity Percentage (%)",
                        visible=True,
                        interactive=False,
                        precision=2,
                    )
                    dcsr = gr.Slider(
                        value=1.3,
                        label="Debt Service Coverage Ratio",
                        minimum=1,
                        maximum=2,
                        step=0.05,
                    )
                with gr.Row():
                    financing_mode = gr.Radio(
                        choices=["Target DSCR", "Manual Debt/Equity Split"],
                        value="Target DSCR",
                        show_label=False,
                        visible=True,
                    )

        with gr.Column():
            json_output = gr.JSON()
            line_chart = gr.Plot()
    with gr.Row():
        model_output = gr.Matrix(headers=None, max_height=800)

    # Set up event handlers for all inputs
    input_components = [
        capacity_mw,
        capacity_factor,
        capital_expenditure_per_kw,
        o_m_cost_pct_of_capital_cost,
        debt_pct_of_capital_cost,
        cost_of_debt,
        cost_of_equity,
        tax_rate,
        project_lifetime_years,
        degradation_rate,
        dcsr,
        financing_mode,
    ]

    # for component in input_components:
    #     component.change(
    #         fn=process_inputs,
    #         inputs=input_components + [financing_mode],
    #         outputs=[
    #             json_output,
    #             line_chart,
    #             debt_pct_of_capital_cost,
    #             equity_pct_of_capital_cost,
    #             model_output,
    #         ],
    #         trigger_mode="always_last",
    #     )
    # Remove individual component change handlers and attach to submit button
    submit_btn.click(
    fn=process_inputs,
    inputs=input_components,
    outputs=[
        json_output,
        line_chart,
        debt_pct_of_capital_cost,
        equity_pct_of_capital_cost,
        dcsr,
        model_output,
    ],
    )


    json_output.change(
        fn=get_share_url,
        inputs=[
            capacity_mw,
            capacity_factor,
            capital_expenditure_per_kw,
            o_m_cost_pct_of_capital_cost,
            debt_pct_of_capital_cost,
            cost_of_debt,
            cost_of_equity,
            tax_rate,
            project_lifetime_years,
            degradation_rate,
            dcsr,
            financing_mode,
        ],
        outputs=share_url,
        trigger_mode="always_last",
    )

    interface.load(get_params, None, input_components, trigger_mode="always_last")
    # Run the model on first load
    interface.load(
        process_inputs,
        inputs=input_components,
        outputs=[json_output, line_chart,  debt_pct_of_capital_cost, equity_pct_of_capital_cost, dcsr, model_output],
    )

    def toggle_financing_inputs(choice):
        if choice == "Target DSCR":
            return {
                dcsr: gr.update(interactive=True),
                debt_pct_of_capital_cost: gr.update(interactive=False),
                equity_pct_of_capital_cost: gr.update(),
            }
        else:
            return {
                dcsr: gr.update(interactive=False),
                debt_pct_of_capital_cost: gr.update(interactive=True),
                equity_pct_of_capital_cost: gr.update(),
            }

    financing_mode.change(
        fn=toggle_financing_inputs,
        inputs=[financing_mode],
        outputs=[dcsr, debt_pct_of_capital_cost, equity_pct_of_capital_cost],
    )

    # Add debt percentage change listener
    debt_pct_of_capital_cost.change(
        fn=update_equity_from_debt,
        inputs=[debt_pct_of_capital_cost],
        outputs=[equity_pct_of_capital_cost],
        trigger_mode="always_last"
    )
