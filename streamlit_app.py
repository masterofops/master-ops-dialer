import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import re
import google.generativeai as genai
from datetime import datetime, timedelta
import urllib.parse
import time

# --- PAGE CONFIG ---
st.set_page_config(page_title="Master of Ops Dialer", layout="wide")

# --- 1. CONNECTION & SESSION STATE ---
conn = st.connection("gsheets", type=GSheetsConnection)

if 'index' not in st.session_state:
    st.session_state.index = 0
if 'start_time' not in st.session_state:
    st.session_state.start_time = time.time()

# --- 2. UTILITIES ---
def get_col(df, keywords):
    for col in df.columns:
        if any(key.lower() in str(col).lower() for key in keywords):
            return col
    return None

def clean_phone(val):
    if pd.isna(val) or val == "": return ""
    return re.sub(r'\D', '', str(val))

# --- 3. DATA LOAD (With Quota Protection) ---
try:
    df = conn.read(ttl=300).copy()
    for c in df.columns: df[c] = df[c].astype(object)
    
    try:
        activity_log = conn.read(worksheet="Activity_Log", ttl=300).copy()
    except:
        activity_log = pd.DataFrame(columns=["Timestamp", "Lead Name", "Outcome", "Rating", "Note", "User"])
except Exception as e:
    st.error(f"Sync Error: {e}")
    st.stop()

# Mapping
col_first = get_col(df, ["first", "name"])
col_last = get_col(df, ["last"])
col_comp = get_col(df, ["company", "account"])
col_phone = get_col(df, ["phone", "mobile", "tel"])
col_email = get_col(df, ["email", "@"])
col_notes = get_col(df, ["notes", "comment", "history"])
col_li_person = get_col(df, ["linkedin", "profile"])

# --- SIDEBAR ---
with st.sidebar:
    st.title("MASTER OF OPS")
    mode = st.radio("Navigation", ["Dialer", "Dashboard", "Lead Manager"])
    
    st.divider()
    # TIME TRACKER
    elapsed = time.time() - st.session_state.start_time
    st.metric("Session Time", f"{int(elapsed // 3600)}h {int((elapsed % 3600) // 60)}m")
    
    if st.button("🔄 Sync Sheets"):
        st.cache_data.clear()
        st.rerun()

    st.subheader("📤 Upload Leads")
    uploaded_file = st.file_uploader("Upload CSV", type=["csv"])
    if uploaded_file:
        try:
            new_leads = pd.read_csv(uploaded_file)
            if st.button("Confirm Upload"):
                updated_df = pd.concat([df, new_leads], ignore_index=True)
                conn.update(data=updated_df)
                st.success("Leads Added!")
                st.rerun()
        except Exception as e:
            st.error(f"Upload failed: {e}")

    st.divider()
    if st.button("🏠 HOME (Lead 1)"):
        st.session_state.index = 0
        st.rerun()
    
    st.markdown(f"🔗 [Open Master Sheet](https://docs.google.com/spreadsheets/d/1YWt8gtPMQHCZQO91tl_I0iv592Q_yhPBR1SUdbIQP6g/)")

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

    col_l, col_r = st.columns([1, 1])

    with col_l:
        st.markdown("### ⚡ Execution")
        phone_raw = lead.get(col_phone, '')
        if phone_raw:
            st.link_button(f"📲 CALL: {phone_raw}", f"tel:{clean_phone(phone_raw)}", use_container_width=True, type="primary")
        
        contact_made = st.checkbox("👤 CONTACT MADE")
        rating = st.selectbox("Lead Rating", ["Cold", "Warm", "Hot"], index=1)
        # Unique key per index ensures the box clears on move
        new_note = st.text_area("New Call Note", key=f"note_input_{st.session_state.index}")

    with col_r:
        st.markdown("### 🧠 Lead Intel")
        st.write(f"🌐 **Email:** {lead.get(col_email, 'N/A')}")
        st.write(f"👤 **LinkedIn:** [Profile]({lead.get(col_li_person, '#')})")
        st.info(f"📋 **History:**\n\n {lead.get(col_notes, 'No history.')}")

    def log_action(outcome, move_val=1):
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
        
        st.session_state.index += move_val
        st.rerun()

    st.divider()
    c1, c2, c3, c4, c5 = st.columns(5)
    
    with c1:
        if st.button("⬅️ PREVIOUS", use_container_width=True):
            if st.session_state.index > 0:
                st.session_state.index -= 1
                st.rerun()

    with c2:
        if st.button("✅ LOG & NEXT", type="primary", use_container_width=True):
            log_action("Contact Made" if contact_made else "Outbound Call")

    with c3:
        cal_url = f"https://www.google.com/calendar/render?action=TEMPLATE&text={urllib.parse.quote('Follow up: ' + full_name)}"
        if st.button("📅 APPOINTMENT", use_container_width=True):
            log_action("Appointment Scheduled")
            st.markdown(f'<meta http-equiv="refresh" content="0;URL=\'{cal_url}\' \">', unsafe_allow_html=True)

    with c4:
        if st.button("💸 CLOSED DEAL", use_container_width=True):
            st.balloons()
            log_action("Closed Deal")

    with c5:
        email_addr = lead.get(col_email, '')
        if st.button("✉️ EMAIL", use_container_width=True):
            subj = urllib.parse.quote("Master of Ops - Follow up")
            st.markdown(f'<meta http-equiv="refresh" content="0;URL=\'mailto:{email_addr}?subject={subj}\' \">', unsafe_allow_html=True)

# --- MODE: DASHBOARD ---
elif mode == "Dashboard":
    st.title("📈 Performance Stats")
    if not activity_log.empty:
        activity_log['Timestamp'] = pd.to_datetime(activity_log['Timestamp'], errors='coerce')
        
        # Date Filter
        start_date = st.date_input("Start Date", value=datetime.now() - timedelta(days=7))
        end_date = st.date_input("End Date", value=datetime.now())
        mask = (activity_log['Timestamp'].dt.date >= start_date) & (activity_log['Timestamp'].dt.date <= end_date)
        filtered_log = activity_log.loc[mask]

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Dials in Range", len(filtered_log))
        k2.metric("Contacts", len(filtered_log[filtered_log['Outcome'] == 'Contact Made']))
        k3.metric("Appointments", len(filtered_log[filtered_log['Outcome'] == 'Appointment Scheduled']))
        k4.metric("Closed Deals", len(filtered_log[filtered_log['Outcome'] == 'Closed Deal']))
        
        st.subheader("Daily Execution Trend")
        if not filtered_log.empty:
            chart_data = filtered_log.set_index('Timestamp').resample('D').count()['Lead Name']
            st.area_chart(chart_data)
        
        st.subheader("Activity History")
        st.dataframe(filtered_log.sort_values('Timestamp', ascending=False), use_container_width=True)

# --- MODE: LEAD MANAGER ---
elif mode == "Lead Manager":
    st.title("🗂️ Lead Manager")
    search = st.text_input("Search Leads (Name, Company, or Email)")
    if search:
        display_df = df[df.astype(str).apply(lambda x: x.str.contains(search, case=False)).any(axis=1)]
    else:
        display_df = df
    st.dataframe(display_df, use_container_width=True)
