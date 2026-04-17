import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

st.set_page_config(page_title="Master of Ops Dialer", layout="centered")

conn = st.connection("gsheets", type=GSheetsConnection)

if 'index' not in st.session_state:
    st.session_state.index = 0

try:
    # If we don't specify a worksheet, it pulls the FIRST tab.
    # ACTION: Move your 'Leads' tab to the first position (far left).
    df = conn.read() 
    
    if df.empty:
        st.warning("Sheet is empty. Please add lead data.")
        st.stop()
except Exception as e:
    st.error(f"Connection Error: {e}")
    st.stop()

# Safety check for index
if st.session_state.index >= len(df):
    st.success("🏁 All leads processed!")
    if st.button("Restart"):
        st.session_state.index = 0
        st.rerun()
    st.stop()

lead = df.iloc[st.session_state.index]

# --- UI with Safety Checks ---
# This prevents the app from crashing if a column name is slightly off
fname = lead.get('First Name', 'N/A')
lname = lead.get('Last Name', 'N/A')
cname = lead.get('Company Name', lead.get('Company name', 'Unknown Co'))
title = lead.get('Title', 'No Title')
city = lead.get('City', 'N/A')
state = lead.get('State', 'N/A')
phone = lead.get('Corporate Phone', '')
rev = lead.get('Annual Revenue', 'N/A')

st.title(f"📞 {fname} {lname}")
st.subheader(f"{cname} | {title}")

col1, col2 = st.columns(2)
with col1:
    st.info(f"📍 {city}, {state}")
    st.write(f"💰 Revenue: {rev}")
    if phone:
        st.markdown(f"### [CLICK TO CALL](tel:{phone})")
    else:
        st.warning("No phone number found in 'Corporate Phone' column.")

with col2:
    st.selectbox("Rating", ["Cold", "Warm", "Hot"], index=1)
    st.text_area("Notes")

if st.button("Next Lead ⏭️", use_container_width=True):
    st.session_state.index += 1
    st.rerun()
