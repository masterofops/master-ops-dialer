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

# Re-mapping with industrial-strength detection
col_first = get_cols(df, ["first name", "executive 1 first", "nombre", "lead name", "contact name"])[0] if get_cols(df, ["first", "nombre", "lead"]) else None
col_last = get_cols(df, ["last name", "executive 1 last", "apellido"])[0] if get_cols(df, ["last", "apellido"]) else None
col_comp = get_cols(df, ["company name", "company", "account", "empresa", "organización", "firm"])[0] if get_cols(df, ["company", "account", "empresa"]) else None

# Aggressive Phone Detection (Pulls all available numbers into the Dial list)
phone_cols = get_cols(df, ["phone", "mobile", "tel", "celular", "direct phone", "work direct", "corporate phone", "toll free"])

# LinkedIn & Links
li_cols = get_cols(df, ["person linkedin url", "linkedin", "profile", "li-", "person url"])

# Email
col_email = get_cols(df, ["email", "executive 1 direct email", "correo", "mail", "@"])[0] if get_cols(df, ["email", "correo", "mail"]) else None

# Notes & Descriptions
col_notes = get_cols(df, ["business description", "notes", "comment", "history", "notas", "log"])[0] if get_cols(df, ["description", "notes", "notas"]) else "Notes"

# Specific Intelligence Fields (For the right-hand column)
col_revenue = get_cols(df, ["annual revenue", "annual sales", "total sales", "min sales"])[0] if get_cols(df, ["revenue", "sales"]) else None
col_employees = get_cols(df, ["total employees", "# employees", "employees", "num employees"])[0] if get_cols(df, ["employee", "staff"]) else None
col_role = get_cols(df, ["executive 1 title", "title", "role", "seniority", "position"])[0] if get_cols(df, ["title", "role"]) else None

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
    
    # Option 1: File Upload
    uploaded_file = st.file_uploader("Upload CSV", type=["csv"])
    
    # Option 2: Copy-Paste Contacts
    pasted_data = st.text_area("Or paste emails here (one per line):")

    if st.button("Add to Master List"):
        try:
            new_entries = pd.DataFrame()
            if uploaded_file:
                new_entries = pd.read_csv(uploaded_file, encoding='latin1', on_bad_lines='skip')
            elif pasted_data:
                # Detect if pasted data is a table (Excel/LinkedIn) or just list
                rows = [line.split('\t') for line in pasted_data.strip().split('\n')]
                if len(rows[0]) > 1:
                    temp_df = pd.DataFrame(rows)
                    # Try to find headers in first row, else use Master Sheet columns
                    if any('@' in str(x) for x in rows[0]): # No header row
                        temp_df.columns = df.columns[:len(temp_df.columns)]
                    else:
                        temp_df.columns = rows[0]
                        temp_df = temp_df[1:] # Drop header row
                    new_entries = temp_df
                else:
                    new_entries = pd.DataFrame({col_email: [r[0].strip() for r in rows if '@' in r[0]]})

            if not new_entries.empty:
                # Standardize columns to match Master
                new_entries.columns = [c.strip() for c in new_entries.columns]
                
                # Merge logic: Email is the Anchor
                if col_email in new_entries.columns and col_email in df.columns:
                    # Identify existing vs new
                    existing_emails = df[col_email].unique()
                    updates = new_entries[new_entries[col_email].isin(existing_emails)]
                    additions = new_entries[~new_entries[col_email].isin(existing_emails)]
                    
                    # Update existing leads (Enrichment)
                    for _, row in updates.iterrows():
                        idx = df[df[col_email] == row[col_email]].index[0]
                        for col in row.index:
                            if col in df.columns and pd.notna(row[col]):
                                df.at[idx, col] = row[col]
                    
                    # Add brand new leads
                    if not additions.empty:
                        df = pd.concat([df, additions], ignore_index=True)
                
                conn.update(data=df)
                st.success(f"Processed {len(new_entries)} leads. Duplicates enriched, new leads added.")
                st.cache_data.clear()
                time.sleep(1)
                st.rerun()
        except Exception as e:
            st.error(f"Logic Error: {e}")
            
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
        # --- A. MULTI-CONTACT RELATABILITY ---
        if col_comp and pd.notna(lead.get(col_comp)):
            company_name = lead.get(col_comp)
            others = df[df[col_comp] == company_name]
            # Exclude the current lead from the "others" list
            others = others[others[col_email] != lead.get(col_email)]
            
            if not others.empty:
                with st.expander(f"👥 OTHER CONTACTS AT {company_name}", expanded=False):
                    for _, o_lead in others.iterrows():
                        o_name = f"{o_lead.get(col_first, '')} {o_lead.get(col_last, '')}"
                        o_role = next((o_lead.get(c) for c in df.columns if 'title' in c.lower() or 'role' in c.lower()), "N/A")
                        st.write(f"**{o_name}** ({o_role})")
                        if col_email in o_lead: st.caption(f"📧 {o_lead[col_email]}")
        
        st.divider()

        # --- B. SPECIFIC KEY INFO ---
        info_keys = ["title", "role", "location", "employee", "revenue", "keywords"]
        found_cols = []
        for col in df.columns:
            if any(key in col.lower() for key in info_keys):
                val = lead.get(col, 'N/A')
                if pd.notna(val) and str(val).strip() != '':
                    st.write(f"🔹 **{col}:** {val}")
                    found_cols.append(col)

        # --- C. CATCH-ALL (HIDDEN DATA BOX) ---
        # This shows everything else that isn't already displayed
        already_shown = [col_first, col_last, col_comp, col_email, col_notes, "Rating", "Last Touch"] + phone_cols + found_cols
        other_data = ""
        for col in df.columns:
            if col not in already_shown:
                val = lead.get(col, '')
                if pd.notna(val) and str(val).strip() != '':
                    other_data += f"{col}: {val}\n"
        
        if other_data:
            st.text_area("📋 Raw Lead Data (Uncategorized)", value=other_data, height=150)

        st.divider()
        
        # LinkedIn Profiles
        for col in df.columns:
            if "linkedin" in col.lower() or "profile" in col.lower():
                url = lead.get(col, '')
                if pd.notna(url) and str(url).startswith('http'):
                    st.write(f"👤 **{col}:** [View Profile]({url})")
        
        st.info(f"📋 **Static Sheet Notes:**\n\n {lead.get(col_notes, 'None')}")
        
        st.info(f"📋 **Static Sheet Notes:**\n\n {lead.get(col_notes, 'None')}")

    def log_action(outcome, step=0): # Default step to 0 so it doesn't move unless told
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
            conn.update(worksheet="Activity_Log", data=entry)
        
        if step != 0:
            st.session_state.index += step
            st.rerun()

   # --- ACTION BUTTONS ---
    st.write("---")
    c1, c2, c3, c4, c5 = st.columns(5)
    
    with c1:
        if st.button("⬅️ PREVIOUS", use_container_width=True):
            if st.session_state.index > 0:
                st.session_state.index -= 1
                st.rerun()
                
    with c1: # Add this below the Existing Previous Button
        if st.button("⏭️ SKIP", use_container_width=True):
            move_val = 1 if dial_dir == "Top to Bottom" else -1
            st.session_state.index += move_val
            st.rerun()
            
    with c2:
        if st.button("✅ LOG & NEXT", type="primary", use_container_width=True):
            move_val = 1 if dial_dir == "Top to Bottom" else -1
            log_action("Contact Made" if contact_made else "Outbound Call", step=move_val)

    with c3:
        # Change to a direct link button for reliability
        st.link_button("🔗 ZCAL", "https://zcal.co/masterofops/clarity", use_container_width=True)
        # Note: Standard link buttons don't trigger log_action until clicked. 
        # For OPS accuracy, keep your manual log.

    with c4:
        if st.button("💸 CLOSED", use_container_width=True):
            st.balloons()
            log_action("Closed Deal")

    with c5:
        email_val = lead.get(col_email, '')
        if pd.notna(email_val) and "@" in str(email_val):
            # Desktop Mail
            st.link_button("✉️ DESKTOP MAIL", f"mailto:{email_val}", use_container_width=True)
            
            # Gmail Web
            gmail_url = f"https://mail.google.com/mail/?view=cm&fs=1&to={email_val}"
            st.link_button("🌐 GMAIL WEB", gmail_url, use_container_width=True)
        else:
            st.error("No email found")

