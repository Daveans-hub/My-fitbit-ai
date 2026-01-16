import streamlit as st
import requests
import base64
import json

# 1. LOAD SECRETS
CID, SEC, GKEY, URI = st.secrets["FITBIT_CLIENT_ID"], st.secrets["FITBIT_CLIENT_SECRET"], st.secrets["GEMINI_API_KEY"], st.secrets["YOUR_SITE_URL"]

# 2. THE ANALYST AI ENGINE
def ask_ai(ctx, q):
    try:
        list_url = f"https://generativelanguage.googleapis.com/v1beta/models?key={GKEY}"
        model_list = requests.get(list_url).json()
        available = [m['name'] for m in model_list.get('models', []) if 'generateContent' in m.get('supportedGenerationMethods', [])]
        priority = [m for m in available if "1.5-flash" in m] + [m for m in available if "gemini-pro" in m and "2." not in m]
        
        prompt = f"""
        You are an elite Health & Performance Coach. Analyze the provided health data for trends and correlations.
        
        DATA CONTEXT (Last 60-90 days of metrics):
        {ctx}
        
        USER QUESTION: {q}
        
        COACHING RULES:
        1. Do not say 'I cannot run statistical models.' Instead, perform pattern recognition to see which variables move together.
        2. Identify 'Lead Indicators' (e.g., 'On days you eat more protein, your muscle mass tends to tick up 48 hours later').
        3. If data is missing (e.g., Muscle Mass is 0), advise the user how to log it.
        4. Be specific with numbers.
        """
        
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "safetySettings": [{"category": c, "threshold": "BLOCK_NONE"} for c in ["HARM_CATEGORY_HARASSMENT", "HARM_CATEGORY_HATE_SPEECH", "HARM_CATEGORY_SEXUALLY_EXPLICIT", "HARM_CATEGORY_DANGEROUS_CONTENT"]]
        }

        for model_path in priority:
            gen_url = f"https://generativelanguage.googleapis.com/v1beta/{model_path}:generateContent?key={GKEY}"
            try:
                r = requests.post(gen_url, json=payload, timeout=60)
                res = r.json()
                if "candidates" in res: return res["candidates"][0]["content"]["parts"][0]["text"]
            except: continue
        return "AI is processing too much data. Try asking a more specific question."
    except Exception as e: return f"System Snag: {str(e)}"

