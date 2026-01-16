import streamlit as st
import requests
import base64
import json
import pandas as pd
from datetime import datetime, timedelta

# 1. LOAD SECRETS
CID, SEC, URI = st.secrets["FITBIT_CLIENT_ID"], st.secrets["FITBIT_CLIENT_SECRET"], st.secrets["YOUR_SITE_URL"]

# 2. GLOBAL STYLING (Professional Dark + Pure White Text)
st.set_page_config(page_title="Kinetic Lab | Diagnostic", layout="wide")

st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');
        
        /* Background Slate Blue-Black */
        .stApp, [data-testid="stAppViewContainer"] {
            background-color: #0F172A !important;
            font-family: 'Inter', sans-serif;
        }

        /* FORCE ALL TEXT TO PURE WHITE */
        html, body, [class*="css"], .stMarkdown, p, h1, h2, h3, li, span, label, div {
            color: #FFFFFF !important;
        }

        /* Sidebar: Deep Navy */
        [data-testid="stSidebar"] {
            background-color: #1E293B !important;
            border-right: 1px solid rgba(255, 255, 255, 0.1);
        }

        /* Diagnostic Tables Styling */
        .stTable, table, th, td {
            color: #FFFFFF !important;
            background-color: rgba(255,255,255,0.05) !important;
        }

        /* Primary Button (Sky Blue) */
        .stButton button {
            width: 100% !important;
            background-color: #38BDF8 !important;
            color: white !important;
            font-weight: 700 !important;
            border: none !important;
            border-radius: 8px;
            height: 3.5em;
        }
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

# 4. DIAGNOSTIC DASHBOARD
if st.session_state.tk:
    st.sidebar.title("KINETIC LAB")
    st.sidebar.write("Diagnostic Mode: AI DISABLED")
    if st.sidebar.button("Logout"):
        st.session_state.tk = None
        st.rerun()

    st.title("📡 Raw Data Synchronization")
    st.write("Pulling 180 days of vitals to verify numerical accuracy.")

    if st.button("🔍 RUN FULL DATA EXTRACTION"):
        h = {"Authorization": f"Bearer {st.session_state.tk}"}
        
        with st.spinner("Harvesting data from Fitbit Time-Series..."):
            try:
                # A. PULL ALL 6-MONTH TIME SERIES
                s_raw = requests.get("https://api.fitbit.com/1/user/-/activities/steps/date/today/6m.json", headers=h).json().get('activities-steps', [])
                w_raw = requests.get("https://api.fitbit.com/1/user/-/body/weight/date/today/6m.json", headers=h).json().get('body-weight', [])
                f_raw = requests.get("https://api.fitbit.com/1/user/-/body/fat/date/today/6m.json", headers=h).json().get('body-fat', [])
                co_raw = requests.get("https://api.fitbit.com/1/user/-/activities/calories/date/today/6m.json", headers=h).json().get('activities-calories', [])
                ci_raw = requests.get("https://api.fitbit.com/1/user/-/foods/log/caloriesIn/date/today/6m.json", headers=h).json().get('foods-log-caloriesIn', [])

                # B. WEAVER LOGIC (Merging by Date)
                master = {}
                def weave(data_list, label):
                    for x in data_list:
                        d = x.get('dateTime')
                        if d:
                            if d not in master: master[d] = {"Steps":0,"Weight":0,"Fat%":0,"CalOut":0,"CalIn":0}
                            master[d][label] = x.get('value', 0)

                weave(s_raw, "Steps")
                weave(w_raw, "Weight")
                weave(f_raw, "Fat%")
                weave(co_raw, "CalOut")
                weave(ci_raw, "CalIn")

                # C. DISPLAY TABLE
                df = pd.DataFrame.from_dict(master, orient='index').reset_index()
                df.columns = ['Date', 'Steps', 'Weight', 'Fat%', 'CalOut', 'CalIn']
                df = df.sort_values(by='Date', ascending=False)

                st.subheader("1. Master Metrics Timeline")
                st.write("Checking for numerical values in Weight and Fat% columns:")
                st.table(df.head(20)) # Show latest 20 days

                st.divider()

                # D. RAW JSON INSPECTION
                st.subheader("2. Raw Data Inspection")
                c1, c2 = st.columns(2)
                with c1:
                    with st.expander("Raw Weight JSON"):
                        st.json(w_raw[:5])
                    with st.expander("Raw Fat% JSON"):
                        st.json(f_raw[:5])
                with c2:
                    with st.expander("Raw Calories In JSON"):
                        st.json(ci_raw[:5])
                    with st.expander("Raw Steps JSON"):
                        st.json(s_raw[:5])

            except Exception as e:
                st.error(f"Extraction failed: {e}")

else:
    # LANDING PAGE
    st.markdown("<h1 style='text-align: center; margin-top: 10rem;'>Kinetic Lab</h1>", unsafe_allow_html=True)
    url = f"https://www.fitbit.com/oauth2/authorize?response_type=code&client_id={CID}&scope=activity%20heartrate%20nutrition%20profile%20sleep%20weight&redirect_uri={URI}"
    st.markdown(f"<div style='text-align: center;'><a href='{url}' target='_blank' style='background-color: #38BDF8; color: white; padding: 1.2rem 3rem; border-radius: 50px; text-decoration: none; font-weight: 800;'>START DIAGNOSTIC SYNC</a></div>", unsafe_allow_html=True)

# --- END OF APP ---
