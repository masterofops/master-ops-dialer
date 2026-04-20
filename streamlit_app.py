import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import re
import google.generativeai as genai
from datetime import datetime
import urllib.parse

# --- PAGE CONFIG ---
st.set_page_config(page_title="Master of Ops Dialer", layout="wide")

# --- 1. CONNECTION ---
conn = st.connection("gsheets", type=GSheetsConnection)

if 'index' not in st.session_state:
    st.session_state.index = 0

# --- 2. SMART PARSER & COLUMN GUARD ---
def get_col(df, keywords):
    for col in df.columns:
        if any(key.lower() in str(col).lower() for key in keywords):
            return col
    return None

def ensure_columns(df, required_cols):
    """Adds missing columns to the dataframe if they don't exist."""
    for col in required_cols:
        if col not in df.columns:
            df[col] = ""
    return df

# --- 3. UTILITY FUNCTIONS ---
def clean_phone(val):
    if pd.isna(val) or val == "": return ""
    return re.sub(r'\D', '', str(val))

def safe_append_activity(new_entry):
    """Safely appends to Activity_Log without recreation errors."""
    try:
        current_log = conn.read(worksheet="Activity_Log", ttl=0).copy()
        updated_log = pd.concat([current_log, new_entry], ignore_index=True)
        conn.update(worksheet="Activity_Log", data=updated_log)
    except:
        conn.create(worksheet="Activity_Log", data=new_entry)
    st.toast(f"✅ Activity Logged: {new_entry['Outcome'].iloc[0]}")

# --- 4. DATA LOAD ---
try:
    df = conn.read(ttl=0).copy()
    df = ensure_columns(df, ['Rating', 'Last Touch', 'Notes'])
    for c in df.columns: df[c] = df[c].astype(object)
    
    try:
        activity_log = conn.read(worksheet="Activity_Log", ttl=0).copy()
    except:
        activity_log = pd.DataFrame(columns=["Timestamp", "Lead Name", "Outcome", "Rating", "Note", "User"])
except Exception as e:
    st.error(f"Sync Error: {e}")
    st.stop()

# Identify columns
col_first = get_col(df, ["first", "name"])
col_last = get_col(df, ["last"])
col_comp = get_col(df, ["company", "account"])
col_phone = get_col(df, ["phone", "mobile", "tel"])
col_email = get_col(df, ["email", "@"])
col_notes = get_col(df, ["notes", "comment", "history"])
col_li_person = get_col(df, ["linkedin", "profile"])

with st.sidebar:
    st.title("MASTER OF OPS")
    mode = st.radio("Navigation", ["Dialer", "Dashboard"])
    st.divider()
    if st.button("🏠 HOME (Go to Lead 1)"):
        st.session_state.index = 0
        st.rerun()
    
    # Progress Calculation
    total_leads = len(df)
    remaining = total_leads - st.session_state.index
    st.metric("Leads Remaining", remaining)
    st.progress(st.session_state.index / total_leads if total_leads > 0 else 0)

