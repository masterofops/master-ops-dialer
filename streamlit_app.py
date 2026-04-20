import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import re
from datetime import datetime
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

# --- 2. SMART PARSER (Aggressive Detection) ---
def get_col(df, keywords):
    for col in df.columns:
        if any(key.lower() in str(col).lower() for key in keywords):
            return col
    return None

# --- 3. DATA LOAD (Quota Protected) ---
try:
    # ttl=60 helps avoid the 429 "Quota Exceeded" error by not pinging Google every second
    df = conn.read(ttl=60).copy()
    for c in df.columns: df[c] = df[c].astype(object)
    
    try:
        activity_log = conn.read(worksheet="Activity_Log", ttl=60).copy()
    except:
        activity_log = pd.DataFrame(columns=["Timestamp", "Lead Name", "Outcome", "Rating", "Note", "User"])
except Exception as e:
    st.error(f"Quota/Sync Error: {e}")
    st.stop()

# --- RE-MAPPING COLUMNS (More keywords for better parsing) ---
col_first = get_col(df, ["first", "name", "nombre"])
col_last = get_col(df, ["last", "apellido"])
col_comp = get_col(df, ["company", "account", "empresa"])
col_phone = get_col(df, ["phone", "mobile", "tel", "corporate phone", "personal phone"])
col_email = get_col(df, ["email", "@", "correo"])
col_notes = get_col(df, ["notes", "comment", "history", "notas"])
col_li_person = get_col(df, ["linkedin", "profile", "person linkedin"])

# --- SIDEBAR ---
with st.sidebar:
    st.title("MASTER OF OPS")
    mode = st.radio("Navigation", ["Dialer", "Dashboard", "Lead Manager"])
    
    st.divider()
    # START POSITION SELECTOR
    new_start = st.number_input("Start at Lead #:", min_value=1, max_value=len(df), value=st.session_state.index + 1)
    if st.button("Jump to Lead"):
        st.session_state.index = int(new_start) - 1
        st.rerun()

    st.divider()
    # UPLOADER (Fixed for Encoding and Appending)
    st.subheader("📤 Add to List")
    uploaded_file = st.file_uploader("Upload CSV", type=["csv"])
    if uploaded_file:
        try:
            # latin1 handles special characters that 'utf-8' crashes on
            new_data = pd.read_csv(uploaded_file, encoding='latin1')
            if st.button("Enrich & Append List"):
                # Append logic
                combined_df = pd.concat([df, new_data], ignore_index=True).drop_duplicates(subset=[col_email] if col_email else None, keep='first')
                conn.update(data=combined_df)
                st.success(f"Added {len(new_data)} contacts without deleting previous.")
                st.rerun()
        except Exception as e:
            st.error(f"Upload failed: {e}")

    st.divider()
    if st.button("🏠 RESET TO 1"):
        st.session_state.index = 0
        st.rerun()
    
    st.markdown(f"🔗 [Open Google Sheet](https://docs.google.com/spreadsheets/d/1YWt8gtPMQHCZQO91tl_I0iv592Q_yhPBR1SUdbIQP6g/)")

# --- MODE: DIALER ---
if mode == "Dialer":
    if st.session_state.index >= len(df) or st.session_state.index < 0:
        st.session_state.index = 0 # Safety reset

    lead = df.iloc[st.session_state.index]
    orig_idx = lead.name
    full_name = f"{lead.get(col_first, '')} {lead.get(col_last, '')}"
    
    st.title(f"📞 {full_name}")
    st.caption(f"Lead {st.session_state.index + 1} of {len(df)}")

    col_l, col_r = st.columns([1, 1])

    with col_l:
        st.markdown("### ⚡ Execution")
        phone_raw = lead.get(col_phone, '')
        if phone_raw:
            st.link_button(f"📲 CALL: {phone_raw}", f"tel:{re.sub(r'\D', '', str(phone_raw))}", use_container_width=True, type="primary")
        else:
            st.warning("No phone detected in this column.")
        
        contact_made = st.checkbox("👤 CONTACT MADE")
        rating = st.selectbox("Lead Rating", ["Cold", "Warm", "Hot"], index=1)
        # Unique key prevents note carry-over
        new_note = st.text_area("New Call Note", key=f"note_{st.session_state.index}")

    with col_r:
        st.markdown("### 🧠 Lead Intel")
        st.write(f"🌐 **Email:** {lead.get(col_email, 'N/A')}")
        st.write(f"👤 **LinkedIn:** [Profile]({lead.get(col_li_person, '#')})")
        st.info(f"📋 **Notes History:**\n\n {lead.get(col_notes, 'No history.')}")

    # LOGGING ACTIONS
    def log_action(outcome, move=1):
        ts = datetime.now().strftime("%m/%d %H:%M")
        old = str(lead.get(col_notes, "")) if not pd.isna(lead.get(col_notes)) else ""
        combined = f"[{ts}]: {new_note} | {old}"
        
        df.at[orig_idx, col_notes] = combined
        df.at[orig_idx, 'Rating'] = rating
        df.at[orig_idx, 'Last Touch'] = datetime.now().strftime("%Y-%m-%d")
        
        conn.update(data=df)
        entry = pd.DataFrame([{"Timestamp": datetime.now(), "Lead Name": full_name, "Outcome": outcome, "Note": new_note, "Rating": rating, "User": "Alfonso"}])
        
        try:
            cur_log = conn.read(worksheet="Activity_Log", ttl=0).copy()
            conn.update(worksheet="Activity_Log", data=pd.concat([cur_log, entry], ignore_index=True))
        except:
            conn.create(worksheet="Activity_Log", data=entry)
        
        st.session_state.index += move
        st.rerun()

    st.divider()
    c1, c2, c3, c4, c5 = st.columns(5)
    
    with c1:
        if st.button("⬅️ PREVIOUS", use_container_width=True):
            st.session_state.index -= 1
            st.rerun()

    with c2:
        if st.button("✅ LOG & NEXT", type="primary", use_container_width=True):
            log_action("Contact Made" if contact_made else "Outbound Call")

    with c3:
        cal_url = f"https://www.google.com/calendar/render?action=TEMPLATE&text={urllib.parse.quote('Appt: ' + full_name)}"
        if st.button("📅 APPOINTMENT", use_container_width=True):
            log_action("Appointment Scheduled", move=0) # Log but stay on page for redirect
            st.markdown(f'<meta http-equiv="refresh" content="0;URL=\'{cal_url}\' \">', unsafe_allow_html=True)

    with c4:
        if st.button("💸 CLOSED DEAL", use_container_width=True):
            st.balloons()
            log_action("Closed Deal")

    with c5:
        email_addr = lead.get(col_email, '')
        if st.button("✉️ EMAIL", use_container_width=True):
            st.markdown(f'<meta http-equiv="refresh" content="0;URL=\'mailto:{email_addr}\' \">', unsafe_allow_html=True)

# --- DASHBOARD & LEAD MANAGER (RESTORED PREVIOUS WORKING LOGIC) ---
elif mode == "Dashboard":
    st.title("📈 Performance Stats")
    if not activity_log.empty:
        activity_log['Timestamp'] = pd.to_datetime(activity_log['Timestamp'], errors='coerce')
        st.metric("Total Dials", len(activity_log))
        st.line_chart(activity_log.set_index('Timestamp').resample('D').count()['Lead Name'])
        st.dataframe(activity_log.sort_values('Timestamp', ascending=False), use_container_width=True)

elif mode == "Lead Manager":
    st.title("🗂️ Lead Manager")
    st.dataframe(df, use_container_width=True)
