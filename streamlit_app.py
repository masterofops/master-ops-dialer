import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import re

# --- PAGE CONFIG ---
st.set_page_config(page_title="Master of Ops Dialer", layout="centered")

# --- 1. CONNECTION & SESSION STATE ---
conn = st.connection("gsheets", type=GSheetsConnection)

if 'index' not in st.session_state:
    st.session_state.index = 0

# --- 2. THE BULLETPROOF PHONE FILTER ---
def clean_phone_for_dialing(phone_value):
    """
    Strips all non-numeric characters to ensure the tel: link works.
    Ensures +1 is handled if present.
    """
    if pd.isna(phone_value) or phone_value == "":
        return None
    
    # Convert to string and strip all non-digits except '+'
    phone_str = str(phone_value)
    
    # Keep the '+' if it's the first character (for international), 
    # then remove all other non-digits (spaces, dashes, parens)
    has_plus = phone_str.startswith('+')
    clean_digits = re.sub(r'\D', '', phone_str)
    
    if has_plus:
        return f"+{clean_digits}"
    return clean_digits

# --- 3. LOAD DATA ---
try:
    # Set ttl to 0 if you want to see sheet updates immediately on refresh
    df = conn.read(ttl=0) 
    if df.empty:
        st.warning("Inventory Empty: No leads found in the first tab.")
        st.stop()
except Exception as e:
    st.error(f"Handshake failed: {e}")
    st.stop()

# Progress check
if st.session_state.index >= len(df):
    st.success("🏁 List Complete! All targets processed.")
    if st.button("Restart from Lead 1"):
        st.session_state.index = 0
        st.rerun()
    st.stop()

# Current Lead Data
lead = df.iloc[st.session_state.index]

#Circulatory System for Gsheets writing
def commit_activity(lead_name, outcome, note, is_contact):
    # 1. Log the individual call
    log_entry = pd.DataFrame([{
        "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Lead Name": lead_name,
        "Outcome": outcome,
        "Note": note,
        "Caller ID": "Alfonso" # Can be dynamic later
    }])
    conn.create(worksheet="Activity_Log", data=log_entry)

    # 2. Update KPI Totals
    # We fetch the current week's row and increment the counts
    # This is a 'scrappy' way to do it without complex database queries
    st.toast(f"Logged {outcome} for {lead_name}!")

#write back KPI logic
def commit_activity(lead_name, outcome, note, is_contact):
    # 1. Log the individual call
    log_entry = pd.DataFrame([{
        "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Lead Name": lead_name,
        "Outcome": outcome,
        "Note": note,
        "Caller ID": "Alfonso" # Can be dynamic later
    }])
    conn.create(worksheet="Activity_Log", data=log_entry)

    # 2. Update KPI Totals
    # We fetch the current week's row and increment the counts
    # This is a 'scrappy' way to do it without complex database queries
    st.toast(f"Logged {outcome} for {lead_name}!")

# --- 4. UI LAYOUT ---
st.title(f"📞 {lead.get('First Name', 'N/A')} {lead.get('Last Name', 'N/A')}")
st.subheader(f"{lead.get('Company Name', 'N/A')} | {lead.get('Title', 'N/A')}")

col1, col2 = st.columns(2)

with col1:
    st.info(f"📍 {lead.get('City', 'N/A')}, {lead.get('State', 'N/A')}")
    st.write(f"💰 Revenue: {lead.get('Annual Revenue', 'N/A')}")
    
    # Apply the Bulletproof Filter
    raw_phone = lead.get('Corporate Phone', '')
    dial_link = clean_phone_for_dialing(raw_phone)
    
    if dial_link:
        # st.link_button is the most reliable 'Operator' tool for mobile
        st.link_button(f"📲 DIAL: {raw_phone}", f"tel:{dial_link}", use_container_width=True)
    else:
        st.error("No valid number in 'Corporate Phone' column.")

with col2:
    rating = st.selectbox("Rating", ["Cold", "Warm", "Hot"], index=1)
    # Using a unique key per index so notes don't bleed into the next lead
    notes = st.text_area("Call Notes", key=f"notes_{st.session_state.index}")

with col2:
    st.markdown("### **Company Specs**")
    st.write(f"🏭 **Industry:** {lead.get('Industry', '---')}")
    st.write(f"👥 **Employees:** {lead.get('# Employees', '---')}")
    st.write(f"💰 **Revenue:** {lead.get('Annual Revenue', '---')}")

#AI Email Composer
import openai

if st.button("🪄 Draft Master of Ops Email"):
    client = openai.OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
    
    prompt = f"""
    Write a short, punchy 'Master of Ops' style email.
    Target: {lead['First Name']}, {lead['Title']} at {lead['Company Name']}.
    Context: {lead['Industry']}, {lead['Annual Revenue']} revenue.
    Call Notes: {notes}
    Outcome: {outcome_selection}
    
    Guidelines: No jargon, direct, 'operator-first' tone. 
    Focus on systems, not heroes. Max 3 sentences.
    """
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )
    
    email_draft = response.choices[0].message.content
    st.text_area("AI Draft (Edit & Copy)", value=email_draft, height=200)
    
    # Clickable link to open Gmail/Mail app
    st.markdown(f"[✉️ Open in Email App](mailto:{lead['Email']}?subject=Follow up&body={email_draft})")
    
# --- 5. SAVE & LOGGING ---
st.divider()
if st.button("✅ LOG CALL & NEXT LEAD", use_container_width=True):
    # Verdad Operativa: We update the dataframe and push to Google
    df.at[st.session_state.index, 'Rating'] = rating
    df.at[st.session_state.index, 'Notes'] = notes
    
    try:
        conn.update(data=df)
        st.toast("System Updated", icon="💾")
    except Exception as e:
        st.warning("View-Only Mode: Note not saved to Google Sheets.")
    
    st.session_state.index += 1
    st.rerun()

#The Dashboard 52-week view
with st.sidebar:
    mode = st.radio("Navigation", ["Dialer", "Dashboard"])

if mode == "Dashboard":
    st.title("📈 Performance Metrics")
    
    # Load the Activity Log
    activity_df = conn.read(worksheet="Activity_Log")
    
    # Create simple metrics
    total_dials = len(activity_df)
    contacts = len(activity_df[activity_df['Outcome'] == 'Connected'])
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Dials", total_dials)
    c2.metric("Contacts", contacts)
    c3.metric("Conv. Rate", f"{(contacts/total_dials)*100:.1f}%" if total_dials > 0 else "0%")

    # 52-Week Trend (Group by Week)
    activity_df['Timestamp'] = pd.to_datetime(activity_df['Timestamp'])
    weekly_trend = activity_df.resample('W', on='Timestamp').count()['Lead Name']
    st.line_chart(weekly_trend)


# --- FOOTER ---
st.caption(f"Lead {st.session_state.index + 1} of {len(df)} | Operational Status: Running")
