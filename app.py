import streamlit as st
import requests
import base64
import json

# 1. LOAD SECRETS
CID, SEC, GKEY, URI = st.secrets["FITBIT_CLIENT_ID"], st.secrets["FITBIT_CLIENT_SECRET"], st.secrets["GEMINI_API_KEY"], st.secrets["YOUR_SITE_URL"]

# 2. THE PERFORMANCE COACH AI ENGINE
def ask_ai(ctx, q):
    try:
        # Auto-Discovery for the best model
        list_url = f"https://generativelanguage.googleapis.com/v1beta/models?key={GKEY}"
        m_list = requests.get(list_url).json()
        available = [m['name'] for m in m_list.get('models', []) if 'generateContent' in m.get('supportedGenerationMethods', [])]
        model_path = next((m for m in available if "1.5-flash" in m), available[0])
        
        gen_url = f"https://generativelanguage.googleapis.com/v1beta/{model_path}:generateContent?key={GKEY}"
        
        prompt = f"""
        You are an Elite Performance Coach & Data Scientist. 
        Analyze the following data for trends. 
        
        INSTRUCTIONS:
        - Calculate 'Muscle Mass' as: Weight * (1 - (Fat% / 100)).
        - Look for 'Lead and Lag' correlations (e.g. Activity today affects Sleep tonight).
        - Be highly specific and numeric. No generic advice.
        
        DATA CONTEXT:
        {ctx}
        
        USER REQUEST:
        {q}
        """
        
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "safetySettings": [{"category": c, "threshold": "BLOCK_NONE"} for c in ["HARM_CATEGORY_HARASSMENT", "HARM_CATEGORY_HATE_SPEECH", "HARM_CATEGORY_SEXUALLY_EXPLICIT", "HARM_CATEGORY_DANGEROUS_CONTENT"]]
        }

        r = requests.post(gen_url, json=payload, timeout=90)
        res = r.json()
        if "candidates" in res:
            return res["candidates"][0]["content"]["parts"][0]["text"]
        return f"AI Error: {res}"
    except Exception as e:
        return f"System Snag: {str(e)}"

# 3. PAGE SETUP
st.set_page_config(page_title="Performance Coach AI", layout="wide")
st.title("🔬 Total Performance & Health Analyst")

