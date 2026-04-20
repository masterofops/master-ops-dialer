import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import re
from datetime import datetime, timedelta
import urllib.parse
import time

# --- PAGE CONFIG ---
st.set_page_config(page_title="Master of Ops Dialer", layout="wide")

# --- 1. CONNECTION ---
conn = st.connection("gsheets", type=GSheetsConnection)

if 'index' not in st.session_state:
    st.session_state.index = 0
if 'start_time' not in st.session_state:
    st.session_state.start_time = time.time()

# --- 2. SMART PARSER (Expanded for Corporate/Personal) ---
def get_cols(df, keywords):
    found = [col for col in df.columns if any(key.lower() in str(col).lower() for key in keywords)]
    return found if found else []

# --- 3. DATA LOAD ---
try:
    df = conn.read(ttl=30).copy() # Lowered TTL for better responsiveness
    for c in df.columns: df[c] = df[c].astype(object)
    
    try:
        activity_log = conn.read(worksheet="Activity_Log", ttl=30).copy()
    except:
        activity_log = pd.DataFrame(columns=["Timestamp", "Lead Name", "Outcome", "Rating", "Note", "User"])
except Exception as e:
    st.error(f"Sync Error: {e}")
    st.stop()

# Re-mapping with higher sensitivity
col_first = get_cols(df, ["first", "name", "nombre"])[0] if get_cols(df, ["first", "name"]) else None
col_last = get_cols(df, ["last", "apellido"])[0] if get_cols(df, ["last", "apellido"]) else None
col_comp = get_cols(df, ["company", "account", "empresa"])[0] if get_cols(df, ["company", "account"]) else None
phone_cols = get_cols(df, ["phone", "mobile", "tel", "celular"])
li_cols = get_cols(df, ["linkedin", "profile", "li-"])
col_email = get_cols(df, ["email", "@", "correo"])[0] if get_cols(df, ["email", "@"]) else None
col_notes = get_cols(df, ["notes", "comment", "history", "notas"])[0] if get_cols(df, ["notes", "comment"]) else "Notes"

# --- SIDEBAR ---
with st.sidebar:
    st.title("MASTER OF OPS")
    mode = st.radio("Navigation", ["Dialer", "Dashboard", "Lead Manager"])
    
    st.divider()
    dial_dir = st.radio("Dialing Direction", ["Top to Bottom", "Bottom to Top"])
    
    st.divider()
    # JUMP LOGIC
    new_start = st.number_input("Current Position:", min_value=1, max_value=len(df), value=st.session_state.index + 1)
    if st.button("Jump to Lead"):
        st.session_state.index = int(new_start) - 1
        st.rerun()

    st.subheader("📤 Lead Enrichment")
    uploaded_file = st.file_uploader("Upload CSV or Excel", type=["csv", "xlsx"])
    if uploaded_file:
        try:
            new_data = pd.read_csv(uploaded_file, encoding='latin1') if uploaded_file.name.endswith('csv') else pd.read_excel(uploaded_file)
            if st.button("Append & Enrich Database"):
                combined_df = pd.concat([df, new_data], ignore_index=True).drop_duplicates(subset=[col_email] if col_email else None, keep='first')
                conn.update(data=combined_df)
                st.success("Database Updated!")
                st.rerun()
        except Exception as e:
            st.error(f"Upload Error: {e}")

    st.divider()
    c_home, c_end = st.columns(2)
    if c_home.button("🏠 HOME"):
        st.session_state.index = 0
        st.rerun()
    if c_end.button("🏁 END"):
        st.session_state.index = len(df) - 1
        st.rerun()

