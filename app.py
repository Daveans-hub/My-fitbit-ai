import streamlit as st
import requests
import base64
import json

# 1. LOAD SECRETS
CID, SEC, GKEY, URI = st.secrets["FITBIT_CLIENT_ID"], st.secrets["FITBIT_CLIENT_SECRET"], st.secrets["GEMINI_API_KEY"], st.secrets["YOUR_SITE_URL"]

# 2. AUTO-DISCOVERY STATISTICAL ENGINE
def ask_ai(master_table, sleep_data, user_query):
    try:
        # Step A: Discover the correct model and version automatically
        # We check v1 first as it's the most likely stable home for your key
        api_version = "v1"
        list_url = f"https://generativelanguage.googleapis.com/{api_version}/models?key={GKEY}"
        model_list_resp = requests.get(list_url)
        
        # If v1 fails, try v1beta
        if model_list_resp.status_code != 200:
            api_version = "v1beta"
            list_url = f"https://generativelanguage.googleapis.com/{api_version}/models?key={GKEY}"
            model_list_resp = requests.get(list_url)

        model_data = model_list_resp.json()
        available = [m['name'] for m in model_data.get('models', []) if 'generateContent' in m.get('supportedGenerationMethods', [])]
        
        if not available:
            return "AI Error: No models found. Please check your API Key in Google AI Studio."

        # Pick the best available (Priority: 1.5-flash, then 1.0-pro, then anything not 2.0)
        selected_model = next((m for m in available if "1.5-flash" in m), 
                         next((m for m in available if "gemini-pro" in m), available[0]))

        # Step B: Construct the generation URL
        gen_url = f"https://generativelanguage.googleapis.com/{api_version}/{selected_model}:generateContent?key={GKEY}"
        
        prompt = f"""
        You are a Health Data Scientist. Perform a multivariate regression analysis.
        
        DATASET (Date,Steps,Weight,Fat%,CalIn,CalOut):
        {master_table}
        
        SLEEP CONTEXT: {sleep_data}
        
        REQUEST: {user_query}
        
        GOAL: Determine which variables have the most statistical impact on Weight and Fat% changes. 
        Order them from most to least impact. Note: Menstrual cycle data is not in the API, 
        so look for internal patterns in Heart Rate/Weight if asked.
        """
        
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "safetySettings": [{"category": c, "threshold": "BLOCK_NONE"} for c in ["HARM_CATEGORY_HARASSMENT", "HARM_CATEGORY_HATE_SPEECH", "HARM_CATEGORY_SEXUALLY_EXPLICIT", "HARM_CATEGORY_DANGEROUS_CONTENT"]]
        }

        # Step C: Execute with a long timeout for math
        res = requests.post(gen_url, json=payload, timeout=120)
        res_json = res.json()
        
        if "candidates" in res_json:
            return res_json["candidates"][0]["content"]["parts"][0]["text"]
        return f"Google Refusal: {json.dumps(res_json)}"
            
    except Exception as e:
        return f"Discovery Error: {str(e)}"

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
            with st.spinner("Aligning 365 days of health metrics..."):
                h = {"Authorization": f"Bearer {st.session_state.tk}"}
                try:
                    # Pull 1 year of all major metrics
                    s = requests.get("https://api.fitbit.com/1/user/-/activities/steps/date/today/1y.json", headers=h).json().get('activities-steps', [])
                    w = requests.get("https://api.fitbit.com/1/user/-/body/weight/date/today/1y.json", headers=h).json().get('body-weight', [])
                    f = requests.get("https://api.fitbit.com/1/user/-/body/fat/date/today/1y.json", headers=h).json().get('body-fat', [])
                    co = requests.get("https://api.fitbit.com/1/user/-/activities/calories/date/today/1y.json", headers=h).json().get('activities-calories', [])
                    ci = requests.get("https://api.fitbit.com/1/user/-/foods/log/caloriesIn/date/today/1y.json", headers=h).json().get('foods-log-caloriesIn', [])
                    sl = requests.get("https://api.fitbit.com/1.2/user/-/sleep/list.json?afterDate=2024-01-01&limit=20&sort=desc", headers=h).json().get('sleep', [])

                    # Align by date
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

                    # Create Ultra-Lean Table (Filter for Weight exists)
                    rows = ["D,S,W,F,I,O"]
                    for d in sorted(master.keys(), reverse=True):
                        v = master[d]
                        if v[1] != "0": # Only send days where Weight was logged
                            rows.append(f"{d},{v[0]},{v[1]},{v[2]},{v[3]},{v[4]}")
                    
                    sleep_txt = [{"d": x['dateOfSleep'], "h": round(x['minutesAsleep']/60, 1)} for x in sl]
                    st.session_state.master_data = {"table": "\n".join(rows[:100]), "sleep": sleep_txt} # Cap at 100 days for performance
                    st.success("Synced 12 months (Weight-logged days prioritized)!")
                    st.rerun()
                except Exception as e: st.error(f"Sync failed: {e}")

    if st.session_state.master_data:
        for m in st.session_state.ms:
            with st.chat_message(m["role"]): st.markdown(m["content"])
            
        if p := st.chat_input("Perform analysis..."):
            st.session_state.ms.append({"role": "user", "content": p})
            with st.chat_message("user"): st.markdown(p)
            with st.chat_message("assistant"):
                with st.spinner("AI is performing regression analysis..."):
                    ans = ask_ai(st.session_state.master_data["table"], st.session_state.master_data["sleep"], p)
                    st.markdown(ans)
                    st.session_state.ms.append({"role": "assistant", "content": ans})

else:
    url = f"https://www.fitbit.com/oauth2/authorize?response_type=code&client_id={CID}&scope=activity%20heartrate%20nutrition%20profile%20sleep%20weight&redirect_uri={URI}"
    st.markdown(f"### [🔗 Connect Fitbit]({url})")

# --- END OF APP ---
