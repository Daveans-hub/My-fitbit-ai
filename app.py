import streamlit as st
import requests
import base64
import json

# 1. LOAD SECRETS
CID = st.secrets["FITBIT_CLIENT_ID"]
SEC = st.secrets["FITBIT_CLIENT_SECRET"]
GKEY = st.secrets["GEMINI_API_KEY"]
URI = st.secrets["YOUR_SITE_URL"]

# 2. BULLETPROOF AUTO-DETECT AI FUNCTION
def ask_ai(ctx, q):
    # Step A: Ask Google which models this API key is allowed to use
    list_url = f"https://generativelanguage.googleapis.com/v1/models?key={GKEY}"
    try:
        models_resp = requests.get(list_url).json()
        models = models_resp.get('models', [])
        
        # Step B: Find a model that supports 'generateContent'
        # We prefer 'gemini-1.5-flash', but we'll take whatever is available
        available_names = [m['name'] for m in models if 'generateContent' in m.get('supportedGenerationMethods', [])]
        
        if not available_names:
            return "Error: Your Google API key doesn't have access to any chat models yet."
        
        # Pick the best one: 1.5-flash is priority, otherwise the first one found
        selected_model = next((n for n in available_names if "1.5-flash" in n), available_names[0])
        
        # Step C: Send the actual request to that specific model
        # We use the full name provided by Google (e.g., 'models/gemini-1.5-flash')
        gen_url = f"https://generativelanguage.googleapis.com/v1/{selected_model}:generateContent?key={GKEY}"
        
        data_snippet = str(ctx)[:12000]
        payload = {
            "contents": [{
                "parts": [{"text": f"You are a professional health analyst. Data: {data_snippet}. Question: {q}"}]
            }]
        }
        
        res = requests.post(gen_url, json=payload, timeout=30)
        result = res.json()
        
        if "candidates" in result:
            return result["candidates"][0]["content"]["parts"][0]["text"]
        return f"AI Error: {result}"
        
    except Exception as e:
        return f"Connection Error: {str(e)}"

# 3. PAGE SETUP
st.set_page_config(page_title="Total Health AI", layout="wide")
st.title("📊 Total Health AI Assistant")

if "tk" not in st.session_state: st.session_state.tk = None
if "ms" not in st.session_state: st.session_state.ms = []
if "health_ctx" not in st.session_state: st.session_state.health_ctx = None

# 4. LOGIC ENGINE
code = st.query_params.get("code")

if st.session_state.tk:
    st.sidebar.success("✅ Connected")
    if st.sidebar.button("Logout / Reset"):
        st.session_state.tk = None
        st.session_state.health_ctx = None
        st.session_state.ms = []
        st.query_params.clear()
        st.rerun()

    # 5. DATA SYNC
    if not st.session_state.health_ctx:
        st.info("Please sync your data to begin analysis.")
        if st.button("🔄 Sync 1-Year History (Steps, Weight, Calories, Sleep)"):
            with st.spinner("Fetching your records..."):
                h = {"Authorization": f"Bearer {st.session_state.tk}"}
                try:
                    steps = requests.get("https://api.fitbit.com/1/user/-/activities/steps/date/today/1y.json", headers=h).json()
                    weight = requests.get("https://api.fitbit.com/1/user/-/body/log/weight/date/today/1y.json", headers=h).json()
                    calories = requests.get("https://api.fitbit.com/1/user/-/activities/calories/date/today/1y.json", headers=h).json()
                    sleep = requests.get("https://api.fitbit.com/1.2/user/-/sleep/list.json?afterDate=2020-01-01&limit=30&sort=desc", headers=h).json()
                    
                    st.session_state.health_ctx = {
                        "Steps": steps.get('activities-steps', []),
                        "Weight": weight.get('weight', []),
                        "Calories": calories.get('activities-calories', []),
                        "Sleep": sleep.get('sleep', [])
                    }
                    st.success("Sync Complete!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Sync failed: {e}")
    
    # 6. CHAT
    if st.session_state.health_ctx:
        for m in st.session_state.ms:
            with st.chat_message(m["role"]): st.markdown(m["content"])

        if p := st.chat_input("Ask about your trends..."):
            st.session_state.ms.append({"role": "user", "content": p})
            with st.chat_message("user"): st.markdown(p)
            with st.chat_message("assistant"):
                with st.spinner("AI is analyzing..."):
                    ans = ask_ai(st.session_state.health_ctx, p)
                    st.markdown(ans)
                    st.session_state.ms.append({"role": "assistant", "content": ans})

elif code:
    try:
        auth = base64.b64encode(f"{CID}:{SEC}".encode()).decode()
        r = requests.post("https://api.fitbit.com/oauth2/token", 
            headers={"Authorization": f"Basic {auth}", "Content-Type": "application/x-www-form-urlencoded"},
            data={"grant_type": "authorization_code", "code": code, "redirect_uri": URI}).json()
        if "access_token" in r:
            st.session_state.tk = r["access_token"]
            st.query_params.clear()
            st.rerun()
        else: st.error(f"Login Error: {r}")
    except Exception as e: st.error(f"System Error: {e}")

else:
    scope = "activity%20heartrate%20nutrition%20profile%20sleep%20weight"
    link = f"https://www.fitbit.com/oauth2/authorize?response_type=code&client_id={CID}&scope={scope}&redirect_uri={URI}"
    st.markdown(f"### [🔗 Connect Fitbit]({link})")

# END OF CODE