# --- MODE: DIALER ---
if mode == "Dialer":
    if st.session_state.index >= len(df) or st.session_state.index < 0:
        st.session_state.index = 0

    lead = df.iloc[st.session_state.index]
    orig_idx = lead.name
    full_name = f"{lead.get(col_first, '')} {lead.get(col_last, '')}"
    
    st.title(f"📞 {full_name}")
    st.subheader(f"{lead.get(col_comp, 'N/A')}")

    # RESTORED: Full Activity Log History for this specific lead
    past = activity_log[activity_log['Lead Name'] == full_name]
    if not past.empty:
        with st.expander("🕒 PREVIOUS INTERACTION HISTORY", expanded=True):
            st.dataframe(past[['Timestamp', 'Outcome', 'Note', 'Rating']].sort_values('Timestamp', ascending=False), use_container_width=True)

    col_l, col_r = st.columns([1, 1])

    with col_l:
        st.markdown("### ⚡ Call Actions")
        for p_col in phone_cols:
            p_val = lead.get(p_col, '')
            if pd.notna(p_val) and str(p_val).strip() != '':
                st.link_button(f"📲 {p_col}: {p_val}", f"tel:{re.sub(r'\D', '', str(p_val))}", use_container_width=True)
        
        contact_made = st.checkbox("👤 CONTACT MADE")
        rating = st.selectbox("Rating", ["Cold", "Warm", "Hot"], index=1)
        new_note = st.text_area("Live Call Notes", key=f"note_{st.session_state.index}")

    with col_r:
        st.markdown("### 🧠 Intelligence")
        st.write(f"🌐 **Email:** {lead.get(col_email, 'N/A')}")
        for l_col in li_cols:
            l_val = lead.get(l_col, '')
            if pd.notna(l_val) and str(l_val).startswith('http'):
                st.write(f"👤 **{l_col}:** [View Profile]({l_val})")
        
        st.info(f"📋 **Static Sheet Notes:**\n\n {lead.get(col_notes, 'None')}")

    def log_action(outcome, step=1):
        move = step if dial_dir == "Top to Bottom" else -step
        ts = datetime.now().strftime("%m/%d %H:%M")
        old = str(lead.get(col_notes, "")) if not pd.isna(lead.get(col_notes)) else ""
        
        df.at[orig_idx, col_notes] = f"[{ts}]: {new_note} | {old}"
        df.at[orig_idx, 'Rating'] = rating
        df.at[orig_idx, 'Last Touch'] = datetime.now().strftime("%Y-%m-%d")
        
        conn.update(data=df)
        entry = pd.DataFrame([{"Timestamp": datetime.now(), "Lead Name": full_name, "Outcome": outcome, "Note": new_note, "Rating": rating}])
        
        try:
            current_log = conn.read(worksheet="Activity_Log", ttl=0).copy()
            conn.update(worksheet="Activity_Log", data=pd.concat([current_log, entry], ignore_index=True))
        except:
            conn.create(worksheet="Activity_Log", data=entry)
        
        st.session_state.index += move
        st.rerun()

    st.divider()
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        if st.button("⬅️ PREVIOUS", use_container_width=True):
            st.session_state.index -= 1 if dial_dir == "Top to Bottom" else -1
            st.rerun()
    with c2:
        if st.button("✅ LOG & NEXT", type="primary", use_container_width=True):
            log_action("Contact Made" if contact_made else "Outbound Call")
    with c3:
        cal_url = f"https://www.google.com/calendar/render?action=TEMPLATE&text={urllib.parse.quote('Appt: ' + full_name)}"
        if st.button("📅 APPOINTMENT", use_container_width=True):
            log_action("Appointment Scheduled", step=0)
            st.markdown(f'<meta http-equiv="refresh" content="0;URL=\'{cal_url}\' \">', unsafe_allow_html=True)
    with c4:
        if st.button("💸 CLOSED", use_container_width=True):
            st.balloons()
            log_action("Closed Deal")
    with c5:
        if st.button("⏭️ SKIP", use_container_width=True):
            st.session_state.index += 1 if dial_dir == "Top to Bottom" else -1
            st.rerun()

# --- MODE: DASHBOARD ---
elif mode == "Dashboard":
    st.title("📈 Manufacturing Ops KPIs")
    if not activity_log.empty:
        activity_log['Timestamp'] = pd.to_datetime(activity_log['Timestamp'], errors='coerce')
        
        # RESTORED: KPI Summary
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Total Dials", len(activity_log))
        k2.metric("Contacts", len(activity_log[activity_log['Outcome'].str.contains('Contact', na=False)]))
        k3.metric("Appts", len(activity_log[activity_log['Outcome'].str.contains('Appt', na=False)]))
        k4.metric("Closed", len(activity_log[activity_log['Outcome'].str.contains('Closed', na=False)]))
        
        st.divider()
        st.subheader("Daily Volume")
        chart_data = activity_log.set_index('Timestamp').resample('D').count()['Lead Name']
        st.area_chart(chart_data)
        st.dataframe(activity_log.sort_values('Timestamp', ascending=False), use_container_width=True)

elif mode == "Lead Manager":
    st.title("🗂️ Database Manager")
    st.dataframe(df, use_container_width=True)
