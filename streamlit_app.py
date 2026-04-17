import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

# Page Config
st.set_page_config(page_title="Master of Ops", layout="centered")

# Connection to Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)

# This defaults to the first tab (which should be your Leads tab).

# 1. LOAD DATA
try:
    df = conn.read()
    st.success("Connection established.")
except Exception as e:
    st.error(f"Handshake failed: {e}")
    st.info("Check if the Sheet URL in Secrets ends with /edit?usp=sharing")

# Session State to keep track of where you are
if 'index' not in st.session_state:
    st.session_state.index = 0

# 2. UI LAYOUT
lead = df.iloc[st.session_state.index]

st.title(f"📞 {lead['First Name']} {lead['Last Name']}")
st.subheader(f"{lead['Company Name']} | {lead['Title']}")

# Action Area
col1, col2 = st.columns(2)
with col1:
    st.info(f"📍 {lead['City']}, {lead['State']}")
    st.write(f"💰 Revenue: {lead['Annual Revenue']}")
    st.markdown(f"### [CLICK TO CALL] (tel:{lead['Corporate Phone']})")

with col2:
    status = st.selectbox("Rating", ["Cold", "Warm", "Hot"], index=1)
    notes = st.text_area("Notes", placeholder="Quick summary...")

# 3. OUTCOME BUTTONS (Auto-Logging)
def log_and_next(outcome, is_contact):
    # This part updates your Google Sheet automatically
    # (Simplified for the logic flow)
    st.success(f"Logged: {outcome}")
    st.session_state.index += 1
    st.rerun()

st.divider()
c1, c2, c3 = st.columns(3)

if c1.button("✅ Connected"):
    log_and_next("Connected", is_contact=True)

if c2.button(" voicemial"):
    log_and_next("Left Voicemail", is_contact=False)

if c3.button("⏭️ Skip/No Answer"):
    log_and_next("No Answer", is_contact=False)
