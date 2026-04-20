import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import re
import google.generativeai as genai
from datetime import datetime
import urllib.parse

# --- PAGE CONFIG ---
st.set_page_config(page_title="Master of Ops Dialer", layout="wide")

# --- 1. CONNECTION & CACHING ---
conn = st.connection("gsheets", type=GSheetsConnection)

# Using session state to prevent unnecessary re-reads
if 'index' not in st.session_state:
    st.session_state.index = 0

# --- 2. SMART PARSER & DATA CLEANING ---
def get_col(df, keywords):
    for col in df.columns:
        if any(key.lower() in str(col).lower() for key in keywords):
            return col
    return None

def clean_phone(val):
    if pd.isna(val) or val == "": return ""
    return re.sub(r'\D', '', str(val))

# --- 3. CORE LOGGING ENGINE ---
def safe_append_activity(new_entry):
    try:
        # Pull current log without cache to ensure integrity before write
        current_log = conn.read(worksheet="Activity_Log", ttl=0).copy()
        updated_log = pd.concat([current_log, new_entry], ignore_index=True)
        conn.update(worksheet="Activity_Log", data=updated_log)
    except:
        conn.create(worksheet="Activity_Log", data=new_entry)
    st.toast(f"✅ Logged: {new_entry['Outcome'].iloc[0]}")

# --- 4. LOAD DATA (WITH CACHE TO FIX 429 ERROR) ---
# We use ttl=300 (5 mins) to stay under Google's 60 requests/min limit
try:
    df = conn.read(ttl=300).copy() 
    for c in df.columns: df[c] = df[c].astype(object)
    
    try:
        activity_log = conn.read(worksheet="Activity_Log", ttl=300).copy()
    except:
        activity_log = pd.DataFrame(columns=["Timestamp", "Lead Name", "Outcome", "Rating", "Note", "User"])
except Exception as e:
    st.error(f"Sync Error (Quota): {e}")
    st.stop()

# Identify columns
col_first = get_col(df, ["first", "name"])
col_last = get_col(df, ["last"])
col_comp = get_col(df, ["company", "account"])
col_phone = get_col(df, ["phone", "mobile", "tel"])
col_email = get_col(df, ["email", "@"])
col_notes = get_col(df, ["notes", "comment", "history"])
col_li_person = get_col(df, ["linkedin", "profile"])

# --- SIDEBAR & UPLOADER ---
with st.sidebar:
    st.title("MASTER OF OPS")
    mode = st.radio("Navigation", ["Dialer", "Dashboard"])
    
    st.divider()
    # Force Sync Button to bypass cache
    if st.button("🔄 Sync with Google Sheets"):
        st.cache_data.clear()
        st.rerun()

    # Lead Uploader
    st.subheader("📤 Upload Leads")
    uploaded_file = st.file_uploader("Drop CSV or Excel", type=["csv", "xlsx"])
    if uploaded_file:
        new_leads = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('csv') else pd.read_excel(uploaded_file)
        if st.button("Confirm Upload"):
            updated_df = pd.concat([df, new_leads], ignore_index=True)
            conn.update(data=updated_df)
            st.success("Leads Added!")
            st.rerun()

    st.divider()
    if st.button("🏠 HOME (Lead 1)"):
        st.session_state.index = 0
        st.rerun()
    
    sheet_url = "https://docs.google.com/spreadsheets/d/1YWt8gtPMQHCZQO91tl_I0iv592Q_yhPBR1SUdbIQP6g/"
    st.markdown(f"🔗 [Open Master Sheet]({sheet_url})")

