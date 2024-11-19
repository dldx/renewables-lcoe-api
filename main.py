from typing import Annotated, Dict, List, Tuple
from urllib.parse import urlencode
from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
import pandas as pd
from schema import SolarPVAssumptions
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

app = gr.mount_gradio_app(app, interface, path="/ui")

@app.get("/")
async def read_main(request: Request):
    # Get query parameters as dictionary
    query_params = dict(request.query_params)

    # Create new URL with parameters
    redirect_url = "/ui"
    if query_params:
        redirect_url += "?" + urlencode(query_params)

    return RedirectResponse(redirect_url)

@app.get("/solarpv/")
def get_lcoe(pv_assumptions: Annotated[SolarPVAssumptions, Query()]):
    return calculate_lcoe(pv_assumptions)