# --- MODE: DIALER ---
if mode == "Dialer":
    if st.session_state.index >= len(df):
        st.success("🏁 All leads processed!")
        if st.button("Return to Start"):
            st.session_state.index = 0
            st.rerun()
        st.stop()

    lead = df.iloc[st.session_state.index]
    orig_idx = lead.name
    full_name = f"{lead.get(col_first, '')} {lead.get(col_last, '')}"
    
    st.title(f"📞 {full_name}")
    st.caption(f"Lead {st.session_state.index + 1} of {len(df)}")

    # History Expander
    past_interactions = activity_log[activity_log['Lead Name'] == full_name]
    if not past_interactions.empty:
        with st.expander("🕒 PREVIOUS CONTACT HISTORY", expanded=True):
            st.table(past_interactions[['Timestamp', 'Outcome', 'Note']].tail(3))

    col_l, col_r = st.columns([1, 1])

    with col_l:
        st.markdown("### ⚡ Execution")
        phone_raw = lead.get(col_phone, '')
        if phone_raw:
            st.link_button(f"📲 CALL: {phone_raw}", f"tel:{clean_phone(phone_raw)}", use_container_width=True, type="primary")
        
        contact_made = st.checkbox("👤 CONTACT MADE")
        rating = st.selectbox("Lead Rating", ["Cold", "Warm", "Hot"], index=1)
        new_note = st.text_area("New Call Note", placeholder="Enter notes here...")

    with col_r:
        st.markdown("### 🧠 Lead Intel")
        st.write(f"🌐 **Email:** {lead.get(col_email, 'N/A')}")
        st.write(f"👤 **LinkedIn:** [Profile]({lead.get(col_li_person, '#')})")
        st.info(f"📋 **System Notes History:**\n\n {lead.get(col_notes, 'No history found.')}")

    # --- LOGGING ACTIONS ---
    st.divider()
    c1, c2, c3, c4 = st.columns(4)
    
    def complete_action(outcome_text, move_next=True):
        timestamp = datetime.now().strftime("%m/%d %H:%M")
        old_notes = str(lead.get(col_notes, "")) if not pd.isna(lead.get(col_notes)) else ""
        combined = f"[{timestamp}]: {new_note} | {old_notes}"
        
        # Update Main Sheet
        df.at[orig_idx, col_notes] = combined
        df.at[orig_idx, 'Rating'] = rating
        df.at[orig_idx, 'Last Touch'] = datetime.now().strftime("%Y-%m-%d")
        conn.update(data=df)
        
        # Log Activity
        new_entry = pd.DataFrame([{"Timestamp": datetime.now(), "Lead Name": full_name, "Outcome": outcome_text, "Note": new_note, "Rating": rating, "User": "Alfonso"}])
        safe_append_activity(new_entry)
        
        if move_next:
            st.session_state.index += 1
            st.rerun()

    with c1:
        if st.button("✅ LOG & NEXT", type="primary", use_container_width=True):
            complete_action("Contact Made" if contact_made else "Outbound Call")

    with c2:
        cal_url = f"https://www.google.com/calendar/render?action=TEMPLATE&text={urllib.parse.quote('Follow up: ' + full_name)}"
        if st.button("📅 APPOINTMENT", use_container_width=True):
            st.markdown(f'<a href="{cal_url}" target="_blank">Confirm in Calendar</a>', unsafe_allow_html=True)
            complete_action("Appointment Scheduled")

    with c3:
        if st.button("💸 CLOSED DEAL", use_container_width=True):
            st.balloons()
            complete_action("Closed Deal")

    with c4:
        if st.button("⏭️ SKIP", use_container_width=True):
            st.session_state.index += 1
            st.rerun()

# --- MODE: DASHBOARD ---
elif mode == "Dashboard":
    st.title("📈 Performance Stats")
    if not activity_log.empty:
        # FIX: errors='coerce' prevents the ValueError if timestamps are messy
        activity_log['Timestamp'] = pd.to_datetime(activity_log['Timestamp'], errors='coerce')
        activity_log = activity_log.dropna(subset=['Timestamp'])
        
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Total Dials", len(activity_log))
        k2.metric("Contacts", len(activity_log[activity_log['Outcome'] == 'Contact Made']))
        k3.metric("Appointments", len(activity_log[activity_log['Outcome'] == 'Appointment Scheduled']))
        k4.metric("Closed Deals", len(activity_log[activity_log['Outcome'] == 'Closed Deal']))
        
        st.divider()
        st.subheader("Daily Execution Trend")
        daily = activity_log.set_index('Timestamp').resample('D').count()['Lead Name']
        st.line_chart(daily)
        st.dataframe(activity_log.sort_values('Timestamp', ascending=False), use_container_width=True)
    else:
        st.info("No activity found in Activity_Log.")
