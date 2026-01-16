import streamlit as st
import requests
import base64
from datetime import datetime, timedelta

# 1. SETUP SECRETS
CID, SEC, URI = st.secrets["FITBIT_CLIENT_ID"], st.secrets["FITBIT_CLIENT_SECRET"], st.secrets["YOUR_SITE_URL"]

st.set_page_config(page_title="Fitbit Raw Data Sync", layout="wide")
st.title("📡 Fitbit Raw Data Diagnostic")
st.write("This app pulls 6 months of data and displays the raw results to verify the connection.")

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

# 3. DATA COLLECTION (The "Trimmed Back" Engine)
if st.session_state.tk:
    st.sidebar.success("✅ Linked")
    if st.sidebar.button("Logout"):
        st.session_state.tk = None
        st.rerun()

    h = {"Authorization": f"Bearer {st.session_state.tk}"}
    
    if st.button("🔄 Pull 6 Months of Raw Data"):
        with st.spinner("Fetching data from Fitbit servers..."):
            # We use these endpoints to get 6 months (180 days)
            # Fitbit allows '6m' for activity and weight time-series
            
            try:
                # Steps
                steps = requests.get("https://api.fitbit.com/1/user/-/activities/steps/date/today/6m.json", headers=h).json()
                
                # Weight
                weight = requests.get("https://api.fitbit.com/1/user/-/body/weight/date/today/6m.json", headers=h).json()
                
                # Fat %
                fat = requests.get("https://api.fitbit.com/1/user/-/body/fat/date/today/6m.json", headers=h).json()
                
                # Calories Burned (Out)
                cal_out = requests.get("https://api.fitbit.com/1/user/-/activities/calories/date/today/6m.json", headers=h).json()
                
                # Calories Consumed (In)
                cal_in = requests.get("https://api.fitbit.com/1/user/-/foods/log/caloriesIn/date/today/6m.json", headers=h).json()
                
                # Sleep (Last 50 sessions)
                sleep = requests.get("https://api.fitbit.com/1.2/user/-/sleep/list.json?afterDate=2024-01-01&limit=50&sort=desc", headers=h).json()

                # DISPLAY RAW DATA
                st.subheader("Results")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    with st.expander("⚖️ Raw Weight Data (Last 6 Months)"):
                        st.json(weight)
                    with st.expander("📉 Raw Fat % Data"):
                        st.json(fat)
                    with st.expander("😴 Raw Sleep Logs"):
                        st.json(sleep)

                with col2:
                    with st.expander("🚶 Raw Steps Data"):
                        st.json(steps)
                    with st.expander("🔥 Raw Calories (Burned vs Consumed)"):
                        st.write("Calories Burned:")
                        st.json(cal_out)
                        st.write("Calories Consumed:")
                        st.json(cal_in)
                
                st.success("Data successfully retrieved!")
                
            except Exception as e:
                st.error(f"Error fetching data: {e}")

else:
    scope = "activity%20heartrate%20nutrition%20profile%20sleep%20weight"
    link = f"https://www.fitbit.com/oauth2/authorize?response_type=code&client_id={CID}&scope={scope}&redirect_uri={URI}"
    st.markdown(f"### [🔗 Connect Fitbit]({link})")

# --- END OF APP ---