# 3. PAGE SETUP
st.set_page_config(page_title="Elite Health Analyst", layout="wide")
st.title("🔬 Total Health Trend Analyst")

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
    st.sidebar.success("✅ Fitbit Linked")
    st.sidebar.divider()
    st.sidebar.header("Coach Shortcuts")
    
    # Preset Analysis Buttons
    if st.sidebar.button("🌙 What's impacting my sleep?"):
        st.session_state.ms.append({"role": "user", "content": "What is having the most impact on my sleep? Analyze my activity, heart rate, and macros to find correlations, and tell me how to improve it."})
    
    if st.sidebar.button("⚖️ What's impacting my weight/fat%?"):
        st.session_state.ms.append({"role": "user", "content": "What is having the most impact on my weight and body fat %? Look at my calories in/out and activity trends, and give me a plan to improve it."})
        
    if st.sidebar.button("💪 What's impacting my muscle mass?"):
        st.session_state.ms.append({"role": "user", "content": "What is having the most impact on my muscle mass? Compare my protein intake and activity levels to my muscle mass logs, and tell me how to improve it."})

    st.sidebar.divider()
    if st.sidebar.button("Logout / Reset"):
        st.session_state.tk, st.session_state.data, st.session_state.ms = None, None, []
        st.query_params.clear()
        st.rerun()

    # --- DATA SYNC (The "Full Vitals" Pull) ---
    if not st.session_state.data:
        if st.button("🔄 Sync Total Health History (Macros, Muscle, Sleep Stages)"):
            with st.spinner("Analyzing your entire health timeline..."):
                h = {"Authorization": f"Bearer {st.session_state.tk}"}
                try:
                    # Time Series Fetch (90 Days for high correlation detail)
                    steps = requests.get("https://api.fitbit.com/1/user/-/activities/steps/date/today/90d.json", headers=h).json().get('activities-steps', [])
                    weight = requests.get("https://api.fitbit.com/1/user/-/body/weight/date/today/90d.json", headers=h).json().get('body-weight', [])
                    fat = requests.get("https://api.fitbit.com/1/user/-/body/fat/date/today/90d.json", headers=h).json().get('body-fat', [])
                    muscle = requests.get("https://api.fitbit.com/1/user/-/body/muscle/date/today/90d.json", headers=h).json().get('body-muscle', [])
                    
                    # Macros Fetch
                    c_in = requests.get("https://api.fitbit.com/1/user/-/foods/log/caloriesIn/date/today/90d.json", headers=h).json().get('foods-log-caloriesIn', [])
                    prot = requests.get("https://api.fitbit.com/1/user/-/foods/log/protein/date/today/90d.json", headers=h).json().get('foods-log-protein', [])
                    carb = requests.get("https://api.fitbit.com/1/user/-/foods/log/carbs/date/today/90d.json", headers=h).json().get('foods-log-carbs', [])
                    
                    # Sleep Timeline Fetch (Last 20 sessions with stages)
                    slp = requests.get("https://api.fitbit.com/1.2/user/-/sleep/list.json?afterDate=2024-01-01&limit=20&sort=desc", headers=h).json().get('sleep', [])
                    sleep_stages = [{"date": s['dateOfSleep'], "deep": s['levels']['summary'].get('deep',{}).get('minutes',0), "rem": s['levels']['summary'].get('rem',{}).get('minutes',0), "asleep": s['minutesAsleep']} for s in slp]

                    # Align Data into a Master Performance Table
                    master = {}
                    for i in steps: master[i['dateTime']] = {"steps": i['value'], "w": "0", "f": "0", "m": "0", "cal": "0", "p": "0", "c": "0"}
                    for i in weight: 
                        if i['dateTime'] in master: master[i['dateTime']]['w'] = i['value']
                    for i in fat: 
                        if i['dateTime'] in master: master[i['dateTime']]['f'] = i['value']
                    for i in muscle: 
                        if i['dateTime'] in master: master[i['dateTime']]['m'] = i['value']
                    for i in c_in: 
                        if i['dateTime'] in master: master[i['dateTime']]['cal'] = i['value']
                    for i in prot: 
                        if i['dateTime'] in master: master[i['dateTime']]['p'] = i['value']
                    for i in carb: 
                        if i['dateTime'] in master: master[i['dateTime']]['c'] = i['value']

                    rows = ["Date,Steps,Weight,Fat%,Muscle,Calories,Protein,Carbs"]
                    for d in sorted(master.keys(), reverse=True):
                        v = master[d]
                        if v['steps'] != "0" or v['w'] != "0": # Only keep active days
                            rows.append(f"{d},{v['steps']},{v['w']},{v['f']},{v['m']},{v['cal']},{v['p']},{v['c']}")
                    
                    st.session_state.data = {"table": "\n".join(rows), "sleep": sleep_stages}
                    st.success("Analysis Ready!")
                    st.rerun()
                except Exception as e: st.error(f"Sync failed: {e}")

    # --- CHAT INTERFACE ---
    if st.session_state.data:
        for m in st.session_state.ms:
            with st.chat_message(m["role"]): st.markdown(m["content"])
            
        # Detect if a sidebar button was just clicked
        if st.session_state.ms and st.session_state.ms[-1]["role"] == "user":
            # Prevent double-processing
            if "last_ans" not in st.session_state or st.session_state.last_ans != len(st.session_state.ms):
                with st.chat_message("assistant"):
                    with st.spinner("Analyzing performance trends..."):
                        ans = ask_ai(st.session_state.data, st.session_state.ms[-1]["content"])
                        st.markdown(ans)
                        st.session_state.ms.append({"role": "assistant", "content": ans})
                        st.session_state.last_ans = len(st.session_state.ms)

        if p := st.chat_input("Ask for a custom trend analysis..."):
            st.session_state.ms.append({"role": "user", "content": p})
            st.rerun()

else:
    url = f"https://www.fitbit.com/oauth2/authorize?response_type=code&client_id={CID}&scope=activity%20heartrate%20nutrition%20profile%20sleep%20weight&redirect_uri={URI}"
    st.markdown(f"### [🔗 Connect Total Health Data]({url})")

# --- END OF APP ---
