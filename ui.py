import pandas as pd
import gradio as gr

from typing import Annotated, Dict, List, Tuple
from urllib.parse import urlencode
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio

from capacity_factors import get_solar_capacity_factor

pio.templates.default = "plotly_dark"

from plotly.subplots import make_subplots
from schema import CapacityFactor, Location, SolarPVAssumptions
from model import calculate_cashflow_for_renewable_project, calculate_lcoe


def plot_cashflow(cashflow_model: pd.DataFrame) -> gr.Plot:
    return (
        px.bar(
            cashflow_model.assign(
                **{
                    "Debt Outstanding EoP": lambda x: x["Debt_Outstanding_EoP_mn"]
                    * 1000
                }
            ),
            x="Period",
            y="Debt Outstanding EoP",
        )
        .add_trace(
            go.Scatter(
                x=cashflow_model["Period"],
                y=cashflow_model["EBITDA_mn"] * 1000,
                name="EBITDA",
            ),
        )
        .update_layout(
            xaxis_title="Year",
            # Legend at top of chart
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                # xanchor="right",
            ),
            margin=dict(l=50, r=50, t=100, b=50),
        )
    )


def plot_revenues_costs(cashflow_model: pd.DataFrame) -> gr.Plot:
    # Convert the model to a pandas dataframe
    df = cashflow_model
    # Negate the Total_Operating_Costs_mn values
    df["Total Operating Costs"] = -df["Total_Operating_Costs_mn"] * 1000
    df["Total Revenues"] = df["Total_Revenues_mn"] * 1000
    df["Target Debt Service"] = df["Target_Debt_Service_mn"] * 1000
    df["DSCR"] = df["CFADS_mn"] / df["Target_Debt_Service_mn"]
    # Round the values to 4 decimal places
    df["DSCR"] = df["DSCR"].round(4)

    # Create a new dataframe with the required columns
    plot_df = df[
        [
            "Period",
            "Total Revenues",
            "Total Operating Costs",
            "Target Debt Service",
        ]
    ]

    # Melt the dataframe to have a long format suitable for plotly express
    plot_df = plot_df.melt(
        id_vars="Period",
        value_vars=[
            "Total Revenues",
            "Total Operating Costs",
            "Target Debt Service",
        ],
        var_name="Type",
        value_name="Amount",
    )

    # Create a subplots figure to handle multiple axes
    subfig = make_subplots(specs=[[{"secondary_y": True}]])

    # Plot the bar chart
    fig = px.bar(
        plot_df,
        x="Period",
        y="Amount",
        color="Type",
        barmode="overlay",
        title="Total Revenues and Total Operating Costs",
    )
    subfig.add_trace(fig.data[0], secondary_y=False)
    subfig.add_trace(fig.data[1], secondary_y=False)
    subfig.add_trace(fig.data[2], secondary_y=False)
    # Add line trace for EBITDA
    subfig.add_trace(
        go.Scatter(
            x=df["Period"],
            y=df["EBITDA_mn"] * 1000,
            mode="lines+markers",
            name="EBITDA",
            line=dict(color="green"),
        )
    )
    # Add line trace for post-tax net-equity cashflow
    subfig.add_trace(
        go.Scatter(
            x=df["Period"],
            y=df["Post_Tax_Net_Equity_Cashflow_mn"] * 1000,
            mode="lines+markers",
            name="Post-Tax Net Equity Cashflow",
            line=dict(color="red"),
        )
    )

    # Add the DSCR line
    subfig.add_trace(
        go.Scatter(
            x=df["Period"],
            y=df["DSCR"],
            mode="lines+markers",
            name="DSCR",
            line=dict(color="purple"),
        ),
        secondary_y=True,
    )

    subfig.update_layout(
        # Legend at top of chart
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            # xanchor="right",
        ),
        margin=dict(l=50, r=50, t=130, b=50),
        barmode="overlay",
        title="Total Revenues, Total Operating Costs, and DSCR",
        xaxis_title="Year",
        yaxis_title="Amount",
        yaxis2_title="DSCR",
    )
    return subfig


