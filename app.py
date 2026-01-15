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
        sys_instructions = "You are a professional health data scientist. Analyze the following health metrics. Look for correlations between activity, heart rate, nutrition, and sleep."
        payload = {"contents": [{"parts": [{"text": f"{sys_instructions}\n\nData: {ctx}\n\nQuestion: {q}"}]}]}
        
        res = requests.post(gen_url, json=payload)
        return res.json()["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        return f"AI Error: {str(e)}"

# 3. PAGE SETUP
st.set_page_config(page_title="Total Health AI", layout="wide")
st.title("🏃 Total Health AI Analyst")

if "tk" not in st.session_state: st.session_state.tk = None
if "ms" not in st.session_state: st.session_state.ms = []

# 4. LOGIC ENGINE
code = st.query_params.get("code")

if st.session_state.tk:
    st.sidebar.success("✅ Total Access Active")
    if st.sidebar.button("Logout"):
        st.session_state.tk = None
        st.session_state.ms = []
        st.query_params.clear()
        st.rerun()

    hdr = {"Authorization": f"Bearer {st.session_state.tk}"}
    
    with st.spinner("Processing your lifetime health records..."):
        try:
            # PULLING 1 YEAR OF DIVERSE DATA
            # Activity Time Series
            steps = requests.get("https://api.fitbit.com/1/user/-/activities/steps/date/today/1y.json", headers=hdr).json()
            distance = requests.get("https://api.fitbit.com/1/user/-/activities/distance/date/today/1y.json", headers=hdr).json()
            azm = requests.get("https://api.fitbit.com/1/user/-/activities/active-zone-minutes/date/today/1y.json", headers=hdr).json()
            
            # Nutrition (Last 30 Days - Nutrition is data-heavy)
            nutrition = requests.get("https://api.fitbit.com/1/user/-/foods/log/date/today/30d.json", headers=hdr).json()
            
            # Weight, Fat, BMI (1 Year)
            weight = requests.get("https://api.fitbit.com/1/user/-/body/log/weight/date/today/1y.json", headers=hdr).json()
            fat = requests.get("https://api.fitbit.com/1/user/-/body/log/fat/date/today/1y.json", headers=hdr).json()
            
            # Heart & Vitals
            heart = requests.get("https://api.fitbit.com/1/user/-/activities/heart/date/today/7d.json", headers=hdr).json()
            # HRV (Heart Rate Variability - key for recovery)
            hrv = requests.get("https://api.fitbit.com/1/user/-/hrv/date/today/30d.json", headers=hdr).json()
            
            # Sleep (Last 50 Logs)
            sleep = requests.get("https://api.fitbit.com/1.2/user/-/sleep/list.json?afterDate=2020-01-01&limit=50&sort=desc", headers=hdr).json()
            
            # Pack it for the AI
            ctx = {
                "Step_History": steps,
                "Distance_History": distance,
                "Intensity_Minutes": azm,
                "Weight_Trend": weight,
                "Fat_Percentage": fat,
                "Recent_HRV": hrv,
                "Resting_HR": heart,
                "Nutrition_Summary": nutrition,
                "Sleep_History": sleep
            }
        except Exception as e:
            ctx = f"Data sync issue: {e}"

    # Chat UI
    for m in st.session_state.ms:
        with st.chat_message(m["role"]): st.markdown(m["content"])

    if p := st.chat_input("Ask about your total health..."):
        st.session_state.ms.append({"role": "user", "content": p})
        with st.chat_message("user"): st.markdown(p)
        with st.chat_message("assistant"):
            with st.spinner("AI is analyzing total records..."):
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
    # SCOPE: Added 'nutrition', 'heartrate', 'weight', and 'activity'
    full_scope = "activity%20heartrate%20nutrition%20profile%20sleep%20weight"
    link = f"https://www.fitbit.com/oauth2/authorize?response_type=code&client_id={CID}&scope=full_scope&redirect_uri={URI}"
    # Re-using scope variable name for the link
    link = link.replace("full_scope", full_scope)
    st.markdown(f"### [🔗 Connect Fitbit for Total Analysis]({link})")
    st.info("Check 'Allow All' on the next screen to include Nutrition, Weight, and HRV data.")

# END OF CODE
