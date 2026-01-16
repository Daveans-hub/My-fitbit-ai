import streamlit as st
import requests
import base64
import json
import pandas as pd
from datetime import datetime, timedelta

# 1. LOAD SECRETS
CID, SEC, GKEY, URI = st.secrets["FITBIT_CLIENT_ID"], st.secrets["FITBIT_CLIENT_SECRET"], st.secrets["GEMINI_API_KEY"], st.secrets["YOUR_SITE_URL"]

# 2. OPTIMIZED AI ENGINE
def ask_ai(ctx_table, q):
    try:
        # We target the v1beta endpoint directly for speed and reliability
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GKEY}"
        
        prompt = f"""
        You are the Kinetic Lab AI Coach. 
        Analyze the following 90-day health dataset (CSV format):
        {ctx_table}
        
        User Request: {q}
        
        RULES:
        - Calculate Muscle Mass = Weight * (1 - (Fat% / 100)).
        - Be highly numeric. Show correlations (r-values if possible).
        - Provide a 3-step action plan for Step 2.
        - IGNORE days where Weight or Calories are 0.
        """
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "safetySettings": [{"category": c, "threshold": "BLOCK_NONE"} for c in ["HARM_CATEGORY_HARASSMENT", "HARM_CATEGORY_HATE_SPEECH", "HARM_CATEGORY_SEXUALLY_EXPLICIT", "HARM_CATEGORY_DANGEROUS_CONTENT"]]
        }
        # Increased timeout to 2 minutes for heavy math
        r = requests.post(url, json=payload, timeout=120)
        res = r.json()
        
        if "candidates" in res:
            return res["candidates"][0]["content"]["parts"][0]["text"]
        else:
            return f"AI Snag: {json.dumps(res)}"
    except Exception as e:
        return f"System Snag: {str(e)}"