# --- MODE: DIALER ---
if mode == "Dialer":
    if st.session_state.index >= len(df):
        st.success("🏁 All leads processed!")
        st.stop()

    lead = df.iloc[st.session_state.index]
    orig_idx = lead.name
    full_name = f"{lead.get(col_first, '')} {lead.get(col_last, '')}"
    
    st.title(f"📞 {full_name}")
    st.caption(f"Lead {st.session_state.index + 1} of {len(df)} | {lead.get(col_comp, 'N/A')}")

    # Previous History
    past = activity_log[activity_log['Lead Name'] == full_name]
    if not past.empty:
        with st.expander("🕒 PREVIOUS CONTACT HISTORY", expanded=True):
            st.table(past[['Timestamp', 'Outcome', 'Note']].tail(3))

    col_l, col_r = st.columns([1, 1])

    with col_l:
        st.markdown("### ⚡ Execution")
        phone_raw = lead.get(col_phone, '')
        if phone_raw:
            st.link_button(f"📲 CALL: {phone_raw}", f"tel:{clean_phone(phone_raw)}", use_container_width=True, type="primary")
        
        contact_made = st.checkbox("👤 CONTACT MADE")
        rating = st.selectbox("Lead Rating", ["Cold", "Warm", "Hot"], index=1)
        new_note = st.text_area("New Call Note")

    with col_r:
        st.markdown("### 🧠 Lead Intel")
        st.write(f"🌐 **Email:** {lead.get(col_email, 'N/A')}")
        st.write(f"👤 **LinkedIn:** [Profile]({lead.get(col_li_person, '#')})")
        st.info(f"📋 **History:**\n\n {lead.get(col_notes, 'No history.')}")

    # Action Logic
    def log_action(outcome, move_next=True):
        ts = datetime.now().strftime("%m/%d %H:%M")
        old = str(lead.get(col_notes, "")) if not pd.isna(lead.get(col_notes)) else ""
        combined = f"[{ts}]: {new_note} | {old}"
        
        df.at[orig_idx, col_notes] = combined
        df.at[orig_idx, 'Rating'] = rating
        df.at[orig_idx, 'Last Touch'] = datetime.now().strftime("%Y-%m-%d")
        
        conn.update(data=df)
        entry = pd.DataFrame([{"Timestamp": datetime.now(), "Lead Name": full_name, "Outcome": outcome, "Note": new_note, "Rating": rating, "User": "Alfonso"}])
        safe_append_activity(entry)
        
        if move_next:
            st.session_state.index += 1
            st.rerun()

    st.divider()
    c1, c2, c3, c4 = st.columns(4)
    
    with c1:
        if st.button("✅ LOG & NEXT", type="primary", use_container_width=True):
            log_action("Contact Made" if contact_made else "Outbound Call")

    with c2:
        cal_title = urllib.parse.quote(f"Follow up: {full_name}")
        cal_url = f"https://www.google.com/calendar/render?action=TEMPLATE&text={cal_title}"
        # Direct link + logging combined
        if st.button("📅 APPOINTMENT", use_container_width=True):
            log_action("Appointment Scheduled")
            st.markdown(f'<meta http-equiv="refresh" content="0;URL=\'{cal_url}\' \">', unsafe_allow_html=True)

    with c3:
        if st.button("💸 CLOSED DEAL", use_container_width=True):
            st.balloons()
            log_action("Closed Deal")

    with c4:
        # Email System
        email_addr = lead.get(col_email, '')
        if st.button("✉️ DRAFT EMAIL", use_container_width=True):
            subject = urllib.parse.quote("Master of Ops - Follow up")
            body = urllib.parse.quote(f"Hi {lead.get(col_first)},\n\nFollowing up on our conversation regarding {lead.get(col_comp)}.")
            st.markdown(f'<meta http-equiv="refresh" content="0;URL=\'mailto:{email_addr}?subject={subject}&body={body}\' \">', unsafe_allow_html=True)

# --- DASHBOARD ---
elif mode == "Dashboard":
    st.title("📈 Performance Stats")
    if not activity_log.empty:
        activity_log['Timestamp'] = pd.to_datetime(activity_log['Timestamp'], errors='coerce')
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Total Dials", len(activity_log))
        k2.metric("Contacts", len(activity_log[activity_log['Outcome'] == 'Contact Made']))
        k3.metric("Appointments", len(activity_log[activity_log['Outcome'] == 'Appointment Scheduled']))
        k4.metric("Closed Deals", len(activity_log[activity_log['Outcome'] == 'Closed Deal']))
        st.line_chart(activity_log.set_index('Timestamp').resample('D').count()['Lead Name'])
