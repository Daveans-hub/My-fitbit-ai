import streamlit as st
import requests
import base64
import json

# 1. LOAD SECRETS
CID, SEC, GKEY, URI = st.secrets["FITBIT_CLIENT_ID"], st.secrets["FITBIT_CLIENT_SECRET"], st.secrets["GEMINI_API_KEY"], st.secrets["YOUR_SITE_URL"]

# 2. ROBUST AI FUNCTION
def ask_ai(ctx, q):
    # We will try a list of 'API + Model' combinations until one works
    combos = [
        ("v1", "gemini-1.5-flash"),
        ("v1beta", "gemini-1.5-flash"),
        ("v1", "gemini-1.5-flash-001"),
        ("v1", "gemini-pro")
    ]
    
    payload = {
        "contents": [{"parts": [{"text": f"You are a health data scientist. Use this data: {str(ctx)[:12000]}. Question: {q}"}]}],
        "safetySettings": [{"category": c, "threshold": "BLOCK_NONE"} for c in ["HARM_CATEGORY_HARASSMENT", "HARM_CATEGORY_HATE_SPEECH", "HARM_CATEGORY_SEXUALLY_EXPLICIT", "HARM_CATEGORY_DANGEROUS_CONTENT"]]
    }
    
    last_error = ""
    for version, model in combos:
        try:
            url = f"https://generativelanguage.googleapis.com/{version}/models/{model}:generateContent?key={GKEY}"
            res = requests.post(url, json=payload, timeout=25)
            data = res.json()
            if "candidates" in data:
                return data["candidates"][0]["content"]["parts"][0]["text"]
            last_error = str(data)
        except Exception as e:
            last_error = str(e)
            continue
            
    return f"AI Snag: All models failed. Last Error: {last_error}"

# 3. PAGE SETUP
st.set_page_config(page_title="Health Scientist AI", layout="wide")
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
    st.sidebar.success("✅ Health Data Linked")
    if st.sidebar.button("Logout / Reset Data"):
        st.session_state.tk, st.session_state.master_data, st.session_state.ms = None, None, []
        st.query_params.clear()
        st.rerun()

    if not st.session_state.master_data:
        if st.button("🔄 Sync 12-Month Master Table"):
            with st.spinner("Processing 12 months of health records..."):
                h = {"Authorization": f"Bearer {st.session_state.tk}"}
                try:
                    # Pull 1 year of all major metrics
                    s = requests.get("https://api.fitbit.com/1/user/-/activities/steps/date/today/1y.json", headers=h).json().get('activities-steps', [])
                    w = requests.get("https://api.fitbit.com/1/user/-/body/weight/date/today/1y.json", headers=h).json().get('body-weight', [])
                    f = requests.get("https://api.fitbit.com/1/user/-/body/fat/date/today/1y.json", headers=h).json().get('body-fat', [])
                    co = requests.get("https://api.fitbit.com/1/user/-/activities/calories/date/today/1y.json", headers=h).json().get('activities-calories', [])
                    ci = requests.get("https://api.fitbit.com/1/user/-/foods/log/caloriesIn/date/today/1y.json", headers=h).json().get('foods-log-caloriesIn', [])
                    sl = requests.get("https://api.fitbit.com/1.2/user/-/sleep/list.json?afterDate=2024-01-01&limit=20&sort=desc", headers=h).json().get('sleep', [])

                    # Building a clean CSV table (Latest Data First)
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

                    rows = ["Date,Steps,Wgt,Fat%,CalIn,CalOut"]
                    for d in sorted(master.keys(), reverse=True):
                        v = master[d]
                        rows.append(f"{d},{v[0]},{v[1]},{v[2]},{v[3]},{v[4]}")
                    
                    st.session_state.master_data = {"table": "\n".join(rows), "sleep": sl}
                    st.rerun()
                except Exception as e: st.error(f"Sync failed: {e}")

    if st.session_state.master_data:
        for m in st.session_state.ms:
            with st.chat_message(m["role"]): st.markdown(m["content"])
            
        if p := st.chat_input("Analyze my trends (e.g. 'What is the correlation between steps and weight?')"):
            st.session_state.ms.append({"role": "user", "content": p})
            with st.chat_message("user"): st.markdown(p)
            with st.chat_message("assistant"):
                with st.spinner("AI is analyzing 12 months of daily metrics..."):
                    ans = ask_ai(st.session_state.master_data, p)
                    st.markdown(ans)
                    st.session_state.ms.append({"role": "assistant", "content": ans})

else:
    url = f"https://www.fitbit.com/oauth2/authorize?response_type=code&client_id={CID}&scope=activity%20heartrate%20nutrition%20profile%20sleep%20weight&redirect_uri={URI}"
    st.markdown(f"### [🔗 Connect Fitbit]({url})")

# --- END OF APP ---