elif mode == "Lead Manager":
    st.title("🗂️ Search & Filter Database")
    search_query = st.text_input("Filter by Name, Company, or Status...")
    
    if search_query:
        filtered_df = df[df.astype(str).apply(lambda x: x.str.contains(search_query, case=False)).any(axis=1)]
    else:
        filtered_df = df
        
    st.write(f"Showing {len(filtered_df)} leads")
    st.dataframe(filtered_df, use_container_width=True)

elif mode == "Dashboard":
    st.title("📊 Performance Dashboard")
    if not activity_log.empty:
        dials = len(activity_log)
        contacts = len(activity_log[activity_log['Outcome'].str.contains("Contact Made", na=False)])
        appts = len(activity_log[activity_log['Outcome'].str.contains("Scheduled|Zcal|G-Cal", na=False)])
        closed = len(activity_log[activity_log['Outcome'] == "Closed Deal"])

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Total Dials", dials)
        k2.metric("Contacts", contacts)
        k3.metric("Appointments", appts)
        k4.metric("Closures", closed)

        st.divider()
       activity_log['Timestamp'] = pd.to_datetime(activity_log['Timestamp'], errors='coerce')
activity_log = activity_log.dropna(subset=['Timestamp'])
        chart_data = activity_log.set_index('Timestamp').resample('D').count()['Lead Name']
        st.subheader("Daily Activity Volume")
        st.area_chart(chart_data)
    else:
        st.info("No activity logged yet.")
