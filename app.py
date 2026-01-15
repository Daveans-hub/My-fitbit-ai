import streamlit as st
import requests
import base64
import json

# 1. LOAD SECRETS
CID, SEC, GKEY, URI = st.secrets["FITBIT_CLIENT_ID"], st.secrets["FITBIT_CLIENT_SECRET"], st.secrets["GEMINI_API_KEY"], st.secrets["YOUR_SITE_URL"]

# 2. THE SCIENTIST AI FUNCTION (With Safety Overrides)
def ask_ai(master_table, sleep_data, user_query):
    # Using v1beta with the correct model name
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GKEY}"
    
    prompt = f"""
    You are a professional health data scientist. 
    Analyze the following 12-month dataset for correlations and regressions.
    
    DATA (Date, Steps, Weight, Fat%, CaloriesIn, CaloriesOut):
    {master_table}
    
    SLEEP HISTORY:
    {sleep_data}
    
    USER QUESTION: {user_query}
    
    OUTPUT: Provide a statistical analysis. If a correlation is weak, say so. 
    Focus on patterns between activity, sleep, and weight.
    """
    
    # These settings prevent Google from blocking health-related data
    safety_settings = [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
    ]
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "safetySettings": safety_settings
    }
    
    try:
        res = requests.post(url, json=payload, timeout=60)
        data = res.json()
        
        if "candidates" in data and len(data["candidates"]) > 0:
            return data["candidates"][0]["content"]["parts"][0]["text"]
        elif "error" in data:
            return f"Google API Error: {data['error']['message']}"
        else:
            # This will show us if it was blocked for 'Safety'
            return f"AI Refusal. Data received: {json.dumps(data)[:500]}"
            
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
        st.session_state.tk = r.get("access_token")
        st.query_params.clear()
        st.rerun()
    except: st.error("Login failed.")

# 5. MAIN APP
if st.session_state.tk:
    st.sidebar.success("✅ Linked")
    if st.sidebar.button("Logout / Reset"):
        st.session_state.tk, st.session_state.master_data, st.session_state.ms = None, None, []
        st.rerun()

    if not st.session_state.master_data:
        if st.button("🔄 Sync 12-Month Master Table"):
            with st.spinner("Processing 12 months of data..."):
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
                    st.rerun()
                except Exception as e: st.error(f"Sync failed: {e}")

    if st.session_state.master_data:
        for m in st.session_state.ms:
            with st.chat_message(m["role"]): st.markdown(m["content"])
            
        if p := st.chat_input("Ask for a regression or correlation..."):
            st.session_state.ms.append({"role": "user", "content": p})
            with st.chat_message("user"): st.markdown(p)
            with st.chat_message("assistant"):
                with st.spinner("Analyzing..."):
                    ans = ask_ai(st.session_state.master_data["table"], st.session_state.master_data["sleep"], p)
                    st.markdown(ans)
                    st.session_state.ms.append({"role": "assistant", "content": ans})

else:
    url = f"https://www.fitbit.com/oauth2/authorize?response_type=code&client_id={CID}&scope=activity%20heartrate%20nutrition%20profile%20sleep%20weight&redirect_uri={URI}"
    st.markdown(f"### [🔗 Connect Fitbit]({url})")

# END OF CODE
