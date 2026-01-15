import streamlit as st
import requests
import base64
import json

# 1. LOAD SECRETS
CID, SEC, GKEY, URI = st.secrets["FITBIT_CLIENT_ID"], st.secrets["FITBIT_CLIENT_SECRET"], st.secrets["GEMINI_API_KEY"], st.secrets["YOUR_SITE_URL"]

# 2. DATA SCIENTIST AI FUNCTION
def ask_ai(master_table, sleep_data, user_query):
    try:
        # Step A: Get models and find the best worker
        list_url = f"https://generativelanguage.googleapis.com/v1/models?key={GKEY}"
        model_list = requests.get(list_url).json()
        all_m = [m['name'] for m in model_list.get('models', []) if 'generateContent' in m.get('supportedGenerationMethods', [])]
        priority = [m for m in all_m if "1.5-flash" in m] + [m for m in all_m if "gemini-pro" in m]
        
        # Step B: Clean the table for faster processing
        # We only send lines that have a Weight value (not 0) to allow for regression
        lines = master_table.split('\n')
        clean_rows = [lines[0]] # Keep Header
        for line in lines[1:]:
            parts = line.split(',')
            if len(parts) > 2 and parts[2] != "0": # Index 2 is Weight
                clean_rows.append(line)
        
        clean_table = "\n".join(clean_rows[:200]) # Limit to 200 high-quality data points for speed

        prompt = f"""
        You are a Health Data Scientist. Perform a multivariate regression and correlation analysis.
        
        USER REQUEST: {user_query}
        
        DATASET (Date, Steps, Weight, Fat%, CaloriesIn, CaloriesOut):
        {clean_table}
        
        SLEEP CONTEXT:
        {sleep_data}
        
        INSTRUCTIONS:
        1. Calculate the statistical correlation between activity/sleep and weight/fat.
        2. Identify which variable has the highest 'Impact Factor' on weight changes.
        3. Order variables from most to least impact.
        4. Be technical but clear.
        """
        
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "safetySettings": [{"category": c, "threshold": "BLOCK_NONE"} for c in ["HARM_CATEGORY_HARASSMENT", "HARM_CATEGORY_HATE_SPEECH", "HARM_CATEGORY_SEXUALLY_EXPLICIT", "HARM_CATEGORY_DANGEROUS_CONTENT"]]
        }

        for model_path in priority:
            gen_url = f"https://generativelanguage.googleapis.com/v1/{model_path}:generateContent?key={GKEY}"
            # TIMEOUT increased to 120s for math processing
            res = requests.post(gen_url, json=payload, timeout=120) 
            res_json = res.json()
            if "candidates" in res_json:
                return res_json["candidates"][0]["content"]["parts"][0]["text"]
            continue
            
        return "AI analysis failed to complete. Try a simpler question."
    except Exception as e:
        return f"Statistical Error: {str(e)}"

# 3. PAGE SETUP
st.set_page_config(page_title="Health Analyst Pro", layout="wide")
st.title("🔬 Lifetime Correlation & Regression AI")

if "tk" not in st.session_state: st.session_state.tk = None
if "ms" not in st.session_state: st.session_state.ms = []
if "master_data" not in st.session_state: st.session_state.master_data = None

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
    st.sidebar.success("✅ Health Data Linked")
    if st.sidebar.button("Logout / Reset"):
        st.session_state.tk, st.session_state.master_data, st.session_state.ms = None, None, []
        st.query_params.clear()
        st.rerun()

    if not st.session_state.master_data:
        if st.button("🔄 Sync & Build Statistical Master Table"):
            with st.spinner("Processing 12 months of daily metrics..."):
                h = {"Authorization": f"Bearer {st.session_state.tk}"}
                try:
                    s = requests.get("https://api.fitbit.com/1/user/-/activities/steps/date/today/1y.json", headers=h).json().get('activities-steps', [])
                    w = requests.get("https://api.fitbit.com/1/user/-/body/weight/date/today/1y.json", headers=h).json().get('body-weight', [])
                    f = requests.get("https://api.fitbit.com/1/user/-/body/fat/date/today/1y.json", headers=h).json().get('body-fat', [])
                    co = requests.get("https://api.fitbit.com/1/user/-/activities/calories/date/today/1y.json", headers=h).json().get('activities-calories', [])
                    ci = requests.get("https://api.fitbit.com/1/user/-/foods/log/caloriesIn/date/today/1y.json", headers=h).json().get('foods-log-caloriesIn', [])
                    sl = requests.get("https://api.fitbit.com/1.2/user/-/sleep/list.json?afterDate=2024-01-01&limit=30&sort=desc", headers=h).json().get('sleep', [])

                    master = {}
                    for i in s: master[i['dateTime']] = [i['value'], "0", "0", "0", "0"]
                    for i in w: 
                        if i['dateTime'] in master: master[i['dateTime']][1] = i['value']
                    for i in f: 
                        if i['dateTime'] in master: master[i['dateTime']][2] = i['value']
                    for i in ci: 
                        if i['dateTime'] in master: master[i['dateTime']][3] = i['value']
                    for i in co: 
                        if i['dateTime'] in master: master[i['dateTime']][4] = i['value']

                    rows = ["Date,Steps,Weight,Fat%,In,Out"]
                    for d in sorted(master.keys(), reverse=True):
                        v = master[d]
                        rows.append(f"{d},{v[0]},{v[1]},{v[2]},{v[3]},{v[4]}")
                    
                    sleep_txt = [{"d": x['dateOfSleep'], "h": round(x['minutesAsleep']/60, 1)} for x in sl]
                    st.session_state.master_data = {"table": "\n".join(rows), "sleep": sleep_txt}
                    st.rerun()
                except Exception as e: st.error(f"Sync failed: {e}")

    if st.session_state.master_data:
        for m in st.session_state.ms:
            with st.chat_message(m["role"]): st.markdown(m["content"])
            
        if p := st.chat_input("Ask for statistical analysis..."):
            st.session_state.ms.append({"role": "user", "content": p})
            with st.chat_message("user"): st.markdown(p)
            with st.chat_message("assistant"):
                with st.spinner("AI is calculating correlations... this takes up to 60 seconds."):
                    ans = ask_ai(st.session_state.master_data["table"], st.session_state.master_data["sleep"], p)
                    st.markdown(ans)
                    st.session_state.ms.append({"role": "assistant", "content": ans})

else:
    url = f"https://www.fitbit.com/oauth2/authorize?response_type=code&client_id={CID}&scope=activity%20heartrate%20nutrition%20profile%20sleep%20weight&redirect_uri={URI}"
    st.markdown(f"### [🔗 Connect Fitbit]({url})")

# --- END OF APP ---
