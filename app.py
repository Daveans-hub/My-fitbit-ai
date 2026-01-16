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
        
        prompt = f"""
        You are an Elite Performance Coach. Analyze the CSV dataset provided.
        
        REQUIRED MATH:
        - Calculate 'Muscle Mass' for every row where Weight and Fat% are not 0: Weight * (1 - (Fat% / 100)).
        
        COACHING RULES:
        - If you see numbers in the table, USE THEM.
        - Identify lead indicators (e.g., 'Your sleep score improves when your calories are below X').
        - Provide a clear 3-step action plan if asked.
        
        DATASET:
        {ctx}
        
        USER REQUEST:
        {q}
        """
        
        payload = {"contents": [{"parts": [{"text": prompt}]}], "safetySettings": [{"category": c, "threshold": "BLOCK_NONE"} for c in ["HARM_CATEGORY_HARASSMENT", "HARM_CATEGORY_HATE_SPEECH", "HARM_CATEGORY_SEXUALLY_EXPLICIT", "HARM_CATEGORY_DANGEROUS_CONTENT"]]}
        r = requests.post(gen_url, json=payload, timeout=90)
        return r.json()['candidates'][0]['content']['parts'][0]['text']
    except Exception as e: return f"Coach Snag: {str(e)}"

# 3. GLOBAL STYLING (Professional Dark)
st.set_page_config(page_title="Performance AI", layout="wide")

