import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

# --- PAGE CONFIG ---
st.set_page_config(page_title="Master of Ops Dialer", layout="centered")

# --- 1. CONNECTION & SESSION STATE ---
conn = st.connection("gsheets", type=GSheetsConnection)

# Initialize the index so we know which lead we are on
if 'index' not in st.session_state:
    st.session_state.index = 0

# --- 2. LOAD DATA ---
try:
    # Pulling data from the 'Leads' tab
    df = conn.read(worksheet="Leads")
    
    if df.empty:
        st.warning("The 'Leads' tab is empty. Please add data to your Google Sheet.")
        st.stop()
        
except Exception as e:
    st.error(f"Handshake failed: {e}")
    st.info("Check: Is the sheet shared with the service account email?")
    st.stop()

# Check if we have reached the end of the list
if st.session_state.index >= len(df):
    st.success("🏁 All leads processed for now! Great execution.")
    if st.button("Restart from Beginning"):
        st.session_state.index = 0
        st.rerun()
    st.stop()

# Identify current lead
lead = df.iloc[st.session_state.index]

# --- 3. UI LAYOUT ---
st.title(f"📞 {lead['First Name']} {lead['Last Name']}")
st.subheader(f"{lead['Company Name']} | {lead['Title']}")

# Action Area
col1, col2 = st.columns(2)
with col1:
    st.info(f"📍 {lead['City']}, {lead['State']}")
    st.write(f"💰 Revenue: {lead['Annual Revenue']}")
    # Use a clean button-style link for mobile tapping
    st.markdown(f"### [CLICK TO CALL](tel:{lead['Corporate Phone']})")

with col2:
    status = st.selectbox("Rating", ["Cold", "Warm", "Hot"], index=1)
    notes = st.text_area("Notes", placeholder="Quick summary of the call...")

# --- 4. OUTCOME BUTTONS (Auto-Logging) ---
def log_and_next(outcome, is_contact):
    # Verdad Operativa: In a future update, we can add conn.update() here
    # to write 'outcome' and 'notes' back to your Google Sheet.
    st.session_state.index += 1
    st.rerun()

st.divider()
c1, c2, c3 = st.columns(3)

with c1:
    if st.button("✅ Connected", use_container_width=True):
        log_and_next("Connected", is_contact=True)

with c2:
    if st.button("📟 Voicemail", use_container_width=True):
        log_and_next("Left Voicemail", is_contact=False)

with c3:
    if st.button("⏭️ Skip / No Answer", use_container_width=True):
        log_and_next("No Answer", is_contact=False)

# Progress indicator at the bottom
st.caption(f"Lead {st.session_state.index + 1} of {len(df)}")
