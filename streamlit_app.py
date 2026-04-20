import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import re
from datetime import datetime, timedelta
import urllib.parse
import time

import time

# --- MASTER STRUCTURE DEFINITION ---
MASTER_COLUMNS = [
    "First Name", "Last Name", "Corporate Phone", "Company Name", "Email", "Title", 
    "Primary Email", "Catch-all Status", "Seniority", "Stage", "Person Linkedin", 
    "City", "State", "Country", "# Employees", "Status", "Rating", "Last Touch", 
    "Next Follow up", "Company Linkedin", "Industry", "Website", "Lists", "Keywords", 
    "Secondary Email", "Annual Revenue", "Notes", "Company Name for Emails", 
    "Email Status", "Primary Email Source", "Primary Email Verification Source", 
    "Email Confidence", "Primary Email Catch-all Status", "Primary Email Last Verified At", 
    "Departments", "Sub Departments", "Contact Owner", "Work Direct Phone", "Home Phone", 
    "Mobile Phone", "Other Phone", "Do Not Call", "Last Contacted", "Account Owner", 
    "Person Linkedin Url", "Company Linkedin Url", "Facebook Url", "Twitter Url", 
    "Company Address", "Company City", "Company State", "Company Country", "Company Phone", 
    "Technologies", "Total Funding", "Latest Funding", "Latest Funding Amount", "Last Raised At", 
    "Subsidiary of", "Subsidiary of (Organization ID)", "Email Sent", "Email Open", 
    "Email Bounced", "Replied", "Demoed", "Number of Retail Locations", "Apollo Contact Id", 
    "Apollo Account Id", "Secondary Email Source", "Secondary Email Status", 
    "Secondary Email Verification Source", "Tertiary Email", "Tertiary Email Source", 
    "Tertiary Email Status", "Tertiary Email Verification Source", "Primary Intent Topic", 
    "Primary Intent Score", "Secondary Intent Topic", "Secondary Intent Score", 
    "Qualify Contact", "Company ID", "Company", "Physical Address", "Physical City", 
    "Physical Zip", "Physical County", "Mailing Address", "Mailing City", "Mailing State", 
    "Mailing Zip", "Phone", "Alternate Phone", "Toll Free", "Company Email", "Employees", 
    "Total Employees", "Min Sales", "Max Sales", "Annual Sales", "Square Footage", 
    "Year Established", "Distribution Area", "Ownership", "Imports", "Woman Owned", 
    "Minority Owned", "Veteran Owned", "ISO Certifications", "Business Description", 
    "Brand Names", "Primary SIC Code", "Primary SIC Code Description", "SIC Code 2", 
    "SIC Code 2 Description", "SIC Code 3", "SIC Code 3 Description", "SIC Code 4", 
    "SIC Code 4 Description", "NAICS Code", "NAICS Code Description"
]
for i in range(1, 16):
    prefix = f"Executive {i}"
    MASTER_COLUMNS.extend([
        f"{prefix} Contact ID", f"{prefix} Salutation", f"{prefix} First Name", 
        f"{prefix} Middle Name", f"{prefix} Last Name", f"{prefix} Suffix", 
        f"{prefix} Title", f"{prefix} Abbreviated Title", f"{prefix} Direct Email", 
        f"{prefix} Direct Phone"
    ])

