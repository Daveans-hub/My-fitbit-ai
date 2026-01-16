import streamlit as st
import requests
import base64
import json
from datetime import datetime, timedelta

# 1. LOAD SECRETS
CID, SEC, GKEY, URI = st.secrets["FITBIT_CLIENT_ID"], st.secrets["FITBIT_CLIENT_SECRET"], st.secrets["GEMINI_API_KEY"], st.secrets["YOUR_SITE_URL"]

# 2. ROBUST AI ENGINE (Self-Diagnosing)
def ask_ai(ctx, q):
    # Try the most stable production endpoint first
    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={GKEY}"
    
    payload = {
        "contents": [{"parts": [{"text": f"You are the Kinetic Lab AI Coach. Data: {ctx}. Request: {q}. Provide specific correlations and a 3-step plan."}]}],
        "safetySettings": [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
        ]
    }
    
    try:
        r = requests.post(url, json=payload, timeout=60)
        res = r.json()
        
        if "candidates" in res:
            return res["candidates"][0]["content"]["parts"][0]["text"]
        elif "error" in res:
            return f"Google API Error: {res['error']['message']}"
        else:
            return f"AI Refusal: Google blocked this response for safety or policy reasons. Raw: {json.dumps(res)}"
    except Exception as e:
        return f"System Snag: {str(e)}"

# 3. UI/UX STYLING (Kinetic Lab Branding)
st.set_page_config(page_title="Kinetic Lab", layout="wide")

