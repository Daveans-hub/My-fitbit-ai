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
        list_url = f"https://generativelanguage.googleapis.com/v1/models?key={GKEY}"
        m_list = requests.get(list_url).json()
        available = [m['name'] for m in m_list.get('models', []) if 'generateContent' in m.get('supportedGenerationMethods', [])]
        model_path = next((m for m in available if "1.5-flash" in m), available[0])
        gen_url = f"https://generativelanguage.googleapis.com/v1/{model_path}:generateContent?key={GKEY}"
        
        prompt = f"""
        You are the Elite Performance Coach at Kinetic Lab. 
        Analyze the provided health matrix for these three specific areas:
        
        1. BODY COMPOSITION: Analyze how Calories In vs Out, Steps, and Macros impact Weight and Fat%.
        2. MUSCLE MASS: Calculate Muscle Mass = Weight * (1 - (Fat% / 100)). Identify if Protein intake supports this.
        3. SLEEP QUALITY: Analyze how activity and nutrition correlate with the Sleep Score.
        
        DATASET:
        {ctx}
        
        OUTPUT FORMAT:
        - A technical analysis for each of the 3 points above.
        - A final 'LEVEL UP' section with a highly specific 3-point action plan.
        - Use Pure White text and be numeric.
        """
        payload = {"contents": [{"parts": [{"text": prompt}]}], "safetySettings": [{"category": c, "threshold": "BLOCK_NONE"} for c in ["HARM_CATEGORY_HARASSMENT", "HARM_CATEGORY_HATE_SPEECH", "HARM_CATEGORY_SEXUALLY_EXPLICIT", "HARM_CATEGORY_DANGEROUS_CONTENT"]]}
        r = requests.post(gen_url, json=payload, timeout=90)
        return r.json()['candidates'][0]['content']['parts'][0]['text']
    except Exception as e: return f"Coach Snag: {str(e)}"

