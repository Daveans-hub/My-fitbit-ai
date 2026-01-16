import streamlit as st
import requests
import base64
from datetime import datetime, timedelta

# 1. SETUP SECRETS
CID, SEC, URI = st.secrets["FITBIT_CLIENT_ID"], st.secrets["FITBIT_CLIENT_SECRET"], st.secrets["YOUR_SITE_URL"]

st.set_page_config(page_title="Fitbit Data Sync", layout="wide")
st.title("📡 Fitbit Raw Data Diagnostic")
st.write("Vitals (Steps/Weight/Cals): **6 Months** | Detailed Macros: **Last 30 Days**")

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
    
    if st.button("🔄 Pull All Health Data"):
        with st.spinner("Fetching data (this takes a few seconds due to the macro loop)..."):
            try:
                # --- TIMELINES (6 Months) ---
                steps = requests.get("https://api.fitbit.com/1/user/-/activities/steps/date/today/6m.json", headers=h).json()
                weight = requests.get("https://api.fitbit.com/1/user/-/body/weight/date/today/6m.json", headers=h).json()
                fat = requests.get("https://api.fitbit.com/1/user/-/body/fat/date/today/6m.json", headers=h).json()
                cal_in_series = requests.get("https://api.fitbit.com/1/user/-/foods/log/caloriesIn/date/today/6m.json", headers=h).json()
                
                # --- MACRO LOOP (Last 30 Days) ---
                macro_data = []
                # We start from yesterday and go back 30 days
                for i in range(1, 31):
                    date_str = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
                    day_log = requests.get(f"https://api.fitbit.com/1/user/-/foods/log/date/{date_str}.json", headers=h).json()
                    summary = day_log.get('summary', {})
                    if summary:
                        macro_data.append({
                            "Date": date_str,
                            "Protein (g)": summary.get('protein', 0),
                            "Fat (g)": summary.get('fat', 0),
                            "Carbs (g)": summary.get('carbs', 0),
                            "Calories": summary.get('calories', 0)
                        })

                # --- Sleep (Last 50 sessions) ---
                sleep = requests.get("https://api.fitbit.com/1.2/user/-/sleep/list.json?afterDate=2024-01-01&limit=50&sort=desc", headers=h).json()

                # DISPLAY RESULTS
                st.subheader("Results")
                col1, col2 = st.columns(2)
                
                with col1:
                    with st.expander("⚖️ 6 Months: Weight & Body Fat"):
                        st.json(weight)
                        st.json(fat)
                    with st.expander("🥩 30 Days: Detailed Macro Table"):
                        if macro_data:
                            st.table(macro_data)
                        else:
                            st.write("No food logs found for the last 30 days.")

                with col2:
                    with st.expander("🚶 6 Months: Activity & Sleep"):
                        st.write("Steps:")
                        st.json(steps)
                        st.write("Sleep Sessions:")
                        st.json(sleep)
                
                st.success("Successfully pulled all variables!")
                
            except Exception as e:
                st.error(f"Error fetching data: {e}")

else:
    # Login Link
    scope = "activity%20heartrate%20nutrition%20profile%20sleep%20weight"
    link = f"https://www.fitbit.com/oauth2/authorize?response_type=code&client_id={CID}&scope={scope}&redirect_uri={URI}"
    st.markdown(f"### [🔗 Connect Fitbit]({link})")

# --- END OF APP ---
