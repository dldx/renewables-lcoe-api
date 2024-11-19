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
    print(request.url.components)
    print(request.url.scheme)
    print(request.url.netloc)
    print("hf.space" in request.url.netloc)
    redirect_url = (request.url.scheme if "hf.space" not in request.url.netloc else "https") + "://" + request.url.netloc + request.url.path + "ui"
    print(redirect_url)
    if query_params:
        redirect_url += "?" + urlencode(query_params)

    return RedirectResponse(redirect_url)

@app.get("/solarpv/")
def get_lcoe(pv_assumptions: Annotated[SolarPVAssumptions, Query()]):
    return calculate_lcoe(pv_assumptions)