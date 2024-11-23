from typing import Annotated, Dict, List, Optional, Tuple
from urllib.parse import urlencode
from fastapi import FastAPI, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, RedirectResponse
import pandas as pd
from pydantic import Field, model_validator
from capacity_factors import get_solar_capacity_factor
from schema import CapacityFactor, Location, SolarPVAssumptions
from model import calculate_cashflow_for_renewable_project, calculate_lcoe

app = FastAPI()

import gradio as gr
from ui import interface

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/solarpv/lcoe")
def get_lcoe(pv_assumptions: Annotated[SolarPVAssumptions, Query()]):
    return calculate_lcoe(pv_assumptions)


class SolarPVAssumptionsWithLCOE(SolarPVAssumptions):
    lcoe: Annotated[float, Field(title="Levelized cost of electricity (USD/MWh)", description="The levelized cost of electricity in USD/MWh")]


@app.get("/solarpv/lcoe.json")
def get_lcoe_json(
    pv_assumptions: Annotated[SolarPVAssumptions, Query()]
) -> SolarPVAssumptionsWithLCOE:
    return SolarPVAssumptionsWithLCOE(
        **{"lcoe": calculate_lcoe(pv_assumptions), **pv_assumptions.model_dump()}
    )


@app.get("/solarpv/capacity_factor.json")
def get_capacity_factor(pv_location: Annotated[Location, Query()]) -> CapacityFactor:
    return CapacityFactor(
        capacity_factor=get_solar_capacity_factor(pv_location.longitude, pv_location.latitude),  # type: ignore
        **pv_location.model_dump(),
    )


class CashflowParams(SolarPVAssumptions):
    tariff: Annotated[
        Optional[float],
        Query(
            title="Tariff (USD/MWh)",
            description="If a tariff in USD/MWh is supplied, it will be used to calculate the cashflow. If not, the break-even tariff will be calculated from the assumptions.",
            gt=0,
        ),
    ] = None
    transpose: Annotated[
        bool,
        Query(
            title="Transpose cashflows",
            description="Transpose the cashflow table to have years as columns and cashflows as rows",
            default=False,
        ),
    ] = False

    # If tariff is not provided, calculate it from the assumptions
    @model_validator(mode="after")
    @classmethod
    def calculate_tariff(cls, values):
        if values.tariff is None:
            values.tariff = calculate_lcoe(values)
        return values


@app.get("/solarpv/cashflow.csv", response_class=PlainTextResponse)
def get_cashflow(params: Annotated[CashflowParams, Query()]) -> str:
    cashflow = calculate_cashflow_for_renewable_project(
        params, tariff=params.tariff, return_model=True
    )[0]
    if params.transpose:
        cashflow = cashflow.to_pandas().T
        cashflow.columns = cashflow.loc["Period"].astype(int).astype(str)
        return cashflow.drop(["Period"]).to_csv(float_format="%.3f")
    return cashflow.write_csv(float_precision=3)


app = gr.mount_gradio_app(app, interface, path="/")