st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;800&display=swap');
        
        .stApp {
            background-color: #0F172A !important;
            color: #F8FAFC !important;
            font-family: 'Inter', sans-serif;
        }

        [data-testid="stSidebar"] {
            background-color: #1E293B !important;
            border-right: 1px solid rgba(255, 255, 255, 0.05);
            min-width: 320px !important;
        }

        h1, h2, h3 {
            letter-spacing: 0.025em !important;
            font-weight: 800 !important;
        }

        /* Primary Action Button (Sync) */
        .stButton > button {
            background-color: #38BDF8 !important;
            color: white !important;
            font-weight: 600 !important;
            border: none !important;
            border-radius: 8px;
            width: 100% !important;
            padding: 12px !important;
        }

        /* Secondary Ghost Buttons (Sidebar) */
        [data-testid="stSidebar"] .stButton > button {
            background-color: transparent !important;
            color: #38BDF8 !important;
            border: 1px solid rgba(56, 189, 248, 0.4) !important;
            padding: 10px !important;
        }
        
        [data-testid="stSidebar"] .stButton > button:hover {
            background-color: rgba(56, 189, 248, 0.1) !important;
            border: 1px solid #38BDF8 !important;
        }

        .step-header {
            font-weight: 800;
            font-size: 0.75rem;
            color: #94A3B8;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            margin-top: 2rem;
            margin-bottom: 0.5rem;
        }
        
        .status-dot {
            color: #2DD4BF;
            font-weight: 600;
            font-size: 0.7rem;
            margin-bottom: 2rem;
        }
    </style>
    """, unsafe_allow_html=True)

if "tk" not in st.session_state: st.session_state.tk = None
if "cached_data" not in st.session_state: st.session_state.cached_data = None
if "ms" not in st.session_state: st.session_state.ms = []

# 4. LOGIN LOGIC
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
    except: st.error("Authentication failed.")

# 5. MAIN APP
if st.session_state.tk:
    # Sidebar Navigation
    st.sidebar.markdown("<h2 style='color: white; margin-bottom:0;'>KINETIC LAB</h2>", unsafe_allow_html=True)
    st.sidebar.markdown(f"<div class='status-dot'>● DATA STREAM ACTIVE</div>", unsafe_allow_html=True)
    
    st.sidebar.markdown("<div class='step-header'>Step 1. Looking at trends</div>", unsafe_allow_html=True)
    if st.sidebar.button("Weight & Fat Impact"):
        st.session_state.ms.append({"role": "user", "content": "Analyze my weight and body fat trends."})
    if st.sidebar.button("Sleep Quality Impact"):
        st.session_state.ms.append({"role": "user", "content": "Analyze my sleep quality and what drives my score."})
    if st.sidebar.button("Muscle Mass Impact"):
        st.session_state.ms.append({"role": "user", "content": "Analyze my muscle mass growth vs activity."})

    st.sidebar.markdown("<div class='step-header'>Step 2. Levelling up</div>", unsafe_allow_html=True)
    if st.sidebar.button("🚀 HOW DO I IMPROVE?"):
        if st.session_state.ms:
            topic = st.session_state.ms[-1]["content"]
            st.session_state.ms.append({"role": "user", "content": f"Give me a 3-step action plan for '{topic}'."})
        else: st.sidebar.warning("Run analysis first.")

    st.sidebar.divider()
    if st.sidebar.button("Logout"):
        st.session_state.tk, st.session_state.cached_data, st.session_state.ms = None, None, []
        st.query_params.clear()
        st.rerun()

    # Main Panel
    st.markdown("<h1>Kinetic Performance Analyst</h1>", unsafe_allow_html=True)

    if not st.session_state.cached_data:
        st.markdown("<p style='color: #94A3B8;'>Ready to build your 90-day performance matrix.</p>", unsafe_allow_html=True)
        if st.button("🔄 SYNC & WEAVE DATASET"):
            with st.status("Reading Fitbit Vitals...", expanded=True) as status:
                h = {"Authorization": f"Bearer {st.session_state.tk}"}
                try:
                    # Multi-Metric Extraction
                    s = requests.get("https://api.fitbit.com/1/user/-/activities/steps/date/today/90d.json", headers=h).json().get('activities-steps', [])
                    w = requests.get("https://api.fitbit.com/1/user/-/body/weight/date/today/90d.json", headers=h).json().get('body-weight', [])
                    f = requests.get("https://api.fitbit.com/1/user/-/body/fat/date/today/90d.json", headers=h).json().get('body-fat', [])
                    
                    master = {}
                    for x in s:
                        d = x['dateTime']
                        master[d] = {"s":x['value'],"w":"0","f":"0"}
                    for x in w:
                        if x['date'] in master: master[x['date']]['w'] = x['weight']
                    for x in f:
                        if x['date'] in master: master[x['date']]['f'] = x['fat']

                    rows = ["Date,Steps,Weight,Fat%"]
                    for d in sorted(master.keys(), reverse=True):
                        v = master[d]
                        rows.append(f"{d},{v['s']},{v['w']},{v['f']}")

                    st.session_state.cached_data = "\n".join(rows)
                    status.update(label="✅ Weaving Complete!", state="complete")
                    st.rerun()
                except Exception as e: st.error(f"Sync failed: {e}")

    # Chat Interaction
    if st.session_state.cached_data:
        for m in st.session_state.ms:
            with st.chat_message(m["role"]): st.markdown(m["content"])
        
        if st.session_state.ms and st.session_state.ms[-1]["role"] == "user":
            if "last_ans" not in st.session_state or st.session_state.last_ans != len(st.session_state.ms):
                with st.chat_message("assistant"):
                    with st.spinner("Analyzing..."):
                        ans = ask_ai(st.session_state.cached_data, st.session_state.ms[-1]["content"])
                        st.markdown(ans)
                        st.session_state.ms.append({"role": "assistant", "content": ans})
                        st.session_state.last_ans = len(st.session_state.ms)

        if p := st.chat_input("Query the Kinetic Lab..."):
            st.session_state.ms.append({"role": "user", "content": p})
            st.rerun()

else:
    # Premium Landing Page
    st.markdown("<h1 style='text-align: center; margin-top: 10rem; font-size: 4rem;'>Kinetic Lab</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #94A3B8; font-size: 1.2rem; margin-bottom: 3rem;'>Precision metrics for high-performance health.</p>", unsafe_allow_html=True)
    auth_url = f"https://www.fitbit.com/oauth2/authorize?response_type=code&client_id={CID}&scope=activity%20heartrate%20nutrition%20profile%20sleep%20weight&redirect_uri={URI}"
    st.markdown(f"<div style='text-align: center;'><a href='{auth_url}' target='_blank' style='background-color: #38BDF8; color: white; padding: 1.2rem 3rem; border-radius: 50px; text-decoration: none; font-weight: 800; box-shadow: 0 10px 30px rgba(56, 189, 248, 0.3);'>CONNECT PERFORMANCE COACH</a></div>", unsafe_allow_html=True)

# --- END OF APP ---
