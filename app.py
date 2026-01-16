import streamlit as st
import requests
import base64
import json
from datetime import datetime, timedelta

# 1. LOAD SECRETS
CID, SEC, GKEY, URI = st.secrets["FITBIT_CLIENT_ID"], st.secrets["FITBIT_CLIENT_SECRET"], st.secrets["GEMINI_API_KEY"], st.secrets["YOUR_SITE_URL"]

# 2. THE SELF-HEALING PERFORMANCE ENGINE
def ask_ai(ctx, q):
    try:
        # Discovery: Find the correct model for this key
        list_url = f"https://generativelanguage.googleapis.com/v1beta/models?key={GKEY}"
        available = [m['name'] for m in requests.get(list_url).json().get('models', []) if 'generateContent' in m.get('supportedGenerationMethods', [])]
        model_path = next((m for m in available if "1.5-flash" in m), available[0])
        gen_url = f"https://generativelanguage.googleapis.com/v1beta/{model_path}:generateContent?key={GKEY}"
        
        prompt = f"You are the Kinetic Lab AI Coach. Analyze this health matrix: {ctx}. User Request: {q}. Provide specific numeric correlations and a 3-step improvement plan."
        payload = {"contents": [{"parts": [{"text": prompt}]}], "safetySettings": [{"category": c, "threshold": "BLOCK_NONE"} for c in ["HARM_CATEGORY_HARASSMENT", "HARM_CATEGORY_HATE_SPEECH", "HARM_CATEGORY_SEXUALLY_EXPLICIT", "HARM_CATEGORY_DANGEROUS_CONTENT"]]}
        r = requests.post(gen_url, json=payload, timeout=90)
        return r.json()['candidates'][0]['content']['parts'][0]['text']
    except Exception as e: return f"Coach Snag: {str(e)}"

# 3. HIGH-CONTRAST UI ENHANCEMENTS
st.set_page_config(page_title="Kinetic Lab", layout="wide")

