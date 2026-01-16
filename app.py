import streamlit as st
import requests
import base64
import json
import pandas as pd

# 1. LOAD SECRETS
CID, SEC, URI = st.secrets["FITBIT_CLIENT_ID"], st.secrets["FITBIT_CLIENT_SECRET"], st.secrets["YOUR_SITE_URL"]

# 2. PAGE SETUP
st.set_page_config(page_title="Kinetic Lab | Diagnostic", layout="wide")

st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');
        .stApp { background-color: #0F172A; color: #F8FAFC; font-family: 'Inter', sans-serif; }
        [data-testid="stSidebar"] { background-color: #1E293B; border-right: 1px solid rgba(255, 255, 255, 0.05); }
        .diagnostic-card { background: rgba(255, 255, 255, 0.05); border-radius: 12px; padding: 20px; border: 1px solid #38BDF8; margin-bottom: 20px; }
    </style>
    """, unsafe_allow_html=True)

if "tk" not in st.session_state: st.session_state.tk = None

# 3. LOGIN LOGIC
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
    except: st.error("Login failed.")

# 4. DIAGNOSTIC APP
if st.session_state.tk:
    st.sidebar.title("KINETIC LAB")
    st.sidebar.write("Diagnostic Mode Active")
    if st.sidebar.button("Logout"):
        st.session_state.tk = None
        st.rerun()

    st.title("📡 Data Discovery & Diagnostic")
    st.write("We are investigating why the numerical values for Weight and Fat% are not being captured.")

    if st.button("🔍 RUN FULL DATA DIAGNOSTIC"):
        h = {"Authorization": f"Bearer {st.session_state.tk}"}
        
        with st.spinner("Hunting for data..."):
            # A. Time Series - Usually for graphs
            ts_w = requests.get("https://api.fitbit.com/1/user/-/body/weight/date/today/30d.json", headers=h).json()
            ts_f = requests.get("https://api.fitbit.com/1/user/-/body/fat/date/today/30d.json", headers=h).json()
            ts_s = requests.get("https://api.fitbit.com/1/user/-/activities/steps/date/today/30d.json", headers=h).json()

            # B. Body Logs - Usually for manual entries
            log_w = requests.get("https://api.fitbit.com/1/user/-/body/log/weight/date/today/30d.json", headers=h).json()
            log_f = requests.get("https://api.fitbit.com/1/user/-/body/log/fat/date/today/30d.json", headers=h).json()

            st.divider()

            col1, col2 = st.columns(2)

            with col1:
                st.subheader("1. The 'Time Series' Drawer")
                st.write("This is where Fitbit stores data for 90-day trends.")
                with st.expander("Raw Weight Time Series"):
                    st.json(ts_w)
                with st.expander("Raw Fat% Time Series"):
                    st.json(ts_f)
                with st.expander("Raw Steps Time Series"):
                    st.json(ts_s)

            with col2:
                st.subheader("2. The 'Logs' Drawer")
                st.write("This is where manual scale entries usually hide.")
                with st.expander("Raw Weight Logs"):
                    st.json(log_w)
                with st.expander("Raw Fat% Logs"):
                    st.json(log_f)

            # Merged Verification Table
            st.subheader("3. Merged Data Test")
            st.write("If this table is empty or zeros, our 'Weaver' logic is where the bug lives.")
            
            # Simple Weaver Test
            master_test = []
            steps_list = ts_s.get('activities-steps', [])
            weight_list = ts_w.get('body-weight', [])

            for s in steps_list:
                date = s['dateTime']
                val_steps = s['value']
                # Search for weight on this date
                val_weight = next((w['value'] for w in weight_list if w['dateTime'] == date), "NOT FOUND")
                master_test.append({"Date": date, "Steps": val_steps, "Weight": val_weight})
            
            st.table(pd.DataFrame(master_test).head(10))

else:
    st.markdown(f"""
        <div style='text-align: center; margin-top: 10rem;'>
            <h1 style='font-size: 3rem; color: #F8FAFC;'>Kinetic Lab</h1>
            <p style='color: #94A3B8; margin-bottom: 2rem;'>Diagnostic Mode</p>
            <a href='https://www.fitbit.com/oauth2/authorize?response_type=code&client_id={CID}&scope=activity%20heartrate%20nutrition%20profile%20sleep%20weight&redirect_uri={URI}' 
               target='_blank' 
               style='background-color: #38BDF8; color: white; padding: 1rem 2.5rem; border-radius: 50px; text-decoration: none; font-weight: 800;'>
               CONNECT DIAGNOSTIC TOOL
            </a>
        </div>
    """, unsafe_allow_html=True)

# --- END OF APP ---
