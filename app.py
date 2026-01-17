import streamlit as st
import requests
import base64
import json
from datetime import datetime, timedelta

# 1. LOAD SECRETS
CID, SEC, GKEY, URI = st.secrets["FITBIT_CLIENT_ID"], st.secrets["FITBIT_CLIENT_SECRET"], st.secrets["GEMINI_API_KEY"], st.secrets["YOUR_SITE_URL"]

# 2. AUTO-DISCOVERY AI ENGINE
def ask_ai(ctx, q):
    try:
        list_url = f"https://generativelanguage.googleapis.com/v1beta/models?key={GKEY}"
        m_list = requests.get(list_url).json()
        available = [m['name'] for m in m_list.get('models', []) if 'generateContent' in m.get('supportedGenerationMethods', [])]
        model_path = next((m for m in available if "1.5-flash" in m), available[0])
        gen_url = f"https://generativelanguage.googleapis.com/v1beta/{model_path}:generateContent?key={GKEY}"
        
        prompt = f"""
        You are the Kinetic Lab AI Coach. Analyze the provided health data.
        
        RULES:
        - Calculate Muscle Mass = Weight * (1 - (Fat% / 100)).
        - Analyze the relationship between Macros (Protein/Carbs/Fats) and performance/body composition.
        - Analyze Sleep Score against activity levels.
        - Be specific, numeric, and provide a 3-step action plan.
        
        DATASET:
        {ctx}
        
        REQUEST:
        {q}
        """
        payload = {"contents": [{"parts": [{"text": prompt}]}], "safetySettings": [{"category": c, "threshold": "BLOCK_NONE"} for c in ["HARM_CATEGORY_HARASSMENT", "HARM_CATEGORY_HATE_SPEECH", "HARM_CATEGORY_SEXUALLY_EXPLICIT", "HARM_CATEGORY_DANGEROUS_CONTENT"]]}
        r = requests.post(gen_url, json=payload, timeout=90)
        return r.json()['candidates'][0]['content']['parts'][0]['text']
    except Exception as e: return f"Coach Snag: {str(e)}"

# 3. HIGH-CONTRAST UI STYLING (#FFFFFF White Text)
st.set_page_config(page_title="Kinetic Lab", layout="wide")
st.markdown(f"""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;800&display=swap');
        .stApp, [data-testid="stAppViewContainer"] {{ background-color: #0F172A !important; font-family: 'Inter', sans-serif; }}
        html, body, [class*="css"], .stMarkdown, p, h1, h2, h3, li, span, label, div, [data-testid="stChatMessage"] p {{ color: #FFFFFF !important; }}
        [data-testid="stSidebar"] {{ background-color: #1E293B !important; border-right: 1px solid rgba(255, 255, 255, 0.05); min-width: 320px !important; }}
        .stButton button {{
            width: 100% !important; display: block !important; background: rgba(255, 255, 255, 0.05) !important;
            backdrop-filter: blur(10px); border: 1px solid rgba(56, 189, 248, 0.4) !important;
            color: #38BDF8 !important; font-weight: 600 !important; border-radius: 10px !important;
            text-transform: uppercase !important; height: 3.5em !important; margin-bottom: 8px !important;
        }}
        .stButton button:hover {{ background: rgba(56, 189, 248, 0.1) !important; border-color: #38BDF8 !important; }}
        .step-header {{ font-weight: 800; font-size: 0.85rem; color: #F8FAFC !important; text-transform: uppercase; letter-spacing: 0.05em; margin-top: 2rem; margin-bottom: 0.8rem; }}
    </style>
    """, unsafe_allow_html=True)

