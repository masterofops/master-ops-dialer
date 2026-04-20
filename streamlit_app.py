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

for col in df.columns:
            if "linkedin" in col.lower() or "profile" in col.lower():
                url = lead.get(col, '')
                if pd.notna(url) and str(url).startswith('http'):
                    st.write(f"👤 **{col}:** [View Profile]({url})")

for col in df.columns:
            if any(k in col.lower() for k in ["phone", "tel", "mobile", "celular"]):
                p_val = lead.get(col, '')
                if pd.notna(p_val) and str(p_val).strip() != '':
                    st.link_button(f"📲 {col}: {p_val}", f"tel:{re.sub(r'\D', '', str(p_val))}", use_container_width=True)

# --- SIDEBAR ---
with st.sidebar:
    st.title("MASTER OF OPS")
    mode = st.radio("Navigation", ["Dialer", "Dashboard", "Lead Manager"])
    
    # Session Timer
    elapsed_seconds = time.time() - st.session_state.start_time
    hours, minutes = int(elapsed_seconds // 3600), int((elapsed_seconds % 3600) // 60)
    st.metric("Work Session Duration", f"{hours}h {minutes}m")

    st.divider()
    dial_dir = st.radio("Dialing Direction", ["Top to Bottom", "Bottom to Top"])

    # Jump & Navigation
    list_total = len(df) if len(df) > 0 else 1
    safe_index = max(0, min(st.session_state.index, list_total - 1))
    
    new_start = st.number_input("Current Position:", min_value=1, max_value=list_total, value=safe_index + 1)
    if st.button("Jump to Lead"):
        st.session_state.index = int(new_start) - 1
        st.rerun()

    c_home, c_end = st.columns(2)
    if c_home.button("🏠 HOME"):
        st.session_state.index = 0
        st.rerun()
    if c_end.button("🏁 END"):
        st.session_state.index = len(df) - 1
        st.rerun()

    st.divider()
    st.subheader("📤 Lead Enrichment")
    uploaded_file = st.file_uploader("Upload CSV", type=["csv"])
    if uploaded_file:
        try:
            new_data = pd.read_csv(uploaded_file, encoding='latin1', on_bad_lines='skip', low_memory=False)
            if st.button("Append & Enrich Database"):
                updated_df = pd.concat([df, new_data], axis=0, ignore_index=True)
                if col_email in updated_df.columns:
                    updated_df = updated_df.drop_duplicates(subset=[col_email], keep='first')
                conn.update(data=updated_df)
                st.success(f"Database Expanded! New Total: {len(updated_df)}")
                st.cache_data.clear()
                st.rerun()
        except Exception as e:
            st.error(f"Upload Error: {e}")
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

st.write("---")
    cx, cy = st.columns(2)
    if cx.button("🔵 Log LinkedIn Message", use_container_width=True):
        log_action("LinkedIn Sent", step=0)
    if cy.button("📧 Log Manual Email", use_container_width=True):
        log_action("Email Sent", step=0)
    
    st.divider()
    c1, c2, c3, c4, c5 = st.columns(5)
  with c1:
        if st.button("⬅️ PREVIOUS", use_container_width=True):
            if st.session_state.index > 0:
                st.session_state.index -= 1
                st.rerun()
            else:
                st.toast("⚠️ You are at the first lead.")
    with c2:
        if st.button("✅ LOG & NEXT", type="primary", use_container_width=True):
            log_action("Contact Made" if contact_made else "Outbound Call")
    with c3:
        # Calendar logic
        cal_url = f"https://www.google.com/calendar/render?action=TEMPLATE&text={urllib.parse.quote('Appt: ' + full_name)}"
        if st.button("📅 APPOINTMENT", use_container_width=True):
            log_action("Appointment Scheduled", step=0) # Log logic stays the same
            st.markdown(f'<meta http-equiv="refresh" content="0;URL=\'{cal_url}\' \">', unsafe_allow_html=True)
    with c4:
        if st.button("💸 CLOSED", use_container_width=True):
            st.balloons()
            log_action("Closed Deal")
   with c5:
        # Email logic
        email_addr = lead.get(col_email, '')
        if st.button("✉️ EMAIL", use_container_width=True):
            # Also log that an email was sent
            log_action("Email Sent", step=0)
            st.markdown(f'<meta http-equiv="refresh" content="0;URL=\'mailto:{email_addr}\' \">', unsafe_allow_html=True)

# --- MODE: DASHBOARD ---
elif mode == "Dashboard":
    st.title("📊 Master of Ops Execution Dashboard")
    if not activity_log.empty:
        activity_log['Timestamp'] = pd.to_datetime(activity_log['Timestamp'], errors='coerce')
        
        # Date Range Picker
        c_date1, c_date2 = st.columns(2)
        start_date = c_date1.date_input("From", datetime.now() - timedelta(days=30))
        end_date = c_date2.date_input("To", datetime.now())
        
        # Filter Data
        mask = (activity_log['Timestamp'].dt.date >= start_date) & (activity_log['Timestamp'].dt.date <= end_date)
        f_log = activity_log.loc[mask]

        # Calculation Engine
        dials = len(f_log)
        contacts = len(f_log[f_log['Outcome'].str.contains('Contact', na=False)])
        appts = len(f_log[f_log['Outcome'].str.contains('Appt', na=False)])
        closed = len(f_log[f_log['Outcome'].str.contains('Closed', na=False)])
        
        # Ratios
        con_to_appt = (appts / contacts * 100) if contacts > 0 else 0
        dial_to_close = (closed / dials * 100) if dials > 0 else 0

        # KPI Tiles
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Dials", dials)
        k2.metric("Contact %", f"{(contacts/dials*100 if dials>0 else 0):.1f}%")
        k3.metric("Appts", appts)
        k4.metric("Deals", closed)

        st.divider()
        st.subheader("Performance Ratios")
        r1, r2 = st.columns(2)
        r1.metric("Contact to Appointment", f"{con_to_appt:.1f}%")
        r2.metric("Dial to Close", f"{dial_to_close:.1f}%")

        # Graph Fix
        st.subheader("Daily Activity Volume")
        chart_data = f_log.set_index('Timestamp').resample('D').count()['Lead Name']
        st.area_chart(chart_data)

elif mode == "Lead Manager":
    st.title("🗂️ Search & Filter Database")
    search_query = st.text_input("Filter by Name, Company, or Status...")
    
    if search_query:
        filtered_df = df[df.astype(str).apply(lambda x: x.str.contains(search_query, case=False)).any(axis=1)]
    else:
        filtered_df = df
        
    st.write(f"Showing {len(filtered_df)} leads")
    st.dataframe(filtered_df, use_container_width=True)