# --- PAGE CONFIG ---
st.set_page_config(page_title="Master of Ops Dialer", layout="wide")


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
            raw_data = pd.DataFrame()
            if uploaded_file:
                raw_data = pd.read_csv(uploaded_file, encoding='latin1', on_bad_lines='skip')
            elif pasted_data:
                rows = [line.split('\t') for line in pasted_data.strip().split('\n')]
                raw_data = pd.DataFrame(rows)
                if not any('@' in str(x) for x in rows[0]):
                    raw_data.columns = [f"col_{i}" for i in range(len(rows[0]))]
                else:
                    raw_data.columns = rows[0]
                    raw_data = raw_data[1:]

            if not raw_data.empty:
                # 1. Create a container that matches your EXACT Master Sheet structure
                new_batch = pd.DataFrame(columns=df.columns)
                
                # 2. Map Raw Data to Master Columns
                # We look at every column in YOUR MASTER SHEET and try to find a match in the UPLOAD
                for master_col in df.columns:
                    # Look for the best match in the uploaded file
                    # It checks for exact names, then partial keywords
                    match = next((c for c in raw_data.columns if str(c).lower() == str(master_col).lower()), None)
                    
                    if not match:
                        # Fallback: Fuzzy search for common industrial/Apollo variations
                        keywords = []
                        if "Email" in master_col: keywords = ["email", "correo", "mail", "executive 1 direct email"]
                        elif "First Name" in master_col: keywords = ["first name", "nombre", "executive 1 first name"]
                        elif "Last Name" in master_col: keywords = ["last name", "apellido", "executive 1 last name"]
                        elif "Phone" in master_col: keywords = ["phone", "tel", "mobile", "direct"]
                        elif "Company" in master_col: keywords = ["company", "account", "firm", "empresa"]
                        
                        match = next((c for c in raw_data.columns if any(k in str(c).lower() for k in keywords)), None)
                    
                    if match:
                        new_batch[master_col] = raw_data[match]

               # 3. Clean up the new batch (remove empty rows)
                new_batch = new_batch.dropna(how='all')

            if not new_batch.empty:
                if col_email and col_email in df.columns:
                    existing_emails = df[col_email].astype(str).str.lower().unique()
                    new_leads = new_batch[~new_batch[col_email].astype(str).str.lower().isin(existing_emails)]
                else:
                    new_leads = new_batch

                if not new_leads.empty:
                    # Direct append to your existing dataframe
                    df = pd.concat([df, new_leads], ignore_index=True)
                    
                    # 5. Save and Reset
                    df = df.reset_index(drop=True)
                    conn.update(data=df)
                    
                    st.session_state.index = 0 
                    st.success(f"Successfully injected {len(new_leads)} leads into your Master Structure.")
                    st.cache_data.clear()
                    time.sleep(1)
                    st.rerun()
                else:
                    st.warning("No new leads to add (all were duplicates).")
        except Exception as e:
            st.error(f"Injection Error: {e}")
            
    # 3. Execution (Priority Mapping)
    find_and_fill("First Name", ["executive 1 first name", "first name", "nombre"])
    find_and_fill("Last Name", ["executive 1 last name", "last name", "apellido"])                    
    find_and_fill("Email", ["executive 1 direct email", "primary email", "email", "@"])
    find_and_fill("Title", ["executive 1 title", "title", "role"])
    find_and_fill("Work Direct Phone", ["executive 1 direct phone", "work direct phone", "phone"])
    find_and_fill("Company Name", ["company name", "company", "account"])
    find_and_fill("Annual Revenue", ["annual sales", "annual revenue", "max sales"])
    find_and_fill("# Employees", ["total employees", "employees", "# employees"])
    
    # 4. Auto-fill remaining columns that match exact names
    for col in MASTER_COLUMNS:
        if col not in mapped_df.columns or mapped_df[col].isnull().all():
            find_and_fill(col, [col])

                # 5. Merge with existing database (Anchor on Email)
                m_email = "Email"
                if m_email in df.columns:
                    existing_emails = df[m_email].astype(str).str.lower().unique()
                    new_leads = mapped_df[~mapped_df[m_email].astype(str).str.lower().isin(existing_emails)]
                    if not new_leads.empty:
                        df = pd.concat([df, new_leads], ignore_index=True)
                else:
                    df = mapped_df

                # 6. Final Sync
                df = df.reset_index(drop=True)
                conn.update(data=df)
                st.session_state.index = 0 
                st.success(f"Mapped {len(mapped_df)} leads to Master Structure.")
                st.cache_data.clear()
                time.sleep(1)
                st.rerun()

        except Exception as e:
            st.error(f"Mapping Error: {e}")
            
# --- MODE: DIALER ---
if mode == "Dialer":
    # 1. Check if the list has data
    if df.empty:
        st.warning("Master list is empty. Please upload or paste leads in the sidebar.")
        st.stop()
        
    # 2. Safety Check: Ensure the counter isn't pointing at a non-existent lead
    if st.session_state.index >= len(df) or st.session_state.index < 0:
        st.session_state.index = 0

    # 3. Load lead data
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
            
            # --- GOOGLE CALENDAR APPOINTMENT ---
        if st.button("📅 SCHEDULE G-CAL", use_container_width=True):
            # Encode lead info for the URL
            subject = urllib.parse.quote(f"Clarity Call: Master of Ops x {lead.get(col_comp, 'Lead')}")
            details = urllib.parse.quote(f"Meeting with {full_name}\nEmail: {email_val}\nNotes: {lead.get(col_notes, '')}")
            
            # Create Google Calendar Link (30 min default)
            gcal_link = f"https://www.google.com/calendar/render?action=TEMPLATE&text={subject}&details={details}"
            if pd.notna(email_val):
                gcal_link += f"&add={email_val}"
            
            st.components.v1.html(f"<script>window.open('{gcal_link}', '_blank');</script>", height=0)
            log_action("G-Cal Invite Prepared", step=0)
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
