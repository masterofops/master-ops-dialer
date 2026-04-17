import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import re

# --- PAGE CONFIG ---
st.set_page_config(page_title="Master of Ops Dialer", layout="centered")

# --- 1. CONNECTION & SESSION STATE ---
conn = st.connection("gsheets", type=GSheetsConnection)

if 'index' not in st.session_state:
    st.session_state.index = 0

# --- 2. THE BULLETPROOF PHONE FILTER ---
def clean_phone_for_dialing(phone_value):
    """
    Strips all non-numeric characters to ensure the tel: link works.
    Ensures +1 is handled if present.
    """
    if pd.isna(phone_value) or phone_value == "":
        return None
    
    # Convert to string and strip all non-digits except '+'
    phone_str = str(phone_value)
    
    # Keep the '+' if it's the first character (for international), 
    # then remove all other non-digits (spaces, dashes, parens)
    has_plus = phone_str.startswith('+')
    clean_digits = re.sub(r'\D', '', phone_str)
    
    if has_plus:
        return f"+{clean_digits}"
    return clean_digits

# --- 3. LOAD DATA ---
try:
    # Set ttl to 0 if you want to see sheet updates immediately on refresh
    df = conn.read(ttl=0) 
    if df.empty:
        st.warning("Inventory Empty: No leads found in the first tab.")
        st.stop()
except Exception as e:
    st.error(f"Handshake failed: {e}")
    st.stop()

# Progress check
if st.session_state.index >= len(df):
    st.success("🏁 List Complete! All targets processed.")
    if st.button("Restart from Lead 1"):
        st.session_state.index = 0
        st.rerun()
    st.stop()

# Current Lead Data
lead = df.iloc[st.session_state.index]

# --- 4. UI LAYOUT ---
st.title(f"📞 {lead.get('First Name', 'N/A')} {lead.get('Last Name', 'N/A')}")
st.subheader(f"{lead.get('Company Name', 'N/A')} | {lead.get('Title', 'N/A')}")

col1, col2 = st.columns(2)

with col1:
    st.info(f"📍 {lead.get('City', 'N/A')}, {lead.get('State', 'N/A')}")
    st.write(f"💰 Revenue: {lead.get('Annual Revenue', 'N/A')}")
    
    # Apply the Bulletproof Filter
    raw_phone = lead.get('Corporate Phone', '')
    dial_link = clean_phone_for_dialing(raw_phone)
    
    if dial_link:
        # st.link_button is the most reliable 'Operator' tool for mobile
        st.link_button(f"📲 DIAL: {raw_phone}", f"tel:{dial_link}", use_container_width=True)
    else:
        st.error("No valid number in 'Corporate Phone' column.")

with col2:
    rating = st.selectbox("Rating", ["Cold", "Warm", "Hot"], index=1)
    # Using a unique key per index so notes don't bleed into the next lead
    notes = st.text_area("Call Notes", key=f"notes_{st.session_state.index}")

with col2:
    st.markdown("### **Company Specs**")
    st.write(f"🏭 **Industry:** {lead.get('Industry', '---')}")
    st.write(f"👥 **Employees:** {lead.get('# Employees', '---')}")
    st.write(f"💰 **Revenue:** {lead.get('Annual Revenue', '---')}")
    
# --- 5. SAVE & LOGGING ---
st.divider()
if st.button("✅ LOG CALL & NEXT LEAD", use_container_width=True):
    # Verdad Operativa: We update the dataframe and push to Google
    df.at[st.session_state.index, 'Rating'] = rating
    df.at[st.session_state.index, 'Notes'] = notes
    
    try:
        conn.update(data=df)
        st.toast("System Updated", icon="💾")
    except Exception as e:
        st.warning("View-Only Mode: Note not saved to Google Sheets.")
    
    st.session_state.index += 1
    st.rerun()

# --- FOOTER ---
st.caption(f"Lead {st.session_state.index + 1} of {len(df)} | Operational Status: Running")
