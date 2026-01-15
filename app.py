import streamlit as st
import requests
import base64
import json

# 1. LOAD SECRETS
CID = st.secrets["FITBIT_CLIENT_ID"]
SEC = st.secrets["FITBIT_CLIENT_SECRET"]
GKEY = st.secrets["GEMINI_API_KEY"]
URI = st.secrets["YOUR_SITE_URL"]

# 2. THE AI FUNCTION
def ask_ai(ctx, q):
    list_url = f"https://generativelanguage.googleapis.com/v1/models?key={GKEY}"
    try:
        models_resp = requests.get(list_url).json()
        available_names = [m['name'] for m in models_resp.get('models', []) if 'generateContent' in m.get('supportedGenerationMethods', [])]
        selected_model = next((n for n in available_names if "1.5-flash" in n), available_names[0])
        gen_url = f"https://generativelanguage.googleapis.com/v1/{selected_model}:generateContent?key={GKEY}"
        
        payload = {
            "contents": [{
                "parts": [{"text": f"You are a health analyst. I am providing my Fitbit data. Analyze the trends and answer the question. \n\n DATA: {ctx} \n\n QUESTION: {q}"}]
            }]
        }
        res = requests.post(gen_url, json=payload, timeout=30)
        return res.json()["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        return f"AI Error: {str(e)}"

# 3. PAGE SETUP
st.set_page_config(page_title="Total Health AI", layout="wide")
st.title("🏃 My Personal Health AI")

if "tk" not in st.session_state: st.session_state.tk = None
if "ms" not in st.session_state: st.session_state.ms = []
if "health_ctx" not in st.session_state: st.session_state.health_ctx = None

# 4. LOGIC ENGINE
if st.session_state.tk:
    st.sidebar.success("✅ Connected")
    if st.sidebar.button("Logout"):
        st.session_state.tk = None
        st.session_state.health_ctx = None
        st.session_state.ms = []
        st.rerun()

    # 5. SMART DATA SYNC (Detailed Month + 1 Year Summary)
    if not st.session_state.health_ctx:
        st.info("Syncing your data history...")
        if st.button("🔄 Sync My Health Records"):
            with st.spinner("Fetching steps, weight, sleep, and calories..."):
                h = {"Authorization": f"Bearer {st.session_state.tk}"}
                try:
                    # Pull 1 Year of everything
                    steps_yr = requests.get("https://api.fitbit.com/1/user/-/activities/steps/date/today/1y.json", headers=h).json().get('activities-steps', [])
                    weight_yr = requests.get("https://api.fitbit.com/1/user/-/body/log/weight/date/today/1y.json", headers=h).json().get('weight', [])
                    cals_yr = requests.get("https://api.fitbit.com/1/user/-/activities/calories/date/today/1y.json", headers=h).json().get('activities-calories', [])
                    sleep = requests.get("https://api.fitbit.com/1.2/user/-/sleep/list.json?afterDate=2024-01-01&limit=20&sort=desc", headers=h).json().get('sleep', [])

                    # Organize into a "Cheat Sheet" for the AI
                    # We take the last 30 days for daily detail, and the rest as a general trend
                    st.session_state.health_ctx = {
                        "DAILY_DETAIL_LAST_30_DAYS": {
                            "steps": steps_yr[-30:],
                            "weight": weight_yr[-30:],
                            "calories_burned": cals_yr[-30:]
                        },
                        "LONG_TERM_TREND_LAST_YEAR": {
                            "step_samples": steps_yr[::30], # Every 30th day to show the trend
                            "weight_samples": weight_yr[::30]
                        },
                        "RECENT_SLEEP_LOGS": sleep[:10]
                    }
                    st.success("Sync Complete! Ask me anything.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Sync failed: {e}")

    # 6. CHAT
    if st.session_state.health_ctx:
        for m in st.session_state.ms:
            with st.chat_message(m["role"]): st.markdown(m["content"])

        if p := st.chat_input("Ask about your trends (e.g., 'Analyze my weight vs steps')"):
            st.session_state.ms.append({"role": "user", "content": p})
            with st.chat_message("user"): st.markdown(p)
            with st.chat_message("assistant"):
                with st.spinner("AI is analyzing..."):
                    ans = ask_ai(st.session_state.health_ctx, p)
                    st.markdown(ans)
                    st.session_state.ms.append({"role": "assistant", "content": ans})
        
        with st.expander("Debug: See exactly what the AI sees"):
            st.write(st.session_state.health_ctx)

elif st.query_params.get("code"):
    code = st.query_params.get("code")
    auth = base64.b64encode(f"{CID}:{SEC}".encode()).decode()
    r = requests.post("https://api.fitbit.com/oauth2/token", 
        headers={"Authorization": f"Basic {auth}", "Content-Type": "application/x-www-form-urlencoded"},
        data={"grant_type": "authorization_code", "code": code, "redirect_uri": URI}).json()
    if "access_token" in r:
        st.session_state.tk = r["access_token"]
        st.query_params.clear()
        st.rerun()
else:
    scope = "activity%20heartrate%20nutrition%20profile%20sleep%20weight"
    link = f"https://www.fitbit.com/oauth2/authorize?response_type=code&client_id={CID}&scope={scope}&redirect_uri={URI}"
    st.markdown(f"### [🔗 Connect Fitbit]({link})")