# 3. HIGH-CONTRAST UI (Pure White Text #FFFFFF)
st.set_page_config(page_title="Kinetic Lab", layout="wide")
st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');
        .stApp, [data-testid="stAppViewContainer"] { background-color: #0F172A !important; font-family: 'Inter', sans-serif; }
        
        /* Global White Text Force */
        html, body, .stMarkdown, p, h1, h2, h3, li, span, label, div, [data-testid="stChatMessage"] p { 
            color: #FFFFFF !important; 
        }

        [data-testid="stSidebar"] { 
            background-color: #1E293B !important; 
            border-right: 1px solid rgba(255, 255, 255, 0.05); 
            min-width: 320px !important; 
        }

        .stButton button {
            width: 100% !important; background: rgba(255, 255, 255, 0.05) !important;
            backdrop-filter: blur(10px); border: 1px solid rgba(56, 189, 248, 0.4) !important;
            color: #38BDF8 !important; font-weight: 600 !important; border-radius: 10px !important;
            text-transform: uppercase !important; height: 3.5em !important; margin-bottom: 8px !important;
        }
        .stButton button:hover { background: rgba(56, 189, 248, 0.1) !important; border-color: #38BDF8 !important; }
        .step-header { font-weight: 800; font-size: 0.85rem; color: #94A3B8 !important; text-transform: uppercase; letter-spacing: 0.05em; margin-top: 2rem; margin-bottom: 0.5rem; }
    </style>
    """, unsafe_allow_html=True)

if "tk" not in st.session_state: st.session_state.tk = None
if "data" not in st.session_state: st.session_state.data = None
if "ms" not in st.session_state: st.session_state.ms = []

# 4. LOGIN
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

# 5. MAIN APP
if st.session_state.tk:
    st.sidebar.markdown("<h2 style='font-weight: 800;'>KINETIC LAB</h2>", unsafe_allow_html=True)
    st.sidebar.markdown("<div style='color: #2DD4BF; font-weight: 600; font-size: 0.7rem;'>● DATA STREAM ACTIVE</div>", unsafe_allow_html=True)
    
    st.sidebar.markdown("<div class='step-header'>Step 1. Looking at trends</div>", unsafe_allow_html=True)
    if st.sidebar.button("Weight & Fat Impact"):
        st.session_state.ms.append({"role": "user", "content": "What is having the most impact on my weight and body fat %? Analyze my calories, steps, and fat % trends."})
    if st.sidebar.button("Sleep Quality Impact"):
        st.session_state.ms.append({"role": "user", "content": "What is having the most impact on my sleep score? Analyze activity and heart rate."})
    if st.sidebar.button("Muscle Mass Impact"):
        st.session_state.ms.append({"role": "user", "content": "Analyze my calculated muscle mass trends over the last 90 days."})

    st.sidebar.markdown("<div class='step-header'>Step 2. Levelling up</div>", unsafe_allow_html=True)
    if st.sidebar.button("🚀 HOW DO I IMPROVE?"):
        if st.session_state.ms:
            t = st.session_state.ms[-1]["content"]
            st.session_state.ms.append({"role": "user", "content": f"How do I level up results for '{t}'? Give me a 3-step action plan."})
        else: st.sidebar.warning("Analyze a trend first.")

    st.sidebar.divider()
    if st.sidebar.button("Logout"):
        st.session_state.tk, st.session_state.data, st.session_state.ms = None, None, []
        st.query_params.clear()
        st.rerun()

    st.title("🔬 Kinetic Performance Analyst")

    if not st.session_state.data:
        if st.button("🔄 SYNC & WEAVE 90-DAY DATASET"):
            with st.status("Gathering vitals...", expanded=True) as status:
                h = {"Authorization": f"Bearer {st.session_state.tk}"}
                try:
                    # Pull 90 days (much faster than 180)
                    s = requests.get("https://api.fitbit.com/1/user/-/activities/steps/date/today/90d.json", headers=h).json().get('activities-steps', [])
                    w = requests.get("https://api.fitbit.com/1/user/-/body/weight/date/today/90d.json", headers=h).json().get('body-weight', [])
                    f = requests.get("https://api.fitbit.com/1/user/-/body/fat/date/today/90d.json", headers=h).json().get('body-fat', [])
                    ci = requests.get("https://api.fitbit.com/1/user/-/foods/log/caloriesIn/date/today/90d.json", headers=h).json().get('foods-log-caloriesIn', [])
                    
                    master = {}
                    for x in s:
                        d = x['dateTime']
                        master[d] = {"s":x['value'],"w":0,"f":0,"ci":0}
                    for x in w:
                        if x['dateTime'] in master: master[x['dateTime']]['w'] = x['value']
                    for x in f:
                        if x['dateTime'] in master: master[x['dateTime']]['f'] = x['value']
                    for x in ci:
                        if x['dateTime'] in master: master[x['dateTime']]['ci'] = x['value']

                    rows = ["Date,Steps,Weight,Fat%,CalIn"]
                    for d in sorted(master.keys(), reverse=True):
                        v = master[d]
                        rows.append(f"{d},{v['s']},{v['w']},{v['f']},{v['ci']}")

                    st.session_state.data = "\n".join(rows)
                    status.update(label="✅ Ready!", state="complete")
                    st.rerun()
                except Exception as e: st.error(f"Sync failed: {e}")

    if st.session_state.data:
        for m in st.session_state.ms:
            with st.chat_message(m["role"]): st.markdown(m["content"])
        
        if st.session_state.ms and st.session_state.ms[-1]["role"] == "user":
            if "l_ans" not in st.session_state or st.session_state.l_ans != len(st.session_state.ms):
                with st.chat_message("assistant"):
                    with st.spinner("Crunching data... this takes about 30 seconds."):
                        ans = ask_ai(st.session_state.data, st.session_state.ms[-1]["content"])
                        st.markdown(ans)
                        st.session_state.ms.append({"role": "assistant", "content": ans})
                        st.session_state.last_ans = len(st.session_state.ms)
        
        if p := st.chat_input("Query Kinetic Lab..."):
            st.session_state.ms.append({"role": "user", "content": p})
            st.rerun()

else:
    # LANDING PAGE
    st.markdown("<h1 style='text-align: center; margin-top: 10rem; font-size: 4rem;'>Kinetic Lab</h1>", unsafe_allow_html=True)
    auth_url = f"https://www.fitbit.com/oauth2/authorize?response_type=code&client_id={CID}&scope=activity%20heartrate%20nutrition%20profile%20sleep%20weight&redirect_uri={URI}"
    st.markdown(f"<div style='text-align: center;'><a href='{auth_url}' target='_blank' style='background-color: #38BDF8; color: white; padding: 1.2rem 3rem; border-radius: 50px; text-decoration: none; font-weight: 800;'>CONNECT PERFORMANCE COACH</a></div>", unsafe_allow_html=True)

# --- END OF APP ---
