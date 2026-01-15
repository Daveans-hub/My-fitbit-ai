import streamlit as st
import requests
import base64
import google.generativeai as genai

# --- CLOUD CONFIG ---
CLIENT_ID = st.secrets["FITBIT_CLIENT_ID"]
CLIENT_SECRET = st.secrets["FITBIT_CLIENT_SECRET"]
GEMINI_KEY = st.secrets["GEMINI_API_KEY"]
REDIRECT_URI = st.secrets["YOUR_SITE_URL"] 

# Setup AI with the most stable model name
try:
    genai.configure(api_key=GEMINI_KEY)
    # Changed to 'gemini-1.5-flash' (removed -latest for better cloud compatibility)
    model = genai.GenerativeModel('gemini-1.5-flash')
except Exception as e:
    st.error(f"AI Setup Error: {e}")

st.set_page_config(page_title="Fitbit AI Assistant", layout="wide")
st.title("🏃 My Personal Health AI")

if "access_token" not in st.session_state:
    st.session_state.access_token = None
if "messages" not in st.session_state:
    st.session_state.messages = []

query_params = st.query_params

# 1. Login Link
if not st.session_state.access_token and "code" not in query_params:
    scope = "activity%20heartrate%20profile%20sleep%20weight%20nutrition"
    auth_url = f"https://www.fitbit.com/oauth2/authorize?response_type=code&client_id={CLIENT_ID}&scope={scope}&redirect_uri={REDIRECT_URI}"
    st.info("Your AI is currently offline.")
    st.markdown(f'### [🔗 Click here to Connect Fitbit]({auth_url})')

# 2. Handle the redirect
elif "code" in query_params and st.session_state.access_token is None:
    try:
        auth_code = query_params["code"].replace("#_=_", "")
        token_url = "https://api.fitbit.com/oauth2/token"
        basic_auth = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
        headers = {"Authorization": f"Basic {basic_auth}", "Content-Type": "application/x-www-form-urlencoded"}
        data = {"grant_type": "authorization_code", "code": auth_code, "redirect_uri": REDIRECT_URI}
        token_resp = requests.post(token_url, headers=headers, data=data).json()
        if "access_token" in token_resp:
            st.session_state.access_token = token_resp["access_token"]
            st.rerun()
    except Exception as e:
        st.error(f"Auth Error: {e}")

# 3. Main App
if st.session_state.access_token:
    st.sidebar.success("✅ AI Connected")
    if st.sidebar.button("Logout"):
        st.session_state.access_token = None
        st.session_state.messages = []
        st.rerun()

    h = {"Authorization": f"Bearer {st.session_state.access_token}"}
    
    with st.spinner("Syncing your Fitbit data..."):
        try:
            sleep = requests.get("https://api.fitbit.com/1.2/user/-/sleep/list.json?afterDate=2024-01-01&sort=desc&offset=0&limit=7", headers=h).json()
            steps = requests.get("https://api.fitbit.com/1/user/-/activities/steps/date/today/7d.json", headers=h).json()
            weight = requests.get("https://api.fitbit.com/1/user/-/body/log/weight/date/today/7d.json", headers=h).json()
            heart = requests.get("https://api.fitbit.com/1/user/-/activities/heart/date/today/1d.json", headers=h).json()
            all_data_context = f"Sleep: {sleep} Steps: {steps} Weight: {weight} Heart: {heart}"
        except:
            all_data_context = "Data sync in progress..."

    st.subheader("Conversation with your Health Agent")
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("Ask about your trends..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            try:
                response = model.generate_content(f"Context: {all_data_context}. Question: {prompt}")
                st.markdown(response.text)
                st.session_state.messages.append({"role": "assistant", "content": response.text})
            except Exception as ai_err:
                st.error(f"AI Error: {ai_err}")
                st.info("The AI is having trouble accessing the model. Double check your API key in Secrets.")
