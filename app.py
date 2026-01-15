import streamlit as st
import requests
import base64
import json

# 1. LOAD SECRETS
CID, SEC, GKEY, URI = st.secrets["FITBIT_CLIENT_ID"], st.secrets["FITBIT_CLIENT_SECRET"], st.secrets["GEMINI_API_KEY"], st.secrets["YOUR_SITE_URL"]

# 2. THE AI FUNCTION (With safety settings to prevent blocks)
def ask_ai(ctx, q):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GKEY}"
    payload = {
        "contents": [{"parts": [{"text": f"You are a health analyst. Context: {ctx}. Question: {q}"}]}],
        "safetySettings": [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
        ]
    }
    try:
        r = requests.post(url, json=payload, timeout=25)
        res_json = r.json()
        if "candidates" in res_json:
            return res_json['candidates'][0]['content']['parts'][0]['text']
        return f"AI Snag: {res_json}"
    except Exception as e:
        return f"AI Error: {e}"

# 3. PAGE SETUP
st.set_page_config(page_title="Health AI", layout="wide")
st.title("🏃 My Personal Health AI")

if "tk" not in st.session_state: st.session_state.tk = None
if "ms" not in st.session_state: st.session_state.ms = []
if "data" not in st.session_state: st.session_state.data = None

# 4. LOGIN
code = st.query_params.get("code")
if st.session_state.tk:
    st.sidebar.success("✅ Connected")
    if st.sidebar.button("Logout / Reset"):
        st.session_state.tk, st.session_state.data, st.session_state.ms = None, None, []
        st.rerun()

    # 5. DATA SYNC (Fetching Weight, Fat, Steps, and Sleep)
    if not st.session_state.data:
        if st.button("🔄 Sync My Health Data"):
            with st.spinner("Fetching Weight, Fat, Steps, and Sleep..."):
                h = {"Authorization": f"Bearer {st.session_state.tk}"}
                
                # Fetching 1 year of Weight and Fat history
                wgt = requests.get("https://api.fitbit.com/1/user/-/body/weight/date/today/1y.json", headers=h).json()
                fat = requests.get("https://api.fitbit.com/1/user/-/body/fat/date/today/1y.json", headers=h).json()
                
                # Fetching Steps and Calories (30 days for detail)
                stp = requests.get("https://api.fitbit.com/1/user/-/activities/steps/date/today/30d.json", headers=h).json()
                cal = requests.get("https://api.fitbit.com/1/user/-/activities/calories/date/today/30d.json", headers=h).json()
                
                # Fetching Sleep (Last 10 records)
                slp = requests.get("https://api.fitbit.com/1.2/user/-/sleep/list.json?afterDate=2024-01-01&limit=10&sort=desc", headers=h).json()

                # Cleanup for AI
                weight_list = wgt.get('body-weight', [])[-30:] # Last 30 entries
                fat_list = fat.get('body-fat', [])[-30:]
                step_list = stp.get('activities-steps', [])
                cal_list = cal.get('activities-calories', [])
                sleep_list = [{"date": s['dateOfSleep'], "hrs": round(s['minutesAsleep']/60, 1), "eff": s['efficiency']} for s in slp.get('sleep', [])]

                st.session_state.data = {
                    "Weight_History_kg": weight_list,
                    "Body_Fat_History": fat_list,
                    "Steps_30_Days": step_list,
                    "Calories_Burned_30_Days": cal_list,
                    "Sleep_Summary": sleep_list
                }
                st.success("Synced! Every metric is now visible to the AI.")
                st.rerun()

    # 6. CHAT
    if st.session_state.data:
        for m in st.session_state.ms:
            with st.chat_message(m["role"]): st.markdown(m["content"])
        if p := st.chat_input("Analyze my weight and activity..."):
            st.session_state.ms.append({"role": "user", "content": p})
            with st.chat_message("user"): st.markdown(p)
            with st.chat_message("assistant"):
                with st.spinner("AI is thinking..."):
                    ans = ask_ai(st.session_state.data, p)
                    st.markdown(ans)
                    st.session_state.ms.append({"role": "assistant", "content": ans})

elif code:
    try:
        auth_b64 = base64.b64encode(f"{CID}:{SEC}".encode()).decode()
        r = requests.post("https://api.fitbit.com/oauth2/token", 
            headers={"Authorization": f"Basic {auth_b64}", "Content-Type": "application/x-www-form-urlencoded"},
            data={"grant_type": "authorization_code", "code": code, "redirect_uri": URI}).json()
        st.session_state.tk = r.get("access_token")
        st.query_params.clear()
        st.rerun()
    except: st.error("Login failed.")
else:
    url = f"https://www.fitbit.com/oauth2/authorize?response_type=code&client_id={CID}&scope=activity%20heartrate%20nutrition%20profile%20sleep%20weight&redirect_uri={URI}"
    st.markdown(f"### [🔗 Connect Fitbit]({url})")

# END OF CODE
