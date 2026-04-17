import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import re
import google.generativeai as genai
from datetime import datetime
import urllib.parse

# --- PAGE CONFIG ---
st.set_page_config(page_title="Master of Ops Dialer", layout="centered")

# --- 1. CONNECTION & SESSION STATE ---
conn = st.connection("gsheets", type=GSheetsConnection)

if 'index' not in st.session_state:
    st.session_state.index = 0

# --- 2. THE BULLETPROOF PHONE FILTER ---
def clean_phone_for_dialing(phone_value):
    if pd.isna(phone_value) or phone_value == "":
        return None
    phone_str = str(phone_value)
    has_plus = phone_str.startswith('+')
    clean_digits = re.sub(r'\D', '', phone_str)
    return f"+{clean_digits}" if has_plus else clean_digits

# --- 3. THE LOGGING ENGINE ---
def commit_activity(lead_name, outcome, note):
    log_entry = pd.DataFrame([{
        "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Lead Name": lead_name,
        "Outcome": outcome,
        "Note": note,
        "Caller ID": "Alfonso" 
    }])
    try:
        conn.create(worksheet="Activity_Log", data=log_entry)
        st.toast(f"✅ Logged {outcome}")
    except Exception as e:
        st.error(f"Failed to log activity: {e}")

# --- 4. NAVIGATION & DATA LOAD ---
with st.sidebar:
    mode = st.radio("Navigation", ["Dialer", "Dashboard"])
    st.divider()
    if st.button("Reset to Lead 1"):
        st.session_state.index = 0
        st.rerun()

try:
    df = conn.read(ttl=0) 
    if df.empty:
        st.warning("No leads found.")
        st.stop()
except Exception as e:
    st.error(f"Connection failed: {e}")
    st.stop()

# --- MODE: DIALER ---
if mode == "Dialer":
    if st.session_state.index >= len(df):
        st.success("🏁 List Complete!")
        st.stop()

    lead = df.iloc[st.session_state.index]

    st.title(f"📞 {lead.get('First Name', 'N/A')} {lead.get('Last Name', 'N/A')}")
    st.subheader(f"{lead.get('Company Name', 'N/A')} | {lead.get('Title', 'N/A')}")

    col1, col2 = st.columns(2)

    with col1:
        st.info(f"📍 {lead.get('City', 'N/A')}, {lead.get('State', 'N/A')}")
        st.write(f"💰 Revenue: {lead.get('Annual Revenue', '---')}")
        
        raw_phone = lead.get('Corporate Phone', '')
        dial_link = clean_phone_for_dialing(raw_phone)
        
        if dial_link:
            st.link_button(f"📲 DIAL: {raw_phone}", f"tel:{dial_link}", use_container_width=True)
        else:
            st.error("No valid number.")

    with col2:
        rating = st.selectbox("Rating", ["Cold", "Warm", "Hot"], index=1)
        notes = st.text_area("Call Notes", key=f"notes_{st.session_state.index}")
        st.write(f"🏭 **Industry:** {lead.get('Industry', '---')}")

    # --- GEMINI AI EMAIL COMPOSER ---
    st.divider()
    if st.button("🪄 Draft Email"):
        if "GEMINI_API_KEY" not in st.secrets:
            st.error("Missing Gemini Key in Secrets.")
        else:
            try:
                genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
                model = genai.GenerativeModel('gemini-1.5-flash')
                prompt = f"Write a short, witty, 3-sentence follow-up to {lead.get('First Name')} at {lead.get('Company Name')}. Notes: {notes}. Style: Simple language, operator-first."
                response = model.generate_content(prompt)
                email_draft = response.text
                
                st.text_area("Draft", value=email_draft, height=150)
                subject = urllib.parse.quote("Follow up - Master of Ops")
                body = urllib.parse.quote(email_draft)
                st.markdown(f"[✉️ Open in Email App](mailto:{lead.get('Email', '')}?subject={subject}&body={body})")
            except Exception as e:
                st.error(f"AI Error: {e}")

    # --- CALENDAR & LOGGING ---
    cal_title = urllib.parse.quote(f"Follow up: {lead.get('First Name')}")
    st.markdown(f"[📅 Schedule in Calendar](https://www.google.com/calendar/render?action=TEMPLATE&text={cal_title})")
    
    st.divider()
    if st.button("✅ LOG CALL & NEXT LEAD", use_container_width=True):
        df.at[st.session_state.index, 'Rating'] = rating
        df.at[st.session_state.index, 'Notes'] = notes
        df.at[st.session_state.index, 'Last Touch'] = datetime.now().strftime("%Y-%m-%d")
        
        full_name = f"{lead.get('First Name', '')} {lead.get('Last Name', '')}"
        commit_activity(full_name, "Call Completed", notes)
        
        conn.update(data=df)
        st.session_state.index += 1
        st.rerun()

# --- MODE: DASHBOARD ---
elif mode == "Dashboard":
    st.title("📈 Performance Metrics")
    activity_df = conn.read(worksheet="Activity_Log")
    
    if not activity_df.empty:
        c1, c2 = st.columns(2)
        c1.metric("Total Dials", len(activity_df))
        
        activity_df['Timestamp'] = pd.to_datetime(activity_df['Timestamp'])
        weekly_trend = activity_df.resample('W', on='Timestamp').count()['Lead Name']
        st.line_chart(weekly_trend)
    else:
        st.info("No activity logged yet.")

st.caption(f"Operational Status: Running | Lead Index: {st.session_state.index}")
