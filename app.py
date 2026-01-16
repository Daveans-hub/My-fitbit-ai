import streamlit as st
import requests
import base64
import json
from datetime import datetime, timedelta

# 1. LOAD SECRETS
CID, SEC, GKEY, URI = st.secrets["FITBIT_CLIENT_ID"], st.secrets["FITBIT_CLIENT_SECRET"], st.secrets["GEMINI_API_KEY"], st.secrets["YOUR_SITE_URL"]

# 2. PERFORMANCE COACH AI ENGINE
def ask_ai(ctx, q):
    try:
        list_url = f"https://generativelanguage.googleapis.com/v1beta/models?key={GKEY}"
        m_list = requests.get(list_url).json()
        available = [m['name'] for m in m_list.get('models', []) if 'generateContent' in m.get('supportedGenerationMethods', [])]
        model_path = next((m for m in available if "1.5-flash" in m), available[0])
        gen_url = f"https://generativelanguage.googleapis.com/v1beta/{model_path}:generateContent?key={GKEY}"
        
        prompt = f"You are an Elite Performance Coach. Data: {ctx}. User Request: {q}. Provide numeric trends and a 3-step plan."
        
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "safetySettings": [{"category": c, "threshold": "BLOCK_NONE"} for c in ["HARM_CATEGORY_HARASSMENT", "HARM_CATEGORY_HATE_SPEECH", "HARM_CATEGORY_SEXUALLY_EXPLICIT", "HARM_CATEGORY_DANGEROUS_CONTENT"]]
        }
        r = requests.post(gen_url, json=payload, timeout=90)
        return r.json()['candidates'][0]['content']['parts'][0]['text']
    except Exception as e:
        return f"Coach Snag: {str(e)}"

# 3. PAGE SETUP & DESIGN OVERHAUL (Suggestions Implemented)
st.set_page_config(page_title="Performance AI", layout="wide")

# Custom CSS for UI Improvements
st.markdown("""
    <style>
        /* 1. Typography: Import Inter and apply to whole app */
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;800&display=swap');
        html, body, [class*="css"]  {
            font-family: 'Inter', sans-serif;
        }

        /* 2. Sidebar Appearance (Deep Sky Blue) */
        [data-testid="stSidebar"] {
            background-color: #00BFFF;
        }

        /* 3. Glassmorphism Buttons: Semi-transparent blurred containers */
        div.stButton > button {
            width: 100% !important;
            height: 3.5em;
            background: rgba(255, 255, 255, 0.15) !important;
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            color: white !important;
            font-weight: 600;
            border: 1px solid rgba(255, 255, 255, 0.3) !important;
            border-radius: 12px;
            transition: all 0.3s ease;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            font-size: 0.85rem;
        }

        div.stButton > button:hover {
            background: rgba(255, 255, 255, 0.25) !important;
            border: 1px solid rgba(255, 255, 255, 0.5) !important;
        }

        /* 4. Bold Headings for Steps */
        .step-header {
            font-weight: 800;
            font-size: 1.1rem;
            color: white;
            margin-top: 1.5rem;
            margin-bottom: 0.5rem;
            letter-spacing: -0.5px;
        }
        
        .sidebar-title {
            color: white;
            font-weight: 800;
            font-size: 1.5rem;
            margin-bottom: 1rem;
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
    except: st.error("Login failed.")

# 5. MAIN APP
if st.session_state.tk:
    # --- SIDEBAR ---
    st.sidebar.markdown("<div class='sidebar-title'>COACH CONTROL</div>", unsafe_allow_html=True)
    st.sidebar.success("CONNECTED")
    
    # Suggestion 1: Clean Typography & Heavy Weights for Steps
    st.sidebar.markdown("<div class='step-header'>STEP 1. LET'S LOOK AT TRENDS</div>", unsafe_allow_html=True)
    
    # Suggestion 2: Consistent Iconography (Using clean labels instead of mixed emojis)
    if st.sidebar.button("ANALYSIS: WEIGHT & FAT"):
        st.session_state.ms.append({"role": "user", "content": "What is impacting my weight/fat%? Analyze calories and macros."})
    
    if st.sidebar.button("ANALYSIS: SLEEP QUALITY"):
        st.session_state.ms.append({"role": "user", "content": "What is impacting my sleep score? Analyze activity and heart rate."})
        
    if st.sidebar.button("ANALYSIS: MUSCLE MASS"):
        st.session_state.ms.append({"role": "user", "content": "What is impacting my muscle mass? Compare protein to lean mass."})

    st.sidebar.markdown("<div class='step-header'>STEP 2. COACHING</div>", unsafe_allow_html=True)
    if st.sidebar.button("HOW DO I IMPROVE THIS?"):
        if st.session_state.ms:
            prev = st.session_state.ms[-1]["content"]
            st.session_state.ms.append({"role": "user", "content": f"Based on the analysis of '{prev}', give me a detailed action plan."})
        else: st.sidebar.warning("Run a trend analysis first.")

    st.sidebar.divider()
    if st.sidebar.button("LOGOUT / RESET"):
        st.session_state.tk, st.session_state.cached_data, st.session_state.ms = None, None, []
        st.query_params.clear()
        st.rerun()

    # --- CENTER PAGE ---
    st.title("🔬 Total Performance Analyst")

    if not st.session_state.cached_data:
        st.info("Your performance matrix is ready to weave.")
        if st.button("🔄 SYNC & WEAVE 90-DAY DATASET"):
            with st.status("Fetching vitals...", expanded=True) as status:
                h = {"Authorization": f"Bearer {st.session_state.tk}"}
                try:
                    s = requests.get("https://api.fitbit.com/1/user/-/activities/steps/date/today/90d.json", headers=h).json().get('activities-steps', [])
                    w = requests.get("https://api.fitbit.com/1/user/-/body/weight/date/today/90d.json", headers=h).json().get('body-weight', [])
                    f = requests.get("https://api.fitbit.com/1/user/-/body/fat/date/today/90d.json", headers=h).json().get('body-fat', [])
                    
                    master = {}
                    for x in s:
                        d = x['dateTime']
                        if d not in master: master[d] = {"s":x['value'],"w":"0","f":"0"}
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

    # --- CHAT UI ---
    if st.session_state.cached_data:
        for m in st.session_state.ms:
            with st.chat_message(m["role"]): st.markdown(m["content"])
        
        if st.session_state.ms and st.session_state.ms[-1]["role"] == "user":
            if "l_ans" not in st.session_state or st.session_state.l_ans != len(st.session_state.ms):
                with st.chat_message("assistant"):
                    with st.spinner("Analyzing..."):
                        ans = ask_ai(st.session_state.cached_data, st.session_state.ms[-1]["content"])
                        st.markdown(ans)
                        st.session_state.ms.append({"role": "assistant", "content": ans})
                        st.session_state.l_ans = len(st.session_state.ms)

        if p := st.chat_input("Ask a specific question..."):
            st.session_state.ms.append({"role": "user", "content": p})
            st.rerun()

else:
    # LANDING PAGE
    st.title("🏃 Performance AI")
    url = f"https://www.fitbit.com/oauth2/authorize?response_type=code&client_id={CID}&scope=activity%20heartrate%20nutrition%20profile%20sleep%20weight&redirect_uri={URI}"
    st.markdown(f"### [🔗 Connect Performance Coach]({url})")

# --- END OF APP ---
