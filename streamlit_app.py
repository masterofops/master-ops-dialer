import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import re
import google.generativeai as genai
from datetime import datetime
import datetime as dt
import urllib.parse

# --- PAGE CONFIG ---
st.set_page_config(page_title="Master of Ops Dialer", layout="wide")

# --- 1. CONNECTION & SESSION STATE ---
conn = st.connection("gsheets", type=GSheetsConnection)

if 'index' not in st.session_state:
    st.session_state.index = 0

# --- 2. UTILITY FUNCTIONS ---
def clean_phone_for_dialing(phone_value):
    if pd.isna(phone_value) or phone_value == "":
        return None
    phone_str = str(phone_value)
    has_plus = phone_str.startswith('+')
    clean_digits = re.sub(r'\D', '', phone_str)
    return f"+{clean_digits}" if has_plus else clean_digits

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

# --- 3. NAVIGATION & DATA LOAD ---
with st.sidebar:
    st.image("https://via.placeholder.com/150x50?text=MASTER+OF+OPS", use_container_width=True)
    mode = st.radio("Navigation", ["Dialer", "Dashboard"])
    st.divider()
    
    # Quick Link to Source
    sheet_url = st.secrets.get("connections", {}).get("gsheets", {}).get("spreadsheet", "#")
    st.markdown(f"[📂 Open Google Sheet]({sheet_url})")
    
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
    original_idx = lead.name # CRITICAL for correct spreadsheet updates

    st.title(f"📞 {lead.get('First Name', 'N/A')} {lead.get('Last Name', 'N/A')}")
    st.caption(f"{lead.get('Title', 'N/A')} @ {lead.get('Company Name', 'N/A')}")

    # --- ROW 1: ACTION CENTER ---
    col_call, col_intel = st.columns([1, 1])

    with col_call:
        st.subheader("Action Center")
        raw_phone = lead.get('Corporate Phone', '')
        dial_link = clean_phone_for_dialing(raw_phone)
        
        if dial_link:
            st.link_button(f"📲 DIAL: {raw_phone}", f"tel:{dial_link}", use_container_width=True, type="primary")
        else:
            st.error("No valid number.")

        rating = st.selectbox("Lead Rating", ["Cold", "Warm", "Hot"], index=1)
        notes = st.text_area("Call Notes", placeholder="What happened on the call?", key=f"notes_{st.session_state.index}")

    with col_intel:
        st.subheader("Lead Intel")
        # Displaying extra fields requested
        st.write(f"🏢 **Website:** [{lead.get('Website', 'N/A')}]({lead.get('Website', '#')})")
        st.write(f"👤 **Personal LinkedIn:** [Profile]({lead.get('Person Linkedin Url', '#')})")
        st.write(f"🏭 **Company LinkedIn:** [Company Page]({lead.get('Company Linkedin Url', '#')})")
        
        metrics_col1, metrics_col2 = st.columns(2)
        metrics_col1.write(f"💰 **Revenue:** {lead.get('Annual Revenue', '---')}")
        metrics_col1.write(f"👥 **Employees:** {lead.get('Employees', '---')}")
        metrics_col2.write(f"📍 **Location:** {lead.get('City', 'N/A')}, {lead.get('State', 'N/A')}")
        metrics_col2.write(f"🔑 **Keywords:** {lead.get('Industry', '---')}")

    # --- ROW 2: AI & EMAIL ---
    st.divider()
    if st.button("🪄 Draft & Open Email"):
        if "GEMINI_API_KEY" not in st.secrets:
            st.error("Missing Gemini Key in Secrets.")
        else:
            try:
                genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
                model = genai.GenerativeModel('gemini-1.5-flash')
                prompt = f"Write a short, witty, 3-sentence follow-up to {lead.get('First Name')} at {lead.get('Company Name')}. Notes: {notes}. Use 'operator-first' style."
                response = model.generate_content(prompt)
                email_draft = response.text
                
                # Setup Mailto Link
                subject = urllib.parse.quote("Quick Follow up - Master of Ops")
                body = urllib.parse.quote(email_draft)
                email_addr = lead.get('Email', '')
                mailto_url = f"mailto:{email_addr}?subject={subject}&body={body}"
                
                # Auto-open via JS redirect or link
                st.markdown(f'<meta http-equiv="refresh" content="0;URL=\'{mailto_url}\' \">', unsafe_allow_html=True)
                st.success(f"Opening email for {email_addr}...")
            except Exception as e:
                st.error(f"AI Error: {e}")

    # --- ROW 3: LOGGING & NAVIGATION ---
    st.divider()
    btn_col1, btn_col2, btn_col3 = st.columns([2, 1, 1])
    
    with btn_col1:
        if st.button("✅ LOG CALL & NEXT LEAD", use_container_width=True, type="primary"):
            # Update values in the main dataframe
            df.at[original_idx, 'Rating'] = rating
            df.at[original_idx, 'Notes'] = notes
            df.at[original_idx, 'Last Touch'] = datetime.now().strftime("%Y-%m-%d")
            
            full_name = f"{lead.get('First Name', '')} {lead.get('Last Name', '')}"
            commit_activity(full_name, "Call Completed", notes)
            
            conn.update(data=df)
            st.session_state.index += 1
            st.rerun()

    with btn_col2:
        if st.button("⏭️ SKIP LEAD", use_container_width=True):
            st.session_state.index += 1
            st.rerun()

    with btn_col3:
        cal_title = urllib.parse.quote(f"Follow up: {lead.get('First Name')}")
        st.markdown(f"[📅 Schedule](https://www.google.com/calendar/render?action=TEMPLATE&text={cal_title})")

# --- MODE: DASHBOARD ---
elif mode == "Dashboard":
    st.title("📈 Sales Execution Dashboard")
    activity_df = conn.read(worksheet="Activity_Log")
    
    # Layout for KPIs
    kpi1, kpi2, kpi3 = st.columns(3)
    
    # Total Dials
    total_dials = len(activity_df) if not activity_df.empty else 0
    kpi1.metric("Total Dials", total_dials)

    # Conversion Rate (Hot Leads)
    hot_leads = len(df[df['Rating'] == 'Hot'])
    conv_rate = (hot_leads / len(df) * 100) if len(df) > 0 else 0
    kpi2.metric("Hot Lead Conversion", f"{conv_rate:.1f}%")

    # List Penetration
    progress = (st.session_state.index / len(df) * 100) if len(df) > 0 else 0
    kpi3.metric("List Progress", f"{progress:.1f}%")

    st.divider()
    
    if not activity_df.empty:
        st.subheader("Activity Trend")
        activity_df['Timestamp'] = pd.to_datetime(activity_df['Timestamp'])
        daily_trend = activity_df.resample('D', on='Timestamp').count()['Lead Name']
        st.area_chart(daily_trend)
        
        st.subheader("Recent Activity Log")
        st.dataframe(activity_df.sort_values("Timestamp", ascending=False).head(10), use_container_width=True)
    else:
        st.info("No activity logged yet. Start dialing!")

st.caption(f"Operational Status: Active | Lead {st.session_state.index + 1} of {len(df)}")