if "tk" not in st.session_state: st.session_state.tk = None
if "cached_data" not in st.session_state: st.session_state.cached_data = None
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
    st.sidebar.markdown(f"<div style='color: #2DD4BF; font-weight: 600; font-size: 0.7rem;'>● DATA STREAM ACTIVE</div>", unsafe_allow_html=True)
    
    st.sidebar.markdown("<div class='step-header'>Step 1. Looking at trends</div>", unsafe_allow_html=True)
    if st.sidebar.button("Weight & Fat Impact"):
        st.session_state.ms.append({"role": "user", "content": "Analyze my weight and body fat trends against my calories and macros."})
    if st.sidebar.button("Sleep Quality Impact"):
        st.session_state.ms.append({"role": "user", "content": "Analyze my sleep score drivers. How do activity and macros affect my rest?"})
    if st.sidebar.button("Muscle Mass Impact"):
        st.session_state.ms.append({"role": "user", "content": "Analyze my muscle mass growth vs my protein intake levels."})

    st.sidebar.markdown("<div class='step-header'>Step 2. Levelling up</div>", unsafe_allow_html=True)
    if st.sidebar.button("🚀 HOW DO I IMPROVE?"):
        if st.session_state.ms:
            t = st.session_state.ms[-1]["content"]
            st.session_state.ms.append({"role": "user", "content": f"Based on the trends in '{t}', give me a 3-step action plan to improve."})
        else: st.sidebar.warning("Analyze a trend first.")

    st.sidebar.divider()
    if st.sidebar.button("Logout"):
        st.session_state.tk, st.session_state.cached_data, st.session_state.ms = None, None, []
        st.rerun()

    st.markdown("<h1 style='letter-spacing: 0.025em;'>Kinetic Performance Analyst</h1>", unsafe_allow_html=True)

    if not st.session_state.cached_data:
        if st.button("🔄 SYNC & WEAVE PERFORMANCE DATASET"):
            with st.status("Gathering performance metrics...", expanded=True) as status:
                h = {"Authorization": f"Bearer {st.session_state.tk}"}
                try:
                    # 1. Fetch Time-Series
                    s = requests.get("https://api.fitbit.com/1/user/-/activities/steps/date/today/6m.json", headers=h).json().get('activities-steps', [])
                    w = requests.get("https://api.fitbit.com/1/user/-/body/weight/date/today/6m.json", headers=h).json().get('body-weight', [])
                    f = requests.get("https://api.fitbit.com/1/user/-/body/fat/date/today/6m.json", headers=h).json().get('body-fat', [])
                    co = requests.get("https://api.fitbit.com/1/user/-/activities/calories/date/today/6m.json", headers=h).json().get('activities-calories', [])
                    sl = requests.get("https://api.fitbit.com/1.2/user/-/sleep/list.json?afterDate=2024-01-01&limit=30&sort=desc", headers=h).json().get('sleep', [])
                    
                    # 2. Daily Macro Fetch (Last 30 Days)
                    macros = []
                    for i in range(1, 31):
                        d_str = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
                        log = requests.get(f"https://api.fitbit.com/1/user/-/foods/log/date/{d_str}.json", headers=h).json().get('summary', {})
                        if log and log.get('calories', 0) > 0:
                            macros.append({"d": d_str, "p": log.get('protein', 0), "c": log.get('carbs', 0), "f": log.get('fat', 0), "in": log.get('calories', 0)})

                    # 3. Weaver
                    master = {}
                    def weave(d_list, label):
                        for x in d_list:
                            d = x.get('dateTime') or x.get('date')
                            if d:
                                if d not in master: master[d] = {"s":0,"w":0,"f":0,"co":0,"in":0,"p":0,"c":0,"f_g":0,"score":0}
                                master[d][label] = x.get('value', 0)

                    weave(s,'s'); weave(w,'w'); weave(f,'f'); weave(co,'co')
                    for m in macros:
                        if m['d'] in master: master[m['d']].update({"in":m['in'],"p":m['p'],"c":m['c'],"f_g":m['f']})
                    for sess in sl:
                        if sess['dateOfSleep'] in master: master[sess['dateOfSleep']]['score'] = sess.get('efficiency', 0)

                    rows = ["Date,Steps,Weight,Fat%,CalOut,CalIn,Protein,Carbs,FatGrams,SleepScore"]
                    for d in sorted(master.keys(), reverse=True):
                        v = master[d]
                        rows.append(f"{d},{v['s']},{v['w']},{v['f']},{v['co']},{v['in']},{v['p']},{v['c']},{v['f_g']},{v['score']}")

                    st.session_state.cached_data = "\n".join(rows)
                    status.update(label="✅ Ready!", state="complete")
                    st.rerun()
                except Exception as e: st.error(f"Sync failed: {e}")

    if st.session_state.cached_data:
        for m in st.session_state.ms:
            with st.chat_message(m["role"]): st.markdown(m["content"])
        
        if st.session_state.ms and st.session_state.ms[-1]["role"] == "user":
            if "l_ans" not in st.session_state or st.session_state.l_ans != len(st.session_state.ms):
                with st.chat_message("assistant"):
                    with st.spinner("Crunching performance data..."):
                        ans = ask_ai(st.session_state.cached_data, st.session_state.ms[-1]["content"])
                        st.markdown(ans)
                        st.session_state.ms.append({"role": "assistant", "content": ans})
                        st.session_state.last_ans = len(st.session_state.ms)
        
        if p := st.chat_input("Ask Kinetic Lab..."):
            st.session_state.ms.append({"role": "user", "content": p})
            st.rerun()
else:
    st.markdown("<h1 style='text-align: center; margin-top: 10rem; font-size: 4rem; color: #F8FAFC;'>Kinetic Lab</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #94A3B8; font-size: 1.2rem; margin-bottom: 3rem;'>Precision metrics for high-performance health.</p>", unsafe_allow_html=True)
    auth_url = f"https://www.fitbit.com/oauth2/authorize?response_type=code&client_id={CID}&scope=activity%20heartrate%20nutrition%20profile%20sleep%20weight&redirect_uri={URI}"
    st.markdown(f"<div style='text-align: center;'><a href='{auth_url}' target='_blank' style='background-color: #38BDF8; color: white; padding: 1.2rem 3rem; border-radius: 50px; text-decoration: none; font-weight: 800; box-shadow: 0 10px 30px rgba(56, 189, 248, 0.3);'>CONNECT PERFORMANCE COACH</a></div>", unsafe_allow_html=True)
