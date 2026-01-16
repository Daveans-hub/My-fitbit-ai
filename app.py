import streamlit as st
import requests
import base64

# 1. SETUP SECRETS
CID, SEC, URI = st.secrets["FITBIT_CLIENT_ID"], st.secrets["FITBIT_CLIENT_SECRET"], st.secrets["YOUR_SITE_URL"]

st.set_page_config(page_title="Fitbit Raw Data Sync", layout="wide")
st.title("📡 Fitbit Raw Data Diagnostic")
st.write("Fetching 6 months of Vitals + Macronutrients (Protein, Carbs, Fats).")

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
        st.rerun()

    h = {"Authorization": f"Bearer {st.session_state.tk}"}
    
    if st.button("🔄 Pull 6 Months of Raw Data (Including Macros)"):
        with st.spinner("Fetching full 180-day history..."):
            try:
                # --- Vitals & Activity ---
                steps = requests.get("https://api.fitbit.com/1/user/-/activities/steps/date/today/6m.json", headers=h).json()
                weight = requests.get("https://api.fitbit.com/1/user/-/body/weight/date/today/6m.json", headers=h).json()
                fat = requests.get("https://api.fitbit.com/1/user/-/body/fat/date/today/6m.json", headers=h).json()
                
                # --- Nutrition (Calories + Macros) ---
                cal_in = requests.get("https://api.fitbit.com/1/user/-/foods/log/caloriesIn/date/today/6m.json", headers=h).json()
                prot = requests.get("https://api.fitbit.com/1/user/-/foods/log/protein/date/today/6m.json", headers=h).json()
                fat_nut = requests.get("https://api.fitbit.com/1/user/-/foods/log/fat/date/today/6m.json", headers=h).json()
                carb = requests.get("https://api.fitbit.com/1/user/-/foods/log/carbs/date/today/6m.json", headers=h).json()
                
                # --- Sleep ---
                sleep = requests.get("https://api.fitbit.com/1.2/user/-/sleep/list.json?afterDate=2024-01-01&limit=50&sort=desc", headers=h).json()

                # DISPLAY RAW DATA
                st.subheader("Raw Data Verification")
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    with st.expander("⚖️ Weight & Fat %"):
                        st.write("Weight History:")
                        st.json(weight)
                        st.write("Body Fat History:")
                        st.json(fat)

                with col2:
                    with st.expander("🚶 Activity & Sleep"):
                        st.write("Steps History:")
                        st.json(steps)
                        st.write("Sleep Logs:")
                        st.json(sleep)

                with col3:
                    with st.expander("🥩 Macronutrients & Calories"):
                        st.write("Protein (grams):")
                        st.json(prot)
                        st.json(carb)
                        st.write("Fats (grams):")
                        st.json(fat_nut)
                        st.write("Total Calories In:")
                        st.json(cal_in)
                
                st.success("All data points retrieved!")
                
            except Exception as e:
                st.error(f"Error fetching data: {e}")

else:
    url = f"https://www.fitbit.com/oauth2/authorize?response_type=code&client_id={CID}&scope=activity%20heartrate%20nutrition%20profile%20sleep%20weight&redirect_uri={URI}"
    st.markdown(f"### [🔗 Connect Fitbit]({url})")

# --- END OF APP ---
