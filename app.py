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
def ask_ai_auto(ctx, q):
    list_url = f"https://generativelanguage.googleapis.com/v1/models?key={GKEY}"
    try:
        m_data = requests.get(list_url).json()
        all_m = [m["name"] for m in m_data.get("models", []) if "generateContent" in m.get("supportedGenerationMethods", [])]
        target = next((m for m in all_m if "gemini-1.5-flash" in m), all_m[0])
        gen_url = f"https://generativelanguage.googleapis.com/v1/{target}:generateContent?key={GKEY}"
        
        # System instructions to help AI handle massive data
        sys_instructions = "You are a long-term health data scientist. Analyze the following 1-year data trends. Look for seasonal patterns, long-term improvements, or plateaus."
        payload = {"contents": [{"parts": [{"text": f"{sys_instructions}\n\nData: {ctx}\n\nQuestion: {q}"}]}]}
        
        res = requests.post(gen_url, json=payload)
        return res.json()["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        return f"AI Error: {str(e)}"

# 3. PAGE SETUP
st.set_page_config(page_title="Lifetime Health AI", layout="wide")
st.title("📊 Lifetime Health Trend Analyst")

if "tk" not in st.session_state: st.session_state.tk = None
if "ms" not in st.session_state: st.session_state.ms = []

# 4. LOGIC ENGINE
code = st.query_params.get("code")

if st.session_state.tk:
    st.sidebar.success("✅ Long-Term Data Access Active")
    if st.sidebar.button("Logout"):
        st.session_state.tk = None
        st.session_state.ms = []
        st.query_params.clear()
        st.rerun()

    hdr = {"Authorization": f"Bearer {st.session_state.tk}"}
    
    with st.spinner("Processing 1 year of health records... this may take a moment."):
        try:
            # PULLING 1 YEAR OF DATA (The maximum Fitbit allows per request)
            # Sleep: Pulls the last 100 logs (roughly 3-4 months of sleep)
            sleep = requests.get("https://api.fitbit.com/1.2/user/-/sleep/list.json?afterDate=2020-01-01&limit=100&sort=desc", headers=hdr).json()
            
            # Steps & Calories: 1 Year Time Series
            steps_yr = requests.get("https://api.fitbit.com/1/user/-/activities/steps/date/today/1y.json", headers=hdr).json()
            cal_yr = requests.get("https://api.fitbit.com/1/user/-/activities/calories/date/today/1y.json", headers=hdr).json()
            
            # Weight & Fat: 1 Year Time Series
            weight_yr = requests.get("https://api.fitbit.com/1/user/-/body/log/weight/date/today/1y.json", headers=hdr).json()
            fat_yr = requests.get("https://api.fitbit.com/1/user/-/body/log/fat/date/today/1y.json", headers=hdr).json()
            
            # Pack it for the AI
            ctx = {
                "Historical_Steps": steps_yr,
                "Historical_Calories_Burned": cal_yr,
                "Historical_Weight": weight_yr,
                "Historical_Fat_Percent": fat_yr,
                "Recent_Sleep_Logs": sleep
            }
        except Exception as e:
            ctx = f"Data sync issue: {e}"

    # Chat UI
    for m in st.session_state.ms:
        with st.chat_message(m["role"]): st.markdown(m["content"])

    if p := st.chat_input("Ask about long-term trends (e.g., 'How has my weight changed compared to my steps over the last year?')"):
        st.session_state.ms.append({"role": "user", "content": p})
        with st.chat_message("user"): st.markdown(p)
        with st.chat_message("assistant"):
            with st.spinner("Analyzing 1 year of data..."):
                ans = ask_ai_auto(ctx, p)
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
    except: st.error("Connection error.")

else:
    full_scope = "activity%20heartrate%20nutrition%20profile%20sleep%20weight"
    link = f"https://www.fitbit.com/oauth2/authorize?response_type=code&client_id={CID}&scope={full_scope}&redirect_uri={URI}"
    st.markdown(f"### [🔗 Connect Fitbit for Lifetime Analysis]({link})")

# END OF CODE
