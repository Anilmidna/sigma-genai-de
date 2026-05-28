import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "shared"))

import streamlit as st
import duckdb
from bedrock_helper import call_nova_lite, call_nova_pro

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "shared", "sigma_platform.duckdb")

st.set_page_config(page_title="Schema Archaeologist", layout="wide")
st.title("Schema Archaeologist")
st.caption("Sigma DataTech AI Ops Platform — Day 9")

conn = duckdb.connect(DB_PATH, read_only=True)

# Build your 3-round Streamlit app here.
# Read brief.md for your problem statement and the trap you need to find.
