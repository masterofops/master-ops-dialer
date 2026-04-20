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

# --- 2. SMART PARSER (Detects columns by content, not just names) ---
def get_col(df, keywords, default_val="N/A"):
    for col in df.columns:
        if any(key.lower() in col.lower() for key in keywords):
            return col
    return None

# --- 3. UTILITY FUNCTIONS ---
def clean_phone(val):
    if pd.isna(val) or val == "": return ""
    return re.sub(r'\D', '', str(val))

def safe_append_activity(log_df, new_entry):
    """Appends to the Activity_Log without trying to recreate the sheet."""
    updated_log = pd.concat([log_df, new_entry], ignore_index=True)
    conn.update(worksheet="Activity_Log", data=updated_log)
    st.toast("✅ Activity Tracked")

# --- 4. DATA LOAD ---
try:
    df = conn.read(ttl=0).copy()
    # Force columns to object to prevent TypeErrors
    for c in df.columns: df[c] = df[c].astype(object)
    
    # Load Activity Log for history and dashboard
    try:
        activity_log = conn.read(worksheet="Activity_Log", ttl=0).copy()
    except:
        # Create empty log if it doesn't exist (only happens once)
        activity_log = pd.DataFrame(columns=["Timestamp", "Lead Name", "Outcome", "Rating", "Note", "User"])
except Exception as e:
    st.error(f"Sync Error: {e}")
    st.stop()

# Identify columns dynamically
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
    if st.button("Reset to Lead 1"):
        st.session_state.index = 0
        st.rerun()

# --- MODE: DIALER ---
if mode == "Dialer":
    lead = df.iloc[st.session_state.index]
    orig_idx = lead.name
    full_name = f"{lead.get(col_first, '')} {lead.get(col_last, '')}"
    
    st.title(f"📞 {full_name}")
    st.subheader(f"{lead.get(col_comp, 'N/A')}")

    # Historical Intel Section
    past_interactions = activity_log[activity_log['Lead Name'] == full_name]
    if not past_interactions.empty:
        with st.expander("🕒 PREVIOUS CONTACT HISTORY", expanded=False):
            st.table(past_interactions[['Timestamp', 'Outcome', 'Note']].tail(5))

    col_l, col_r = st.columns([1, 1])

    with col_l:
        st.markdown("### ⚡ Execution")
        phone_raw = lead.get(col_phone, '')
        if phone_raw:
            st.link_button(f"📲 CALL: {phone_raw}", f"tel:{clean_phone(phone_raw)}", use_container_width=True, type="primary")
        
        contact_made = st.checkbox("👤 CONTACT MADE")
        rating = st.selectbox("Lead Rating", ["Cold", "Warm", "Hot"], index=1)
        new_note = st.text_area("New Call Note", placeholder="Add to history...")

    with col_r:
        st.markdown("### 🧠 Lead Intel")
        st.write(f"🌐 **Email:** {lead.get(col_email, 'N/A')}")
        st.write(f"👤 **LinkedIn:** [Profile]({lead.get(col_li_person, '#')})")
        st.info(f"📋 **System Notes History:**\n\n {lead.get(col_notes, 'No history found.')}")

    # Log Actions
    st.divider()
    c1, c2, c3, c4 = st.columns(4)
    
    with c1:
        if st.button("✅ LOG & NEXT", type="primary", use_container_width=True):
            outcome = "Contact Made" if contact_made else "Outbound Call"
            # Append notes logic: [Date]: Note | Old Notes
            timestamp = datetime.now().strftime("%m/%d %H:%M")
            combined_notes = f"[{timestamp}]: {new_note} | {lead.get(col_notes, '')}"
            
            df.at[orig_idx, col_notes] = combined_notes
            df.at[orig_idx, 'Rating'] = rating
            df.at[orig_idx, 'Last Touch'] = datetime.now().strftime("%Y-%m-%d")
            
            # Log to Activity
            new_entry = pd.DataFrame([{"Timestamp": datetime.now(), "Lead Name": full_name, "Outcome": outcome, "Note": new_note, "Rating": rating, "User": "Alfonso"}])
            safe_append_activity(activity_log, new_entry)
            conn.update(data=df)
            st.session_state.index += 1
            st.rerun()

    with c2:
        cal_url = f"https://www.google.com/calendar/render?action=TEMPLATE&text={urllib.parse.quote('Follow up: ' + full_name)}"
        st.link_button("📅 APPOINTMENT", cal_url, use_container_width=True)

    with c3:
        if st.button("💸 CLOSED DEAL", use_container_width=True):
            new_entry = pd.DataFrame([{"Timestamp": datetime.now(), "Lead Name": full_name, "Outcome": "Closed Deal", "Note": new_note, "Rating": "Hot", "User": "Alfonso"}])
            safe_append_activity(activity_log, new_entry)
            st.balloons()

    with c4:
        if st.button("⏭️ SKIP", use_container_width=True):
            st.session_state.index += 1
            st.rerun()

# --- MODE: DASHBOARD ---
elif mode == "Dashboard":
    st.title("📈 Performance Stats")
    if not activity_log.empty:
        activity_log['Timestamp'] = pd.to_datetime(activity_log['Timestamp'])
        
        k1, k2, k3 = st.columns(3)
        k1.metric("Total Dials", len(activity_log))
        k2.metric("Contacts", len(activity_log[activity_log['Outcome'] == 'Contact Made']))
        k3.metric("Closed Deals", len(activity_log[activity_log['Outcome'] == 'Closed Deal']))
        
        st.divider()
        st.subheader("Daily Activity")
        daily = activity_log.set_index('Timestamp').resample('D').count()['Lead Name']
        st.line_chart(daily)
        st.dataframe(activity_log.sort_values('Timestamp', ascending=False), use_container_width=True)
    else:
        st.info("No activity found in Activity_Log.")
