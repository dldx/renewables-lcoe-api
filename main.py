from typing import Annotated, Dict, List, Tuple
from urllib.parse import urlencode
from fastapi import FastAPI, Query
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
def read_main():
    # Redirect to the Gradio UI
    return RedirectResponse("/ui")

@app.get("/solarpv/")
def get_lcoe(pv_assumptions: Annotated[SolarPVAssumptions, Query()]):
    return calculate_lcoe(pv_assumptions)