st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');
        .stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
            background-color: #0F172A !important;
            color: #F8FAFC !important;
            font-family: 'Inter', sans-serif;
        }
        [data-testid="stSidebar"] {
            background-color: #1E293B !important;
            border-right: 1px solid rgba(255, 255, 255, 0.1);
            min-width: 300px !important;
        }
        /* Fix button widths to be identical */
        .stButton button {
            width: 100% !important;
            display: block !important;
            background: rgba(255, 255, 255, 0.05) !important;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.1) !important;
            color: #38BDF8 !important;
            font-weight: 800 !important;
            border-radius: 12px !important;
            text-transform: uppercase !important;
            margin-bottom: 5px !important;
        }
        .step-label {
            font-weight: 800;
            font-size: 0.8rem;
            color: #94A3B8;
            text-transform: uppercase;
            margin-top: 2rem;
            margin-bottom: 0.5rem;
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
    st.sidebar.markdown("<h2 style='color: white; font-weight: 800;'>COACH</h2>", unsafe_allow_html=True)
    
    st.sidebar.markdown("<div class='step-label'>Step 1. Looking at trends</div>", unsafe_allow_html=True)
    if st.sidebar.button("Weight & Fat Impact"):
        st.session_state.ms.append({"role": "user", "content": "What is having the most impact on my weight and body fat %? Analyze my calories and macros."})
    if st.sidebar.button("Sleep Quality Impact"):
        st.session_state.ms.append({"role": "user", "content": "What is having the most impact on my sleep? Analyze my activity and macros."})
    if st.sidebar.button("Muscle Mass Impact"):
        st.session_state.ms.append({"role": "user", "content": "Analyze my muscle mass. Calculate it from weight and fat logs, then compare to protein intake."})

    st.sidebar.markdown("<div class='step-label'>Step 2. Levelling up</div>", unsafe_allow_html=True)
    if st.sidebar.button("🚀 HOW DO I IMPROVE?"):
        if st.session_state.ms:
            st.session_state.ms.append({"role": "user", "content": "Give me a specific 3-step action plan based on the data trends we just discussed."})
        else: st.sidebar.warning("Analyze a trend first.")

    st.sidebar.divider()
    if st.sidebar.button("Logout / Reset"):
        st.session_state.tk, st.session_state.cached_data, st.session_state.ms = None, None, []
        st.query_params.clear()
        st.rerun()

    # --- CENTER DASHBOARD ---
    st.title("🔬 Total Performance Analyst")

    if not st.session_state.cached_data:
        st.info("Performance matrix ready for weaving.")
        if st.button("🔄 SYNC & WEAVE 90-DAY DATASET"):
            with st.status("Assembling metrics...", expanded=True) as status:
                h = {"Authorization": f"Bearer {st.session_state.tk}"}
                try:
                    # 1. Fetching (Using multi-level key access)
                    s_data = requests.get("https://api.fitbit.com/1/user/-/activities/steps/date/today/90d.json", headers=h).json().get('activities-steps', [])
                    w_data = requests.get("https://api.fitbit.com/1/user/-/body/weight/date/today/90d.json", headers=h).json().get('body-weight', [])
                    f_data = requests.get("https://api.fitbit.com/1/user/-/body/fat/date/today/90d.json", headers=h).json().get('body-fat', [])
                    sl_data = requests.get("https://api.fitbit.com/1.2/user/-/sleep/list.json?afterDate=2024-01-01&limit=30&sort=desc", headers=h).json().get('sleep', [])

                    # 2. Fetch 30 days of macros
                    macros = []
                    for i in range(1, 31):
                        d_str = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
                        log = requests.get(f"https://api.fitbit.com/1/user/-/foods/log/date/{d_str}.json", headers=h).json().get('summary', {})
                        if log and log.get('calories', 0) > 0:
                            macros.append({"date": d_str, "p": log.get('protein', 0), "c": log.get('carbs', 0), "f": log.get('fat', 0), "in": log.get('calories', 0)})

                    # 3. DEEP SEARCH WEAVER
                    master = {}
                    
                    # Steps uses 'dateTime' and 'value'
                    for x in s_data:
                        d = x.get('dateTime')
                        if d: master[d] = {"s": x.get('value', 0), "w": 0, "f": 0, "cal": 0, "p": 0, "c": 0}
                    
                    # Weight and Fat often use 'value' in time-series
                    for x in w_data:
                        d = x.get('dateTime')
                        if d and d in master: master[d]['w'] = x.get('value', 0)
                    
                    for x in f_data:
                        d = x.get('dateTime')
                        if d and d in master: master[d]['f'] = x.get('value', 0)

                    # Macros
                    for m in macros:
                        if m['date'] in master:
                            master[m['date']].update({"cal": m['in'], "p": m['p'], "c": m['c']})

                    # Build CSV
                    rows = ["Date,Steps,Weight,Fat%,Calories,Protein,Carbs"]
                    for d in sorted(master.keys(), reverse=True):
                        v = master[d]
                        rows.append(f"{d},{v['s']},{v['w']},{v['f']},{v['cal']},{v['p']},{v['c']}")

                    st.session_state.cached_data = {"matrix": "\n".join(rows), "sleep": sl_data}
                    status.update(label="✅ Weaving Complete!", state="complete")
                    st.rerun()
                except Exception as e: st.error(f"Sync failed: {e}")

    # --- CHAT UI ---
    if st.session_state.cached_data:
        # Mini Debug Table (Check if numbers are here!)
        with st.expander("🛠️ DATA DEBUGGER (Check your numbers here)"):
            st.text(st.session_state.cached_data["matrix"][:1000])

        for m in st.session_state.ms:
            with st.chat_message(m["role"]): st.markdown(m["content"])
        
        if st.session_state.ms and st.session_state.ms[-1]["role"] == "user":
            if "l_ans" not in st.session_state or st.session_state.l_ans != len(st.session_state.ms):
                with st.chat_message("assistant"):
                    with st.spinner("Performance Coach is analyzing..."):
                        ans = ask_ai(st.session_state.cached_data, st.session_state.ms[-1]["content"])
                        st.markdown(ans)
                        st.session_state.ms.append({"role": "assistant", "content": ans})
                        st.session_state.last_ans = len(st.session_state.ms)

        if p := st.chat_input("Ask a follow-up..."):
            st.session_state.ms.append({"role": "user", "content": p})
            st.rerun()

else:
    # LANDING PAGE
    st.markdown(f"""
        <div style='text-align: center; margin-top: 10rem;'>
            <h1 style='font-weight: 800; font-size: 3.5rem; color: #F8FAFC;'>Performance AI</h1>
            <p style='color: #94A3B8; font-size: 1.2rem; margin-bottom: 3rem;'>Elite analytics for high-performance health.</p>
            <a href='https://www.fitbit.com/oauth2/authorize?response_type=code&client_id={CID}&scope=activity%20heartrate%20nutrition%20profile%20sleep%20weight&redirect_uri={URI}' 
               target='_blank' 
               style='background-color: #38BDF8; color: white; padding: 1.2rem 3rem; border-radius: 50px; text-decoration: none; font-weight: 800; box-shadow: 0 10px 30px rgba(56, 189, 248, 0.3);'>
               CONNECT PERFORMANCE COACH
            </a>
        </div>
    """, unsafe_allow_html=True)
# --- END OF APP ---
