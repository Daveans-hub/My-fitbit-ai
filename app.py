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
        You are an Elite Performance Coach. Analyze the health metrics below.
        
        CRITICAL MATH INSTRUCTIONS:
        - If Fat% and Weight are present, calculate Muscle Mass: Weight * (1 - (Fat% / 100)).
        - Look for trends even if some days have '0' values.
        - Compare variables to find what DRIVES changes (e.g. 'Higher Protein leads to higher Muscle Mass' or 'Steps > 15k improves Deep Sleep').
        
        DATASET:
        {ctx}
        
        USER REQUEST:
        {q}
        """
        
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        r = requests.post(gen_url, json=payload, timeout=90)
        res = r.json()
        if "candidates" in res:
            return res["candidates"][0]["content"]["parts"][0]["text"]
        return f"AI Snag: {res}"
    except Exception as e:
        return f"System Snag: {str(e)}"

# 3. PAGE SETUP
st.set_page_config(page_title="Performance Coach AI", layout="wide")
st.title("🔬 Elite Performance & Health Analyst")

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
    st.sidebar.success("✅ Fitbit Link Active")
    st.sidebar.divider()
    
    st.sidebar.header("Step 1: Trend Analysis")
    if st.sidebar.button("⚖️ Analyze Weight/Fat Trends"):
        st.session_state.ms.append({"role": "user", "content": "What is having the most impact on my weight and body fat %? Analyze my calories in/out, steps, and protein."})
    
    if st.sidebar.button("🌙 Analyze Sleep Trends"):
        st.session_state.ms.append({"role": "user", "content": "What is having the most impact on my sleep? Analyze my activity, heart rate, and macro correlations."})
        
    if st.sidebar.button("💪 Analyze Muscle Mass Trends"):
        st.session_state.ms.append({"role": "user", "content": "Analyze my muscle mass trends. Calculate lean mass from weight/fat and compare to protein intake."})

    st.sidebar.header("Step 2: Improvement")
    if st.sidebar.button("🚀 How do I improve this?"):
        if st.session_state.ms:
            st.session_state.ms.append({"role": "user", "content": "Based on our data analysis, give me a highly specific 3-step action plan to improve my results starting tomorrow."})
        else: st.sidebar.warning("Run analysis first")

    st.sidebar.header("Step 3: Deep Correlations")
    if st.sidebar.button("🍗 Protein vs Muscle Gains"):
        st.session_state.ms.append({"role": "user", "content": "Analyze the relationship between protein intake and calculated muscle mass. Am I eating enough protein to see gains?"})
    
    if st.sidebar.button("🚶 Steps vs Deep Sleep"):
        st.session_state.ms.append({"role": "user", "content": "Compare deep sleep minutes to my daily step count. Do I get more deep sleep on days when I walk over 15,000 steps?"})
    
    if st.sidebar.button("🍎 Food Log Deep-Dive"):
        st.session_state.ms.append({"role": "user", "content": "Look at my food logs and macros. Is there anything specific impacting my weight loss, muscle gain, or sleep?"})

    if st.sidebar.button("Logout / Reset"):
        st.session_state.tk, st.session_state.data, st.session_state.ms = None, None, []
        st.query_params.clear()
        st.rerun()

    # --- DATA WEAVER (Fetches every metric) ---
    if not st.session_state.data:
        if st.button("🔄 Sync Total Performance History"):
            with st.spinner("Weaving 90 days of performance vitals..."):
                h = {"Authorization": f"Bearer {st.session_state.tk}"}
                try:
                    # 1. Fetch data from all endpoints
                    s = requests.get("https://api.fitbit.com/1/user/-/activities/steps/date/today/90d.json", headers=h).json().get('activities-steps', [])
                    w = requests.get("https://api.fitbit.com/1/user/-/body/weight/date/today/90d.json", headers=h).json().get('body-weight', [])
                    f = requests.get("https://api.fitbit.com/1/user/-/body/fat/date/today/90d.json", headers=h).json().get('body-fat', [])
                    cin = requests.get("https://api.fitbit.com/1/user/-/foods/log/caloriesIn/date/today/90d.json", headers=h).json().get('foods-log-caloriesIn', [])
                    prot = requests.get("https://api.fitbit.com/1/user/-/foods/log/protein/date/today/90d.json", headers=h).json().get('foods-log-protein', [])
                    carb = requests.get("https://api.fitbit.com/1/user/-/foods/log/carbs/date/today/90d.json", headers=h).json().get('foods-log-carbs', [])
                    # Sleep (last 30 logs with stages)
                    slp_r = requests.get("https://api.fitbit.com/1.2/user/-/sleep/list.json?afterDate=2024-01-01&limit=30&sort=desc", headers=h).json().get('sleep', [])

                    # 2. Build the date-aligned Master Dictionary
                    all_dates = sorted(list(set([x['dateTime'] for x in s] + [x['dateTime'] for x in w])), reverse=True)
                    master = {d: {"s": "0", "w": "0", "f": "0", "cal": "0", "p": "0", "c": "0"} for d in all_dates}

                    # Populate the dictionary
                    for i in s: master[i['dateTime']]['s'] = i['value']
                    for i in w: master[i['dateTime']]['w'] = i['value']
                    for i in f: master[i['dateTime']]['f'] = i['value']
                    for i in cin: master[i['dateTime']]['cal'] = i['value']
                    for i in prot: master[i['dateTime']]['p'] = i['value']
                    for i in carb: master[i['dateTime']]['c'] = i['value']

                    rows = ["Date,Steps,Weight,Fat%,Calories,Protein,Carbs"]
                    for d in all_dates:
                        v = master[d]
                        rows.append(f"{d},{v['s']},{v['w']},{v['f']},{v['cal']},{v['p']},{v['c']}")
                    
                    slp_clean = [{"date": x['dateOfSleep'], "deep": x['levels']['summary'].get('deep',{}).get('minutes',0), "total": x['minutesAsleep']} for x in slp_r]
                    
                    st.session_state.data = {"matrix": "\n".join(rows[:60]), "sleep_logs": slp_clean}
                    st.success("Sync Complete!")
                    st.rerun()
                except Exception as e: st.error(f"Sync failed: {e}")

    # --- CHAT UI ---
    if st.session_state.data:
        for m in st.session_state.ms:
            with st.chat_message(m["role"]): st.markdown(m["content"])
            
        if st.session_state.ms and st.session_state.ms[-1]["role"] == "user":
            if "last_ans" not in st.session_state or st.session_state.last_ans != len(st.session_state.ms):
                with st.chat_message("assistant"):
                    with st.spinner("Analyzing performance trends..."):
                        ans = ask_ai(st.session_state.data, st.session_state.ms[-1]["content"])
                        st.markdown(ans)
                        st.session_state.ms.append({"role": "assistant", "content": ans})
                        st.session_state.last_ans = len(st.session_state.ms)

        if p := st.chat_input("Custom question..."):
            st.session_state.ms.append({"role": "user", "content": p})
            st.rerun()
else:
    scope = "activity%20heartrate%20nutrition%20profile%20sleep%20weight"
    link = f"https://www.fitbit.com/oauth2/authorize?response_type=code&client_id={CID}&scope={scope}&redirect_uri={URI}"
    st.markdown(f"### [🔗 Connect Total Health Data]({link})")
# --- END OF APP ---
