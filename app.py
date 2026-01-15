import streamlit as st
import requests
import base64
import json

# 1. LOAD SECRETS
CID, SEC, GKEY, URI = st.secrets["FITBIT_CLIENT_ID"], st.secrets["FITBIT_CLIENT_SECRET"], st.secrets["GEMINI_API_KEY"], st.secrets["YOUR_SITE_URL"]

# 2. FAIL-SAFE AI FUNCTION
def ask_ai(master_table, sleep_data, user_query):
    try:
        # Step A: Get all available models
        list_url = f"https://generativelanguage.googleapis.com/v1/models?key={GKEY}"
        model_list = requests.get(list_url).json()
        
        # Step B: Filter and Prioritize (We exclude 2.0 because of your 0-quota error)
        all_models = [
            m['name'] for m in model_list.get('models', []) 
            if 'generateContent' in m.get('supportedGenerationMethods', [])
        ]
        
        # Preference order: 1.5-flash (stable), 1.0-pro (backup), then anything else non-2.0
        priority_list = [m for m in all_models if "1.5-flash" in m]
        priority_list += [m for m in all_models if "gemini-pro" in m and "2.0" not in m]
        priority_list += [m for m in all_models if m not in priority_list and "2.0" not in m]

        if not priority_list:
            return "No stable Gemini models found for this API key."

        # Step C: The Failover Loop
        # We try each model. If one hits a quota (429), we try the next one.
        prompt = f"""
        You are a health data scientist. Use this 12-month dataset.
        DATA (Date, Steps, Weight, Fat%, In, Out): {str(master_table)[:15000]}
        SLEEP: {sleep_data}
        QUESTION: {user_query}
        """
        
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "safetySettings": [{"category": c, "threshold": "BLOCK_NONE"} for c in ["HARM_CATEGORY_HARASSMENT", "HARM_CATEGORY_HATE_SPEECH", "HARM_CATEGORY_SEXUALLY_EXPLICIT", "HARM_CATEGORY_DANGEROUS_CONTENT"]]
        }

        last_error = ""
        for model_path in priority_list:
            gen_url = f"https://generativelanguage.googleapis.com/v1/{model_path}:generateContent?key={GKEY}"
            res = requests.post(gen_url, json=payload, timeout=40)
            res_json = res.json()
            
            if "candidates" in res_json:
                return res_json["candidates"][0]["content"]["parts"][0]["text"]
            
            # If this model has a quota error (429), the loop continues to the next model
            last_error = res_json.get('error', {}).get('message', 'Unknown error')
            continue

        return f"AI Error: All models hit quota limits. Google says: {last_error}"
            
    except Exception as e:
        return f"System Error: {str(e)}"

# 3. PAGE SETUP
st.set_page_config(page_title="Health Data Scientist", layout="wide")
st.title("🔬 Lifetime Health Analyst")

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
    st.sidebar.success("✅ Linked")
    if st.sidebar.button("Logout / Reset"):
        st.session_state.tk, st.session_state.master_data, st.session_state.ms = None, None, []
        st.query_params.clear()
        st.rerun()

    if not st.session_state.master_data:
        if st.button("🔄 Sync 12-Month Master Table"):
            with st.spinner("Aligning 365 days of health metrics..."):
                h = {"Authorization": f"Bearer {st.session_state.tk}"}
                try:
                    s = requests.get("https://api.fitbit.com/1/user/-/activities/steps/date/today/1y.json", headers=h).json().get('activities-steps', [])
                    w = requests.get("https://api.fitbit.com/1/user/-/body/weight/date/today/1y.json", headers=h).json().get('body-weight', [])
                    f = requests.get("https://api.fitbit.com/1/user/-/body/fat/date/today/1y.json", headers=h).json().get('body-fat', [])
                    co = requests.get("https://api.fitbit.com/1/user/-/activities/calories/date/today/1y.json", headers=h).json().get('activities-calories', [])
                    ci = requests.get("https://api.fitbit.com/1/user/-/foods/log/caloriesIn/date/today/1y.json", headers=h).json().get('foods-log-caloriesIn', [])
                    sl = requests.get("https://api.fitbit.com/1.2/user/-/sleep/list.json?afterDate=2024-01-01&limit=20&sort=desc", headers=h).json().get('sleep', [])

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

                    rows = ["Date,Steps,Wgt,Fat%,In,Out"]
                    for d in sorted(master.keys(), reverse=True):
                        v = master[d]
                        rows.append(f"{d},{v[0]},{v[1]},{v[2]},{v[3]},{v[4]}")
                    
                    sleep_txt = [{"d": x['dateOfSleep'], "h": round(x['minutesAsleep']/60, 1)} for x in sl]
                    st.session_state.master_data = {"table": "\n".join(rows), "sleep": sleep_txt}
                    st.success("Synced 365 days!")
                    st.rerun()
                except Exception as e: st.error(f"Sync failed: {e}")

    if st.session_state.master_data:
        for m in st.session_state.ms:
            with st.chat_message(m["role"]): st.markdown(m["content"])
            
        if p := st.chat_input("Perform correlation or regression..."):
            st.session_state.ms.append({"role": "user", "content": p})
            with st.chat_message("user"): st.markdown(p)
            with st.chat_message("assistant"):
                with st.spinner("Analyzing lifetime trends..."):
                    ans = ask_ai(st.session_state.master_data["table"], st.session_state.master_data["sleep"], p)
                    st.markdown(ans)
                    st.session_state.ms.append({"role": "assistant", "content": ans})

else:
    url = f"https://www.fitbit.com/oauth2/authorize?response_type=code&client_id={CID}&scope=activity%20heartrate%20nutrition%20profile%20sleep%20weight&redirect_uri={URI}"
    st.markdown(f"### [🔗 Connect Fitbit]({url})")

# --- END OF APP ---