# 3. GLOBAL STYLING (Professional Dark + Pure White #FFFFFF Text)
st.set_page_config(page_title="Kinetic Lab", layout="wide")
st.markdown(f"""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;800&display=swap');
        .stApp, [data-testid="stAppViewContainer"] {{ background-color: #0F172A !important; font-family: 'Inter', sans-serif; }}
        
        /* FORCE ALL TEXT TO PURE WHITE */
        html, body, [class*="css"], .stMarkdown, p, h1, h2, h3, li, span, label, div, [data-testid="stChatMessage"] p {{
            color: #FFFFFF !important;
        }}

        [data-testid="stSidebar"] {{ background-color: #1E293B !important; border-right: 1px solid rgba(255, 255, 255, 0.05); min-width: 320px !important; }}
        
        .stButton button {{
            width: 100% !important; display: block !important; background: rgba(255, 255, 255, 0.05) !important;
            backdrop-filter: blur(10px); border: 1px solid rgba(56, 189, 248, 0.4) !important;
            color: #38BDF8 !important; font-weight: 800 !important; border-radius: 10px !important;
            text-transform: uppercase !important; height: 4em !important; margin-bottom: 15px !important;
        }}
        .stButton button:hover {{ background: rgba(56, 189, 248, 0.1) !important; border-color: #38BDF8 !important; }}
        .sidebar-header {{ font-weight: 800; font-size: 1.2rem; color: #F8FAFC !important; margin-bottom: 1.5rem; }}
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
    st.sidebar.markdown("<div class='sidebar-header'>KINETIC LAB</div>")
    
    # Analyze trends button removed from sidebar as requested (it is now automatic)
    
    if st.sidebar.button("Logout"):
        st.session_state.tk, st.session_state.cached_data, st.session_state.ms = None, None, []
        st.query_params.clear()
        st.rerun()

    st.markdown("<h1 style='letter-spacing: 0.025em;'>Kinetic Performance Analyst</h1>", unsafe_allow_html=True)

    if not st.session_state.cached_data:
        if st.button("🔄 SYNC & ANALYSE ALL TRENDS"):
            with st.status("Syncing vitals and running analysis...", expanded=True) as status:
                h = {"Authorization": f"Bearer {st.session_state.tk}"}
                try:
                    # FETCHING (Fixed keys to stop recording zeros)
                    s_raw = requests.get("https://api.fitbit.com/1/user/-/activities/steps/date/today/6m.json", headers=h).json().get('activities-steps', [])
                    w_raw = requests.get("https://api.fitbit.com/1/user/-/body/weight/date/today/6m.json", headers=h).json().get('body-weight', [])
                    f_raw = requests.get("https://api.fitbit.com/1/user/-/body/fat/date/today/6m.json", headers=h).json().get('body-fat', [])
                    co_raw = requests.get("https://api.fitbit.com/1/user/-/activities/calories/date/today/6m.json", headers=h).json().get('activities-calories', [])
                    ci_raw = requests.get("https://api.fitbit.com/1/user/-/foods/log/caloriesIn/date/today/6m.json", headers=h).json().get('foods-log-caloriesIn', [])
                    sl_raw = requests.get("https://api.fitbit.com/1.2/user/-/sleep/list.json?afterDate=2024-01-01&limit=30&sort=desc", headers=h).json().get('sleep', [])
                    
                    # Daily Macro Detail (30 Days)
                    macros = {}
                    for i in range(1, 31):
                        d_str = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
                        m_res = requests.get(f"https://api.fitbit.com/1/user/-/foods/log/date/{d_str}.json", headers=h).json().get('summary', {})
                        if m_res and m_res.get('calories', 0) > 0:
                            macros[d_str] = m_res

                    # THE FOUNDRY (Fixed to hunt for 'weight' and 'fat' keys)
                    master = {}
                    def weave(data_list, label, key_name='value'):
                        for x in data_list:
                            d = x.get('dateTime') or x.get('date')
                            if d:
                                if d not in master: master[d] = {"s":0,"w":0,"f":0,"co":0,"ci":0,"p":0,"c":0,"fat_g":0,"score":0}
                                # Hunt for the specific key (Fitbit uses 'weight' for weight, 'fat' for fat)
                                val = x.get(key_name) or x.get('value') or 0
                                master[d][label] = val

                    weave(s_raw, 's', 'value')
                    weave(w_raw, 'w', 'weight')
                    weave(f_raw, 'f', 'fat')
                    weave(co_raw, 'co', 'value')
                    weave(ci_raw, 'ci', 'value')

                    for d_key, m_val in macros.items():
                        if d_key in master:
                            master[d_key].update({"p": m_val.get('protein', 0), "c": m_val.get('carbs', 0), "fat_g": m_val.get('fat', 0)})
                    for sess in sl_raw:
                        if sess['dateOfSleep'] in master: master[sess['dateOfSleep']]['score'] = sess.get('efficiency', 0)

                    rows = ["Date,Steps,Weight,Fat%,CalOut,CalIn,Protein,Carbs,Fats,SleepScore"]
                    for d in sorted(master.keys(), reverse=True):
                        v = master[d]
                        rows.append(f"{d},{v['s']},{v['w']},{v['f']},{v['co']},{v['ci']},{v['p']},{v['c']},{v['fat_g']},{v['score']}")

                    st.session_state.cached_data = "\n".join(rows)
                    # AUTOMATIC ANALYSIS TRIGGER
                    st.session_state.ms.append({"role": "user", "content": "Analyze my trends now."})
                    status.update(label="✅ Weaving Complete! Analysing...", state="complete")
                    st.rerun()
                except Exception as e: st.error(f"Sync failed: {e}")

    if st.session_state.cached_data:
        for m in st.session_state.ms:
            with st.chat_message(m["role"]): st.markdown(m["content"])
        
        if st.session_state.ms and st.session_state.ms[-1]["role"] == "user":
            if "l_ans" not in st.session_state or st.session_state.l_ans != len(st.session_state.ms):
                with st.chat_message("assistant"):
                    with st.spinner("Performance Coach is crunching the numbers..."):
                        ans = ask_ai(st.session_state.cached_data, "Provide the full 3-part trend analysis and the Level Up plan.")
                        st.markdown(ans)
                        st.session_state.ms.append({"role": "assistant", "content": ans})
                        st.session_state.last_ans = len(st.session_state.ms)
        
        if p := st.chat_input("Ask a follow-up..."):
            st.session_state.ms.append({"role": "user", "content": p})
            st.rerun()

else:
    # LANDING PAGE
    st.markdown("<h1 style='text-align: center; margin-top: 10rem; font-size: 4rem; color: #F8FAFC;'>Kinetic Lab</h1>", unsafe_allow_html=True)
    auth_url = f"https://www.fitbit.com/oauth2/authorize?response_type=code&client_id={CID}&scope=activity%20heartrate%20nutrition%20profile%20sleep%20weight&redirect_uri={URI}"
    st.markdown(f"<div style='text-align: center;'><a href='{auth_url}' target='_blank' style='background-color: #38BDF8; color: white; padding: 1.2rem 3rem; border-radius: 50px; text-decoration: none; font-weight: 800; box-shadow: 0 10px 30px rgba(56, 189, 248, 0.3);'>CONNECT PERFORMANCE COACH</a></div>", unsafe_allow_html=True)
