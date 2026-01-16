
import streamlit as st
import requests
import base64
from datetime import datetime, timedelta

# 1. SETUP SECRETS
CID, SEC, URI = st.secrets["FITBIT_CLIENT_ID"], st.secrets["FITBIT_CLIENT_SECRET"], st.secrets["YOUR_SITE_URL"]

st.set_page_config(page_title="Fitbit Data Cache", layout="wide")
st.title("📡 Fitbit High-Performance Sync")
st.write("Vitals: **6 Months** | Macros: **3 Months**")

# Setup Memory (so we don't hit the rate limit twice)
if "tk" not in st.session_state: st.session_state.tk = None
if "cached_data" not in st.session_state: st.session_state.cached_data = None

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

# 3. DATA COLLECTION ENGINE
if st.session_state.tk:
    st.sidebar.success("✅ Connected")
    
    # Show Rate Limit Warning
    st.sidebar.warning("⚠️ Fitbit Limit: 150 requests/hour. A 90-day sync uses ~95 requests. Do not click Sync more than once per hour!")

    if st.sidebar.button("Logout / Clear Cache"):
        st.session_state.tk = None
        st.session_state.cached_data = None
        st.rerun()

    h = {"Authorization": f"Bearer {st.session_state.tk}"}
    
    # ONLY show the button if we don't have data yet
    if not st.session_state.cached_data:
        if st.button("🚀 Sync All Health Data (Uses ~95 Credits)"):
            try:
                with st.status("Fetching 6-month timeline...", expanded=True) as status:
                    # --- Vitals (1 request each) ---
                    steps = requests.get("https://api.fitbit.com/1/user/-/activities/steps/date/today/6m.json", headers=h).json()
                    weight = requests.get("https://api.fitbit.com/1/user/-/body/weight/date/today/6m.json", headers=h).json()
                    fat = requests.get("https://api.fitbit.com/1/user/-/body/fat/date/today/6m.json", headers=h).json()
                    # Sleep (1 request)
                    sleep = requests.get("https://api.fitbit.com/1.2/user/-/sleep/list.json?afterDate=2024-01-01&limit=100&sort=desc", headers=h).json()

                    # --- Macros (90 requests) ---
                    macro_data = []
                    progress_bar = st.progress(0)
                    
                    num_days = 90 
                    for i in range(1, num_days + 1):
                        progress = i / num_days
                        progress_bar.progress(progress)
                        
                        date_str = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
                        day_log = requests.get(f"https://api.fitbit.com/1/user/-/foods/log/date/{date_str}.json", headers=h).json()
                        summary = day_log.get('summary', {})
                        
                        if summary and summary.get('calories', 0) > 0:
                            macro_data.append({
                                "Date": date_str,
                                "Protein (g)": summary.get('protein', 0),
                                "Fat (g)": summary.get('fat', 0),
                                "Carbs (g)": summary.get('carbs', 0),
                                "Calories": summary.get('calories', 0)
                            })
                    
                    # Store everything in memory
                    st.session_state.cached_data = {
                        "steps": steps,
                        "weight": weight,
                        "fat": fat,
                        "sleep": sleep,
                        "macros": macro_data
                    }
                    status.update(label="✅ Sync Complete!", state="complete", expanded=False)
                    st.rerun()
            except Exception as e:
                st.error(f"Sync failed. You might have hit the hourly limit. Wait 60 mins. Error: {e}")

    # 4. DISPLAY THE MEMORY (If it exists)
    if st.session_state.cached_data:
        data = st.session_state.cached_data
        st.success("Displaying data from app memory (No new Fitbit credits used).")
        
        col1, col2 = st.columns(2)
        
        with col1:
            with st.expander("🥩 90-Day Macro Table", expanded=True):
                if data["macros"]:
                    st.table(data["macros"])
                else:
                    st.write("No food logs found.")
            
            with st.expander("😴 Last 100 Sleep Sessions"):
                st.json(data["sleep"])

        with col2:
            with st.expander("⚖️ 6-Month Weight & Fat"):
                st.json(data["weight"])
                st.json(data["fat"])
            
            with st.expander("🚶 6-Month Activity"):
                st.json(data["steps"])

else:
    # Login Link
    scope = "activity%20heartrate%20nutrition%20profile%20sleep%20weight"
    link = f"https://www.fitbit.com/oauth2/authorize?response_type=code&client_id={CID}&scope={scope}&redirect_uri={URI}"
    st.markdown(f"### [🔗 Connect Fitbit]({link})")

# --- END OF APP ---