def trigger_lcoe(
    capacity_mw,
    capacity_factor,
    capital_expenditure_per_kw,
    o_m_cost_pct_of_capital_cost,
    debt_pct_of_capital_cost,
    cost_of_debt,
    cost_of_equity,
    tax_rate,
    project_lifetime_years,
    loan_tenor_years,
    degradation_rate,
    dscr,
    financing_mode,
    request: gr.Request,
) -> Tuple[
    Dict, gr.Plot, gr.Plot, gr.Slider, gr.Number, gr.Slider, gr.Matrix, gr.Markdown
]:
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
            loan_tenor_years=loan_tenor_years,
            degradation_rate=degradation_rate,
            dscr=dscr,
            targetting_dscr=(financing_mode == "Target DSCR"),
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
                "post_tax_equity_irr": post_tax_equity_irr,
                "debt_service_coverage_ratio": adjusted_assumptions.dscr,
                "debt_pct_of_capital_cost": adjusted_assumptions.debt_pct_of_capital_cost,
                "equity_pct_of_capital_cost": adjusted_assumptions.debt_pct_of_capital_cost,
                "api_call": f"{request.request.url.scheme}://{request.request.url.netloc}/solarpv/lcoe?{urlencode(assumptions.model_dump())}",
            },
            plot_cashflow(cashflow_model),
            plot_revenues_costs(cashflow_model),
            adjusted_assumptions.debt_pct_of_capital_cost,
            adjusted_assumptions.equity_pct_of_capital_cost,
            adjusted_assumptions.dscr,
            styled_model,
            gr.Markdown(f"## LCOE: {lcoe:,.2f}"),
        )

    except Exception as e:
        return str(e)


def update_equity_from_debt(debt_pct):
    return gr.update(value=1 - debt_pct)


def get_params(request: gr.Request) -> Dict:
    params = SolarPVAssumptions.model_validate(dict(request.query_params))
    location_params = dict(
        longitude=request.query_params.get("longitude"),
        latitude=request.query_params.get("latitude"),
        address=request.query_params.get("address"),
    )
    for key in location_params:
        if location_params[key] == "None":
            location_params[key] = None
        if location_params[key] is not None and key in ["latitude", "longitude"]:
            location_params[key] = float(location_params[key])

    return {
        capacity_mw: params.capacity_mw,
        capacity_factor: params.capacity_factor,
        capital_expenditure_per_kw: params.capital_expenditure_per_kw,
        o_m_cost_pct_of_capital_cost: params.o_m_cost_pct_of_capital_cost,
        cost_of_debt: params.cost_of_debt,
        cost_of_equity: params.cost_of_equity,
        tax_rate: params.tax_rate,
        project_lifetime_years: params.project_lifetime_years,
        loan_tenor_years: (
            params.loan_tenor_years
            if params.loan_tenor_years
            else params.project_lifetime_years
        ),
        degradation_rate: params.degradation_rate,
        debt_pct_of_capital_cost: params.debt_pct_of_capital_cost,
        dscr: params.dscr,
        financing_mode: (
            "Target DSCR" if params.targetting_dscr else "Manual Debt/Equity Split"
        ),
        latitude: location_params["latitude"],
        longitude: location_params["longitude"],
        address: location_params["address"],
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
    loan_tenor_years,
    degradation_rate,
    dscr,
    financing_mode,
    latitude,
    longitude,
    address,
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
        "loan_tenor_years": loan_tenor_years,
        "degradation_rate": degradation_rate,
        "dscr": dscr,
        "targetting_dscr": financing_mode == "Target DSCR",
        "latitude": latitude if latitude != 51.5074 else None,
        "longitude": longitude if longitude != -0.1278 else None,
        "address": address if address else None,
    }
    base_url = "?"
    return gr.Button(link=base_url + urlencode(params))