st.markdown("""
    <style>
        /* Import Inter Font */
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;800&display=swap');
        
        /* 1. High-Contrast Color Palette */
        .stApp {
            background-color: #0F172A !important; /* Deep Slate */
            color: #F8FAFC !important; /* Near White Primary Text */
            font-family: 'Inter', sans-serif;
        }

        /* 2. Sidebar: Dark Blue-Grey */
        [data-testid="stSidebar"] {
            background-color: #1E293B !important;
            border-right: 1px solid rgba(255, 255, 255, 0.05);
            min-width: 320px !important;
        }

        /* 3. Typography & Layout */
        h1, h2, h3 {
            letter-spacing: 0.025em !important; /* Added Tracking */
            font-weight: 800 !important;
        }
        
        .muted-text {
            color: #94A3B8; /* Soft Grey Secondary Text */
            font-size: 0.9rem;
        }

        /* 4. Button Hierarchy Enhancements */
        /* Primary Action: Solid Sky Blue */
        div.stButton > button:first-child {
            background-color: #38BDF8 !important;
            color: white !important;
            font-weight: 600 !important;
            border: none !important;
            padding: 12px !important;
            border-radius: 8px;
            width: 100% !important;
        }

        /* Secondary Actions (Sidebar): Ghost Style */
        [data-testid="stSidebar"] div.stButton > button {
            background-color: transparent !important;
            color: #38BDF8 !important;
            border: 1px solid rgba(56, 189, 248, 0.4) !important;
            font-weight: 500 !important;
            letter-spacing: 0.01em;
            padding: 10px !important;
            transition: 0.2s all ease;
        }
        
        [data-testid="stSidebar"] div.stButton > button:hover {
            background-color: rgba(56, 189, 248, 0.1) !important;
            border: 1px solid #38BDF8 !important;
        }

        /* Section Header Labels */
        .step-header {
            font-weight: 800;
            font-size: 0.75rem;
            color: #94A3B8;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            margin-top: 2rem;
            margin-bottom: 0.5rem;
        }
        
        .status-indicator {
            color: #2DD4BF; /* Success Teal */
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

# 5. MAIN APP (LOGGED IN)
if st.session_state.tk:
    # --- SIDEBAR ---
    st.sidebar.markdown("<h2 style='color: white; margin-bottom:0;'>KINETIC LAB</h2>", unsafe_allow_html=True)
    st.sidebar.markdown(f"<div class='status-indicator'>● DATA STREAM ACTIVE</div>", unsafe_allow_html=True)
    
    st.sidebar.markdown("<div class='step-header'>Step 1. Looking at trends</div>", unsafe_allow_html=True)
    if st.sidebar.button("Weight & Fat Impact"):
        st.session_state.ms.append({"role": "user", "content": "Analyze my weight and body fat % impact factors using calories, steps, and macros."})
    if st.sidebar.button("Sleep Quality Impact"):
        st.session_state.ms.append({"role": "user", "content": "Analyze my sleep score impact factors using heart rate, activity, and nutrition."})
    if st.sidebar.button("Muscle Mass Impact"):
        st.session_state.ms.append({"role": "user", "content": "Analyze my muscle mass (Weight * (1 - Fat%)) vs my protein and activity levels."})

    st.sidebar.markdown("<div class='step-header'>Step 2. Levelling up</div>", unsafe_allow_html=True)
    if st.sidebar.button("🚀 HOW DO I IMPROVE?"):
        if st.session_state.ms:
            topic = st.session_state.ms[-1]["content"]
            st.session_state.ms.append({"role": "user", "content": f"Based on the analysis of '{topic}', provide a specific 3-step performance plan."})
        else: st.sidebar.warning("Run a trend analysis first.")

    st.sidebar.divider()
    if st.sidebar.button("LOGOUT"):
        st.session_state.tk, st.session_state.cached_data, st.session_state.ms = None, None, []
        st.query_params.clear()
        st.rerun()

    # --- MAIN PAGE ---
    st.markdown("<h1>Kinetic Performance Analyst</h1>", unsafe_allow_html=True)

    if not st.session_state.cached_data:
        st.markdown("<p class='muted-text'>Your performance matrix is ready to weave from your 90-day history.</p>", unsafe_allow_html=True)
        if st.button("🔄 SYNC & WEAVE PERFORMANCE DATA"):
            with st.status("Reading 90-day vitals...", expanded=True) as status:
                h = {"Authorization": f"Bearer {st.session_state.tk}"}
                try:
                    # Multi-Metric Extraction (Fixed Keys)
                    s = requests.get("https://api.fitbit.com/1/user/-/activities/steps/date/today/90d.json", headers=h).json().get('activities-steps', [])
                    w = requests.get("https://api.fitbit.com/1/user/-/body/weight/date/today/90d.json", headers=h).json().get('body-weight', [])
                    f = requests.get("https://api.fitbit.com/1/user/-/body/fat/date/today/90d.json", headers=h).json().get('body-fat', [])
                    cin = requests.get("https://api.fitbit.com/1/user/-/foods/log/caloriesIn/date/today/90d.json", headers=h).json().get('foods-log-caloriesIn', [])
                    prt = requests.get("https://api.fitbit.com/1/user/-/foods/log/protein/date/today/90d.json", headers=h).json().get('foods-log-protein', [])
                    slp = requests.get("https://api.fitbit.com/1.2/user/-/sleep/list.json?afterDate=2024-01-01&limit=30&sort=desc", headers=h).json().get('sleep', [])
                    
                    # Weaving logic
                    master = {}
                    def ingest(d_list, key, val_key):
                        for x in d_list:
                            d = x.get('dateTime') or x.get('date')
                            if d:
                                if d not in master: master[d] = {"s":"0","w":"0","f":"0","c":"0","p":"0"}
                                master[d][key] = str(x.get(val_key, 0))

                    ingest(s,'s','value'); ingest(w,'w','weight'); ingest(f,'f','fat'); ingest(cin,'c','value'); ingest(prt,'p','value')

                    rows = ["Date,Steps,Weight,Fat%,Calories,Protein"]
                    for d in sorted(master.keys(), reverse=True):
                        v = master[d]
                        rows.append(f"{d},{v['s']},{v['w']},{v['f']},{v['c']},{v['p']}")

                    st.session_state.cached_data = {"matrix": "\n".join(rows), "sleep": [{"date": x['dateOfSleep'], "score": x.get('efficiency', 0)} for x in slp]}
                    status.update(label="✅ Weaving Complete!", state="complete")
                    st.rerun()
                except Exception as e: st.error(f"Sync failed: {e}")

    # --- CHAT ---
    if st.session_state.cached_data:
        for m in st.session_state.ms:
            with st.chat_message(m["role"]): st.markdown(m["content"])
        
        if st.session_state.ms and st.session_state.ms[-1]["role"] == "user":
            if "l_ans" not in st.session_state or st.session_state.l_ans != len(st.session_state.ms):
                with st.chat_message("assistant"):
                    with st.spinner("Kinetic Engine analyzing..."):
                        ans = ask_ai(st.session_state.cached_data, st.session_state.ms[-1]["content"])
                        st.markdown(ans)
                        st.session_state.ms.append({"role": "assistant", "content": ans})
                        st.session_state.last_ans = len(st.session_state.ms)

        if p := st.chat_input("Query the Kinetic Lab..."):
            st.session_state.ms.append({"role": "user", "content": p})
            st.rerun()

else:
    # LANDING PAGE
    st.markdown(f"""
        <div style='text-align: center; margin-top: 10rem;'>
            <h1 style='font-size: 4rem; color: #F8FAFC; margin-bottom: 0.5rem;'>Kinetic Lab</h1>
            <p style='color: #94A3B8; font-size: 1.2rem; margin-bottom: 3rem;'>Precision metrics for high-performance health.</p>
            <a href='https://www.fitbit.com/oauth2/authorize?response_type=code&client_id={CID}&scope=activity%20heartrate%20nutrition%20profile%20sleep%20weight&redirect_uri={URI}' 
               target='_blank' 
               style='background-color: #38BDF8; color: white; padding: 1.2rem 3rem; border-radius: 50px; text-decoration: none; font-weight: 800; font-size: 1.1rem; box-shadow: 0 10px 30px rgba(56, 189, 248, 0.3);'>
               CONNECT PERFORMANCE COACH
            </a>
        </div>
    """, unsafe_allow_html=True)

# --- END OF APP ---
