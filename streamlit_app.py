import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import re
import google.generativeai as genai
from datetime import datetime
import urllib.parse

# --- PAGE CONFIG ---
st.set_page_config(page_title="Master of Ops Dialer", layout="wide")

# --- 1. CONNECTION & SESSION STATE ---
conn = st.connection("gsheets", type=GSheetsConnection)

if 'index' not in st.session_state:
    st.session_state.index = 0
if 'user' not in st.session_state:
    st.session_state.user = "Alfonso"

# --- 2. UTILITY FUNCTIONS ---
def clean_phone_for_dialing(phone_value):
    if pd.isna(phone_value) or phone_value == "":
        return None
    # Remove all non-numeric characters for system dialing
    return re.sub(r'\D', '', str(phone_value))

def commit_activity(lead_name, outcome, note, rating="N/A"):
    # Tracking for all KPIs with timestamps
    log_entry = pd.DataFrame([{
        "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "User": st.session_state.user,
        "Lead Name": lead_name,
        "Outcome": outcome,
        "Rating": rating,
        "Note": note
    }])
    try:
        conn.create(worksheet="Activity_Log", data=log_entry)
        st.toast(f"✅ {outcome} Recorded")
    except Exception as e:
        st.error(f"Logging Error: {e}")

# --- 3. NAVIGATION & DATA LOAD ---
with st.sidebar:
    st.title("⚙️ Master of Ops")
    mode = st.radio("Navigation", ["Dialer", "Dashboard"])
    st.divider()
    
    # User Switching (For your team expansion)
    st.session_state.user = st.selectbox("Current User", ["Alfonso", "Team Member 1", "Team Member 2"])
    
    # Direct access to the source of truth
    sheet_url = "https://docs.google.com/spreadsheets/d/1YWt8gtPMQHCZQO91tl_I0iv592Q_yhPBR1SUdbIQP6g/"
    st.markdown(f"🔗 [Open Master Sheet]({sheet_url})")
    
    if st.button("Reset to Lead 1"):
        st.session_state.index = 0
        st.rerun()

try:
    # Read data and force objects to prevent the TypeError you experienced
    df = conn.read(ttl=0).copy()
    for col in ['Notes', 'Rating', 'Last Touch']:
        if col in df.columns:
            df[col] = df[col].astype(object)
    
    if df.empty:
        st.warning("No leads found in the worksheet.")
        st.stop()
except Exception as e:
    st.error(f"Connection failed: {e}")
    st.stop()

