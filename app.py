import streamlit as st
import requests
import base64
from datetime import datetime, timedelta

# 1. SETUP SECRETS
CID, SEC, URI = st.secrets["FITBIT_CLIENT_ID"], st.secrets["FITBIT_CLIENT_SECRET"], st.secrets["YOUR_SITE_URL"]

st.set_page_config(page_title="Fitbit Data Sync", layout="wide")
st.title("📡 Fitbit Raw Data Diagnostic")
st.write("Vitals: **6 Months** | Detailed Macros: **Last 3 months (90 days)**")

if "tk" not in st.session_state: st.session_state.tk = None

# 2. LOGIN LOGIC
qp = st.query_params
if "code" in qp and not st.session_state.tk:
    try:
        auth_b = base64.b64encode(f"{CID}:{SEC}".encode()).decode()
        r = requests.post("https://api.fitbit.com/oauth2/token", 
            headers={"Authorization": f"Basic {auth_b}", "Content-Type": "application/x-www-form-urlencoded"},
            data={"grant_type": "authorization_code", "code": qp["code"], "redirect_uri": URI}).json()
        if "access_token" in r:
            st.session_state.tk = r["access_token"]
            st.query_params.clear()
            st.rerun()
    except Exception as e:
        st.error(f"Login failed: {e}")

# 3. DATA COLLECTION
if st.session_state.tk:
    st.sidebar.success("✅ Linked")
    if st.sidebar.button("Logout"):
        st.session_state.tk = None
        st.query_params.clear()
        st.rerun()

    h = {"Authorization": f"Bearer {st.session_state.tk}"}
    
    if st.button("🔄 Pull All Health Data (90-Day Macro Deep Dive)"):
        with st.spinner("Fetching 6 months of vitals..."):
            try:
                # --- TIMELINES (6 Months) ---
                steps = requests.get("https://api.fitbit.com/1/user/-/activities/steps/date/today/6m.json", headers=h).json()
                weight = requests.get("https://api.fitbit.com/1/user/-/body/weight/date/today/6m.json", headers=h).json()
                fat = requests.get("https://api.fitbit.com/1/user/-/body/fat/date/today/6m.json", headers=h).json()
                
                # --- MACRO LOOP (90 Days) ---
                # We use a progress bar because this takes time
                macro_data = []
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                num_days = 90 
                for i in range(1, num_days + 1):
                    # Update Progress
                    progress = i / num_days
                    progress_bar.progress(progress)
                    
                    date_str = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
                    status_text.text(f"Fetching macros for: {date_str} ({i}/{num_days})")
                    
                    day_log = requests.get(f"https://api.fitbit.com/1/user/-/foods/log/date/{date_str}.json", headers=h).json()
                    summary = day_log.get('summary', {})
                    
                    # Only add if there is actually data for that day
                    if summary and summary.get('calories', 0) > 0:
                        macro_data.append({
                            "Date": date_str,
                            "Protein (g)": summary.get('protein', 0),
                            "Fat (g)": summary.get('fat', 0),
                            "Carbs (g)": summary.get('carbs', 0),
                            "Calories": summary.get('calories', 0)
                        })
                
                status_text.text("✅ Macro Sync Complete!")

                # --- Sleep (Last 100 sessions) ---
                sleep = requests.get("https://api.fitbit.com/1.2/user/-/sleep/list.json?afterDate=2024-01-01&limit=100&sort=desc", headers=h).json()

                # DISPLAY RESULTS
                st.subheader("Final Verification")
                col1, col2 = st.columns(2)
                
                with col1:
                    with st.expander("🥩 90-Day Detailed Macro Table"):
                        if macro_data:
                            st.write(f"Found {len(macro_data)} days with food logs.")
                            st.table(macro_data)
                        else:
                            st.write("No food logs found in the last 90 days.")
                    with st.expander("😴 Last 100 Sleep Sessions"):
                        st.json(sleep)

                with col2:
                    with st.expander("⚖️ 6-Month Weight & Body Fat"):
                        st.json(weight)
                        st.json(fat)
                    with st.expander("🚶 6-Month Step History"):
                        st.json(steps)
                
                st.success("Mission Accomplished: All 6 months of vitals and 3 months of macros are in the app!")
                
            except Exception as e:
                st.error(f"Error fetching data: {e}")

else:
    scope = "activity%20heartrate%20nutrition%20profile%20sleep%20weight"
    link = f"https://www.fitbit.com/oauth2/authorize?response_type=code&client_id={CID}&scope={scope}&redirect_uri={URI}"
    st.markdown(f"### [🔗 Connect Fitbit]({link})")

# --- END OF APP ---