if "tk" not in st.session_state: st.session_state.tk = None
if "ms" not in st.session_state: st.session_state.ms = []
if "data" not in st.session_state: st.session_state.data = None

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
    # --- SIDEBAR COACHING SECTION ---
    st.sidebar.success("✅ Fitbit Data Stream Active")
    st.sidebar.divider()
    
    st.sidebar.header("Step 1: Trend Analysis")
    if st.sidebar.button("⚖️ Analyze Weight/Fat Trends"):
        st.session_state.ms.append({"role": "user", "content": "What is having the most impact on my weight and body fat %? Analyze my calories in/out, steps, and macronutrient trends."})
    
    if st.sidebar.button("🌙 Analyze Sleep Trends"):
        st.session_state.ms.append({"role": "user", "content": "What is having the most impact on my sleep? Analyze my activity, heart rate, and macro correlations."})
        
    if st.sidebar.button("💪 Analyze Muscle Mass Trends"):
        st.session_state.ms.append({"role": "user", "content": "Analyze my muscle mass. Calculate lean mass from my weight and fat logs, then compare it to my protein intake and activity."})

    st.sidebar.header("Step 2: Improvement")
    if st.sidebar.button("🚀 How do I improve this?"):
        if st.session_state.ms:
            prev_topic = st.session_state.ms[-1]["content"]
            st.session_state.ms.append({"role": "user", "content": f"Based on the analysis we just did about '{prev_topic}', give me a highly specific 3-step action plan to improve these results starting tomorrow."})
        else: st.sidebar.warning("Run an analysis first!")

    st.sidebar.header("Specialized Correlations")
    if st.sidebar.button("🍗 Protein vs Muscle Gains"):
        st.session_state.ms.append({"role": "user", "content": "Analyze the relationship between my protein intake and my muscle mass. Am I eating enough protein to see gains?"})
    
    if st.sidebar.button("🚶 Steps vs Deep Sleep"):
        st.session_state.ms.append({"role": "user", "content": "Compare my deep sleep minutes to my daily step count. Do I get more deep sleep on days when I walk over 15,000 steps?"})
    
    if st.sidebar.button("🍎 Food Log Deep-Dive"):
        st.session_state.ms.append({"role": "user", "content": "Look at my food logs and macros. Is there anything specific impacting my weight loss, muscle gain, or sleep?"})

    if st.sidebar.button("Logout / Reset"):
        st.session_state.tk, st.session_state.data, st.session_state.ms = None, None, []
        st.rerun()

    # --- DATA SYNC (Hyper-Granular Matrix) ---
    if not st.session_state.data:
        if st.button("🔄 Sync Total Health History (Detailed Macros & Sleep Stages)"):
            with st.spinner("Crunching 90 days of performance vitals..."):
                h = {"Authorization": f"Bearer {st.session_state.tk}"}
                try:
                    # Pulling detailed Time Series
                    s = requests.get("https://api.fitbit.com/1/user/-/activities/steps/date/today/90d.json", headers=h).json().get('activities-steps', [])
                    w = requests.get("https://api.fitbit.com/1/user/-/body/weight/date/today/90d.json", headers=h).json().get('body-weight', [])
                    f = requests.get("https://api.fitbit.com/1/user/-/body/fat/date/today/90d.json", headers=h).json().get('body-fat', [])
                    
                    # Pulling Nutrition (Detailed Macros)
                    cin = requests.get("https://api.fitbit.com/1/user/-/foods/log/caloriesIn/date/today/90d.json", headers=h).json().get('foods-log-caloriesIn', [])
                    prot = requests.get("https://api.fitbit.com/1/user/-/foods/log/protein/date/today/90d.json", headers=h).json().get('foods-log-protein', [])
                    carb = requests.get("https://api.fitbit.com/1/user/-/foods/log/carbs/date/today/90d.json", headers=h).json().get('foods-log-carbs', [])
                    
                    # Pulling Sleep Stages
                    slp_raw = requests.get("https://api.fitbit.com/1.2/user/-/sleep/list.json?afterDate=2024-01-01&limit=30&sort=desc", headers=h).json().get('sleep', [])
                    slp_clean = [{"d": x['dateOfSleep'], "deep": x['levels']['summary'].get('deep',{}).get('minutes',0), "rem": x['levels']['summary'].get('rem',{}).get('minutes',0), "total": x['minutesAsleep']} for x in slp_raw]

                    # Building the Matrix
                    master = {}
                    for i in s: master[i['dateTime']] = {"s": i['value'], "w": "0", "f": "0", "cal": "0", "p": "0", "c": "0"}
                    for i in w: 
                        if i['dateTime'] in master: master[i['dateTime']]['w'] = i['value']
                    for i in f: 
                        if i['dateTime'] in master: master[i['dateTime']]['f'] = i['value']
                    for i in cin: 
                        if i['dateTime'] in master: master[i['dateTime']]['cal'] = i['value']
                    for i in prot: 
                        if i['dateTime'] in master: master[i['dateTime']]['p'] = i['value']
                    for i in carb: 
                        if i['dateTime'] in master: master[i['dateTime']]['c'] = i['value']

                    rows = ["Date,Steps,Wgt,Fat%,CalIn,Protein,Carb"]
                    for d in sorted(master.keys(), reverse=True):
                        v = master[d]
                        rows.append(f"{d},{v['s']},{v['w']},{v['f']},{v['cal']},{v['p']},{v['c']}")
                    
                    st.session_state.data = {"matrix": "\n".join(rows[:60]), "sleep_timeline": slp_clean}
                    st.success("Coach is ready!")
                    st.rerun()
                except Exception as e: st.error(f"Sync failed: {e}")

    # --- CHAT UI ---
    if st.session_state.data:
        for m in st.session_state.ms:
            with st.chat_message(m["role"]): st.markdown(m["content"])
            
        if st.session_state.ms and st.session_state.ms[-1]["role"] == "user":
            if "last_ans" not in st.session_state or st.session_state.last_ans != len(st.session_state.ms):
                with st.chat_message("assistant"):
                    with st.spinner("Analyzing data timeline..."):
                        ans = ask_ai(st.session_state.data, st.session_state.ms[-1]["content"])
                        st.markdown(ans)
                        st.session_state.ms.append({"role": "assistant", "content": ans})
                        st.session_state.last_ans = len(st.session_state.ms)

        if p := st.chat_input("Ask a follow-up question..."):
            st.session_state.ms.append({"role": "user", "content": p})
            st.rerun()

else:
    scope = "activity%20heartrate%20nutrition%20profile%20sleep%20weight"
    link = f"https://www.fitbit.com/oauth2/authorize?response_type=code&client_id={CID}&scope={scope}&redirect_uri={URI}"
    st.markdown(f"### [🔗 Connect Fitbit]({link})")

# --- END OF APP ---