# --- MODE: DIALER ---
if mode == "Dialer":
    if st.session_state.index >= len(df):
        st.success("🏁 All leads processed!")
        st.stop()

    lead = df.iloc[st.session_state.index]
    original_idx = lead.name 
    full_name = f"{lead.get('First Name', 'N/A')} {lead.get('Last Name', 'N/A')}"

    st.title(f"📞 {full_name}")
    st.subheader(f"{lead.get('Title', 'N/A')} | {lead.get('Company Name', 'N/A')}")

    # Action and Intel Columns
    col_l, col_r = st.columns([1, 1])

    with col_l:
        st.markdown("### ⚡ Execution")
        raw_phone = lead.get('Corporate Phone', '')
        dial_link = clean_phone_for_dialing(raw_phone)
        
        if dial_link:
            st.link_button(f"📲 CALL: {raw_phone}", f"tel:{dial_link}", use_container_width=True, type="primary")
        
        # New "Contact" tracking
        contact_made = st.checkbox("👤 CONTACT MADE (Talked to human)")
        
        rating = st.selectbox("Lead Rating", ["Cold", "Warm", "Hot"], index=1)
        notes = st.text_area("Call Notes", placeholder="Input truth from the field...", key=f"notes_{st.session_state.index}")

    with col_r:
        st.markdown("### 🧠 Deep Intel")
        st.write(f"🌐 **Website:** [{lead.get('Website', 'N/A')}]({lead.get('Website', '#')})")
        st.write(f"👤 **Person LI:** [Profile]({lead.get('Person Linkedin Url', '#')})")
        st.write(f"🏢 **Company LI:** [Page]({lead.get('Company Linkedin Url', '#')})")
        
        # KPI relevant metadata
        st.info(f"💰 Revenue: {lead.get('Annual Revenue', '---')} | 👥 Employees: {lead.get('Employees', '---')}")
        st.write(f"🏷️ **Keywords/Industry:** {lead.get('Industry', '---')}")

    # Email System
    st.divider()
    if st.button("🪄 Draft & Open Email", use_container_width=True):
        draft_text = f"Hi {lead.get('First Name')}, reaching out regarding {lead.get('Company Name')}."
        
        # Check for Gemini Key in Secrets
        if "GEMINI_API_KEY" in st.secrets:
            try:
                genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
                model = genai.GenerativeModel('gemini-1.5-flash')
                prompt = f"Write a 3-sentence witty, no-jargon email follow-up for {lead.get('First Name')} at {lead.get('Company Name')}. Notes: {notes}"
                draft_text = model.generate_content(prompt).text
            except:
                pass # Use fallback draft if AI fails
        
        subject = urllib.parse.quote("Master of Ops - Follow up")
        body = urllib.parse.quote(draft_text)
        st.markdown(f'<meta http-equiv="refresh" content="0;URL=\'mailto:{lead.get("Email", "")}?subject={subject}&body={body}\' ">', unsafe_allow_html=True)

    # Outcome Logging Row
    st.divider()
    c1, c2, c3, c4 = st.columns(4)
    
    with c1:
        if st.button("✅ LOG & NEXT", use_container_width=True, type="primary"):
            outcome = "Contact Made" if contact_made else "Outbound Call"
            df.at[original_idx, 'Rating'] = rating
            df.at[original_idx, 'Notes'] = notes
            df.at[original_idx, 'Last Touch'] = datetime.now().strftime("%Y-%m-%d")
            commit_activity(full_name, outcome, notes, rating)
            conn.update(data=df)
            st.session_state.index += 1
            st.rerun()

    with c2:
        if st.button("📅 APPOINTMENT", use_container_width=True):
            commit_activity(full_name, "Appointment Scheduled", notes, rating)
            st.success("Appointment Logged!")

    with c3:
        if st.button("💸 CLOSED DEAL", use_container_width=True):
            commit_activity(full_name, "Closed Deal", notes, rating)
            st.balloons()

    with c4:
        if st.button("⏭️ SKIP LEAD", use_container_width=True):
            st.session_state.index += 1
            st.rerun()

# --- MODE: DASHBOARD ---
elif mode == "Dashboard":
    st.title("📈 Performance Intelligence")
    log_df = conn.read(worksheet="Activity_Log", ttl=0)
    
    if not log_df.empty:
        log_df['Timestamp'] = pd.to_datetime(log_df['Timestamp'])
        
        # Time Filters
        today = datetime.now().date()
        daily_df = log_df[log_df['Timestamp'].dt.date == today]
        
        # KPI Row
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Today's Dials", len(daily_df))
        k2.metric("Contacts (Humans)", len(daily_df[daily_df['Outcome'] == 'Contact Made']))
        k3.metric("Appointments", len(log_df[log_df['Outcome'] == 'Appointment Scheduled']))
        k4.metric("Closed Deals", len(log_df[log_df['Outcome'] == 'Closed Deal']))

        # Detailed Breakdown
        st.divider()
        col_list, col_trend = st.columns([1, 2])
        
        with col_list:
            st.subheader("Pipeline Health")
            st.write(f"🔥 **Hot Leads:** {len(log_df[log_df['Rating'] == 'Hot'])}")
            st.write(f"⛅ **Warm Leads:** {len(log_df[log_df['Rating'] == 'Warm'])}")
            st.write(f"❄️ **Cold Leads:** {len(log_df[log_df['Rating'] == 'Cold'])}")

        with col_trend:
            st.subheader("Execution History")
            daily_stats = log_df.set_index('Timestamp').resample('D').count()['Lead Name']
            st.line_chart(daily_stats)

        st.subheader("Raw Activity History")
        st.dataframe(log_df.sort_values('Timestamp', ascending=False), use_container_width=True)
    else:
        st.info("The system is waiting for its first dial. Go to the Dialer.")

st.caption(f"Operator: {st.session_state.user} | Sequence Position: {st.session_state.index + 1}")
