from typing import Annotated, Dict, List, Optional, Tuple
from urllib.parse import urlencode
from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
import pandas as pd
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


# @app.get("/")
# async def read_main(request: Request):
#     # Get query parameters as dictionary
#     query_params = dict(request.query_params)

#     # Create new URL with parameters
#     print(request.url.components)
#     print(request.url.scheme)
#     print(request.url.netloc)
#     print("hf.space" in request.url.netloc)
#     redirect_url = (request.url.scheme if "hf.space" not in request.url.netloc else "https") + "://" + request.url.netloc + request.url.path + "ui"
#     print(redirect_url)
#     if query_params:
#         redirect_url += "?" + urlencode(query_params)

#     return RedirectResponse(redirect_url)


@app.get("/solarpv")
def get_lcoe(pv_assumptions: Annotated[SolarPVAssumptions, Query()]):
    return calculate_lcoe(pv_assumptions)


@app.get("/solarpv/capacity_factor.json")
def get_capacity_factor(pv_location: Annotated[Location, Query()]) -> CapacityFactor:
    return CapacityFactor(
        capacity_factor=get_solar_capacity_factor(pv_location.longitude, pv_location.latitude),  # type: ignore
        **pv_location.model_dump(),
    )


app = gr.mount_gradio_app(app, interface, path="/")