with gr.Blocks(theme="citrus", title="Renewable LCOE API") as interface:
    results_state = gr.State()
    with gr.Row():
        with gr.Column(scale=8):
            gr.Markdown("# Solar PV Project Cashflow Model [API](/docs)")
            lcoe_result = gr.Markdown("## LCOE: 0.00")
        with gr.Column(scale=1):
            submit_btn = gr.Button("Calculate", variant="primary")
        with gr.Column(scale=1):
            share_url = gr.Button(
                icon="share.svg",
                value="Share assumptions",
                variant="secondary",
            )
    with gr.Row():
        with gr.Column():
            with gr.Row():
                with gr.Column():
                    latitude = gr.Number(
                        value=51.5074,
                        label="Latitude",
                        minimum=-90,
                        maximum=90,
                        step=0.1,
                    )
                    longitude = gr.Number(
                        value=-0.1278,
                        label="Longitude",
                        minimum=-180,
                        maximum=180,
                        step=0.1,
                    )
                    address = gr.Text(
                        label="Location", placeholder="London, UK", interactive=True
                    )
                    estimate_capacity_factor = gr.Button("Estimate capacity factor")
                with gr.Column():
                    location_plot = gr.Plot()
            with gr.Row():
                capacity_mw = gr.Slider(
                    value=30,
                    minimum=1,
                    maximum=1000,
                    step=10,
                    label="Capacity (MW)",
                )
                capacity_factor = gr.Slider(
                    value=0.1,
                    label="Capacity factor (%)",
                    minimum=0,
                    maximum=0.6,
                    step=0.01,
                )
                degradation_rate = gr.Slider(
                    value=0.005,
                    label="Degradation Rate (%)",
                    minimum=0,
                    maximum=0.05,
                    step=0.005,
                )
            with gr.Row():
                project_lifetime_years = gr.Slider(
                    value=25,
                    label="Project Lifetime (years)",
                    minimum=5,
                    maximum=50,
                    step=1,
                )
                loan_tenor_years = gr.Slider(
                    value=25,
                    label="Loan Tenor (years)",
                    minimum=5,
                    maximum=50,
                    step=1,
                )
            with gr.Row():
                capital_expenditure_per_kw = gr.Slider(
                    value=670,
                    label="Capital expenditure ($/kW)",
                    minimum=1e2,
                    maximum=5e3,
                    step=10,
                )
                o_m_cost_pct_of_capital_cost = gr.Slider(
                    value=0.02,
                    label="O&M as % of total cost (%)",
                    minimum=0,
                    maximum=0.5,
                    step=0.01,
                )
            with gr.Row():
                cost_of_debt = gr.Slider(
                    value=0.05,
                    label="Cost of Debt (%)",
                    minimum=0,
                    maximum=0.5,
                    step=0.01,
                )
                cost_of_equity = gr.Slider(
                    value=0.10,
                    label="Cost of Equity (%)",
                    minimum=0,
                    maximum=0.5,
                    step=0.01,
                )
                tax_rate = gr.Slider(
                    value=0.3,
                    label="Corporate Tax Rate (%)",
                    minimum=0,
                    maximum=0.5,
                    step=0.01,
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
                    dscr = gr.Slider(
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
            with gr.Tab("Revenues and Costs"):
                revenue_cost_chart = gr.Plot()
            with gr.Tab("Debt cashflow"):
                cashflow_bar_chart = gr.Plot()
    with gr.Row():
        model_output = gr.Matrix(headers=None, max_height=800)
    with gr.Row():
        with gr.Column(scale=1):
            gr.Button(
                link="https://github.com/dldx/renewables-lcoe-api",
                value="Source Code",
                variant="secondary",
                size="sm",
            )

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
        loan_tenor_years,
        degradation_rate,
        dscr,
        financing_mode,
    ]

    # Trigger calculation with submit button
    gr.on(
        triggers=[submit_btn.click, capacity_factor.change],
        fn=trigger_lcoe,
        inputs=input_components,
        outputs=[
            json_output,
            cashflow_bar_chart,
            revenue_cost_chart,
            debt_pct_of_capital_cost,
            equity_pct_of_capital_cost,
            dscr,
            model_output,
            lcoe_result,
        ],
    )

    json_output.change(
        fn=get_share_url,
        inputs=input_components
        + [
            latitude,
            longitude,
            address,
        ],
        outputs=share_url,
        trigger_mode="always_last",
    )

    # Load URL parameters into assumptions and then trigger the process_inputs function
    interface.load(
        get_params,
        None,
        input_components
        + [
            latitude,
            longitude,
            address,
        ],
        trigger_mode="always_last",
    ).then(
        trigger_lcoe,
        inputs=input_components,
        outputs=[
            json_output,
            cashflow_bar_chart,
            revenue_cost_chart,
            debt_pct_of_capital_cost,
            equity_pct_of_capital_cost,
            dscr,
            model_output,
            lcoe_result,
        ],
    )

    def toggle_financing_inputs(choice):
        if choice == "Target DSCR":
            return {
                dscr: gr.update(interactive=True),
                debt_pct_of_capital_cost: gr.update(interactive=False),
            }
        else:
            return {
                dscr: gr.update(interactive=False),
                debt_pct_of_capital_cost: gr.update(interactive=True),
            }

    financing_mode.change(
        fn=toggle_financing_inputs,
        inputs=[financing_mode],
        outputs=[dscr, debt_pct_of_capital_cost, equity_pct_of_capital_cost],
    )

    # Add debt percentage change listener
    debt_pct_of_capital_cost.change(
        fn=update_equity_from_debt,
        inputs=[debt_pct_of_capital_cost],
        outputs=[equity_pct_of_capital_cost],
        trigger_mode="always_last",
    )

    def get_capacity_factor_from_location(
        latitude, longitude, address
    ) -> Tuple[float, float, float, str]:
        """Get the capacity factor for a given latitude and longitude, or location."""
        pv_location = Location(latitude=latitude, longitude=longitude, address=address)
        cf = get_solar_capacity_factor(pv_location.longitude, pv_location.latitude)
        return (
            cf,
            pv_location.latitude,
            pv_location.longitude,
            pv_location.address,
        )

    gr.on(
        [estimate_capacity_factor.click, interface.load],
        fn=get_capacity_factor_from_location,
        inputs=[latitude, longitude, address],
        outputs=[capacity_factor, latitude, longitude, address],
    )

    def update_location_plot(latitude, longitude, address):
        return px.scatter_mapbox(
            pd.DataFrame(
                {"latitude": [latitude], "longitude": [longitude], "address": [address]}
            ),
            lat="latitude",
            lon="longitude",
            mapbox_style="carto-darkmatter",
            labels="address",
            size=[10],
        ).update_layout(
            margin=dict(l=0, r=0, t=0, b=0),
            mapbox=dict(
                center=dict(lat=latitude, lon=longitude),
                zoom=10,
            ),
        )

    gr.on(
        [latitude.change, longitude.change, interface.load],
        fn=update_location_plot,
        inputs=[latitude, longitude, address],
        outputs=[location_plot],
    )

    gr.on(
        [address.input],
        fn=lambda: (None, None),
        inputs=[],
        outputs=[latitude, longitude],
    )

    # If user changes the project lifetime, set the maximum loan tenor to the project lifetime
    def update_loan_tenor(project_lifetime_years, loan_tenor_years):
        if project_lifetime_years < loan_tenor_years:
            return gr.Slider(
                value=project_lifetime_years, maximum=project_lifetime_years
            )
        return gr.Slider(maximum=project_lifetime_years)

    project_lifetime_years.change(
        fn=update_loan_tenor,
        inputs=[project_lifetime_years, loan_tenor_years],
        outputs=[loan_tenor_years],
    )
