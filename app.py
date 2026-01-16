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
        prompt = f"You are an Elite Performance Coach. Context: {ctx}. Request: {q}. Provide numeric trends and a 3-step action plan."
        payload = {"contents": [{"parts": [{"text": prompt}]}], "safetySettings": [{"category": c, "threshold": "BLOCK_NONE"} for c in ["HARM_CATEGORY_HARASSMENT", "HARM_CATEGORY_HATE_SPEECH", "HARM_CATEGORY_SEXUALLY_EXPLICIT", "HARM_CATEGORY_DANGEROUS_CONTENT"]]}
        r = requests.post(gen_url, json=payload, timeout=90)
        return r.json()['candidates'][0]['content']['parts'][0]['text']
    except Exception as e: return f"Coach Snag: {str(e)}"

# 3. UI/UX STYLING (Professional Dark)
st.set_page_config(page_title="Performance AI", layout="wide")

st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');
        
        /* Global Background */
        .stApp {
            background-color: #0F172A;
            color: #F8FAFC;
        }
        html, body, [class*="css"] {
            font-family: 'Inter', sans-serif;
        }

        /* Sidebar: Deep Navy */
        [data-testid="stSidebar"] {
            background-color: #1E293B !important;
            border-right: 1px solid rgba(255, 255, 255, 0.1);
        }

        /* Glassmorphism Buttons - Uniform Length */
        div.stButton > button {
            width: 100% !important;
            background: rgba(255, 255, 255, 0.05) !important;
            backdrop-filter: blur(10px);
            -webkit-backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.1) !important;
            color: #38BDF8 !important;
            font-weight: 600;
            border-radius: 12px;
            padding: 10px;
            transition: 0.3s;
            text-transform: uppercase;
            font-size: 0.8rem;
        }
        
        div.stButton > button:hover {
            background: rgba(56, 189, 248, 0.1) !important;
            border: 1px solid #38BDF8 !important;
        }

        .step-label {
            font-weight: 800;
            font-size: 0.75rem;
            color: #94A3B8;
            text-transform: uppercase;
            letter-spacing: 1.5px;
            margin-top: 2rem;
            margin-bottom: 0.5rem;
        }
        
        .skeleton-card {
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid rgba(255, 255, 255, 0.05);
            border-radius: 16px;
            padding: 2rem;
            height: 150px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #475569;
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
    st.sidebar.markdown("<h2 style='color: white; font-weight: 800; margin-bottom:0;'>COACH</h2>", unsafe_allow_html=True)
    st.sidebar.markdown(f"<div style='color: #2DD4BF; font-weight: 600; font-size: 0.7rem; margin-bottom:2rem;'>● DATA STREAM ACTIVE</div>", unsafe_allow_html=True)
    
    st.sidebar.markdown("<div class='step-label'>Step 1. Let's look at trends</div>", unsafe_allow_html=True)
    if st.sidebar.button("ANALYSIS: WEIGHT & FAT"):
        st.session_state.ms.append({"role": "user", "content": "What is impacting my weight and body fat %? Analyze calories in/out, steps, and macros."})
    if st.sidebar.button("ANALYSIS: SLEEP QUALITY"):
        st.session_state.ms.append({"role": "user", "content": "What is having the most impact on my sleep score? Analyze activity, heart rate, and macros."})
    if st.sidebar.button("ANALYSIS: MUSCLE MASS"):
        st.session_state.ms.append({"role": "user", "content": "What is having the most impact on my muscle mass? Calculate lean mass from weight/fat and compare to protein."})

    st.sidebar.markdown("<div class='step-label'>Step 2. Coaching</div>", unsafe_allow_html=True)
    if st.sidebar.button("HOW DO I IMPROVE THIS?"):
        if st.session_state.ms:
            prev = st.session_state.ms[-1]["content"]
            st.session_state.ms.append({"role": "user", "content": f"Based on the analysis of '{prev}', give me a highly specific 3-step action plan."})
        else: st.sidebar.warning("Run a trend analysis first.")

    st.sidebar.divider()
    if st.sidebar.button("LOGOUT / RESET"):
        st.session_state.tk, st.session_state.cached_data, st.session_state.ms = None, None, []
        st.query_params.clear()
        st.rerun()

    # --- CENTER PAGE ---
    st.markdown("<h1 style='font-weight: 800; letter-spacing: -1px;'>Total Performance Analyst</h1>", unsafe_allow_html=True)

    if not st.session_state.cached_data:
        st.markdown("<p style='color: #94A3B8; margin-bottom: 2rem;'>Syncing required to build your 90-day performance matrix.</p>", unsafe_allow_html=True)
        c1, c2, c3 = st.columns(3)
        c1.markdown("<div class='skeleton-card'>Activity Timeline</div>", unsafe_allow_html=True)
        c2.markdown("<div class='skeleton-card'>Recovery Metrics</div>", unsafe_allow_html=True)
        c3.markdown("<div class='skeleton-card'>Nutrition Logs</div>", unsafe_allow_html=True)
        
        st.write("")
        if st.button("🔄 SYNC & WEAVE PERFORMANCE DATA"):
            with st.status("Fetching 90-day history...", expanded=True) as status:
                h = {"Authorization": f"Bearer {st.session_state.tk}"}
                try:
                    # Detailed fetching (Steps, Weight, Fat, Macros, Sleep)
                    s = requests.get("https://api.fitbit.com/1/user/-/activities/steps/date/today/90d.json", headers=h).json().get('activities-steps', [])
                    w = requests.get("https://api.fitbit.com/1/user/-/body/weight/date/today/90d.json", headers=h).json().get('body-weight', [])
                    f = requests.get("https://api.fitbit.com/1/user/-/body/fat/date/today/90d.json", headers=h).json().get('body-fat', [])
                    cin = requests.get("https://api.fitbit.com/1/user/-/foods/log/caloriesIn/date/today/90d.json", headers=h).json().get('foods-log-caloriesIn', [])
                    prt = requests.get("https://api.fitbit.com/1/user/-/foods/log/protein/date/today/90d.json", headers=h).json().get('foods-log-protein', [])
                    slp = requests.get("https://api.fitbit.com/1.2/user/-/sleep/list.json?afterDate=2024-01-01&limit=30&sort=desc", headers=h).json().get('sleep', [])
                    
                    # Merge Logic (The Foundry)
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

                    sleep_data = [{"date": x['dateOfSleep'], "score": x.get('efficiency', 0)} for x in slp]
                    st.session_state.cached_data = {"matrix": "\n".join(rows), "sleep": sleep_data}
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
                    with st.spinner("Analyzing..."):
                        ans = ask_ai(st.session_state.cached_data, st.session_state.ms[-1]["content"])
                        st.markdown(ans)
                        st.session_state.ms.append({"role": "assistant", "content": ans})
                        st.session_state.last_ans = len(st.session_state.ms)

        if p := st.chat_input("Ask a follow-up..."):
            st.session_state.ms.append({"role": "user", "content": p})
            st.rerun()

else:
    # LANDING PAGE (Centred button with Fitbit-friendly link)
    st.markdown("<h1 style='text-align: center; font-weight: 800; margin-top: 10rem; color: #F8FAFC;'>Performance AI</h1>", unsafe_allow_html=True)
    scope = "activity%20heartrate%20nutrition%20profile%20sleep%20weight"
    auth_url = f"https://www.fitbit.com/oauth2/authorize?response_type=code&client_id={CID}&scope={scope}&redirect_uri={URI}"
    
    # We use a proper Streamlit button style for the landing page link
    st.markdown(f"""
        <div style='text-align: center; margin-top: 2rem;'>
            <a href='{auth_url}' target='_blank' style='
                background-color: #38BDF8; 
                color: white; 
                padding: 1rem 2.5rem; 
                border-radius: 50px; 
                text-decoration: none; 
                font-weight: 700;
                font-size: 1.1rem;
                box-shadow: 0 4px 15px rgba(56, 189, 248, 0.4);
            '>CONNECT PERFORMANCE COACH</a>
        </div>
    """, unsafe_allow_html=True)

# --- END OF APP ---
