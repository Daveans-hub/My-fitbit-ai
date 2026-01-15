import streamlit as st
import requests
import base64
import google.generativeai as genai

# --- CLOUD CONFIG ---
# These must be set in your Streamlit "Secrets"
CLIENT_ID = st.secrets["FITBIT_CLIENT_ID"]
CLIENT_SECRET = st.secrets["FITBIT_CLIENT_SECRET"]
GEMINI_KEY = st.secrets["GEMINI_API_KEY"]
REDIRECT_URI = st.secrets["YOUR_SITE_URL"] 

# Setup AI
genai.configure(api_key=GEMINI_KEY)
# We use this specific path to avoid the 404 error
model = genai.GenerativeModel('models/gemini-1.5-flash')

st.set_page_config(page_title="Fitbit AI Assistant", layout="wide")
st.title("🏃 My Personal Health AI")

# Memory
if "access_token" not in st.session_state:
    st.session_state.access_token = None
if "messages" not in st.session_state:
    st.session_state.messages = []

# --- AUTH LOGIC ---
# Get the code from the URL
code = st.query_params.get("code")

# 1. No token, No code -> Show Login Link
if not st.session_state.access_token and not code:
    scope = "activity%20heartrate%20profile%20sleep%20weight%20nutrition"
    auth_url = f"https://www.fitbit.com/oauth2/authorize?response_type=code&client_id={CLIENT_ID}&scope={scope}&redirect_uri={REDIRECT_URI}"
    st.info("Your AI is offline. Please connect your Fitbit.")
    st.markdown(f'### [🔗 Click here to Connect Fitbit]({auth_url})')

# 2. We have a code -> Exchange it for a Token
elif code and not st.session_state.access_token:
    with st.spinner("Connecting to Fitbit..."):
        try:
            token_url = "https://api.fitbit.com/oauth2/token"
            basic_auth = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
            headers = {"Authorization": f"Basic {basic_auth}", "Content-Type": "application/x-www-form-urlencoded"}
            data = {"grant_type": "authorization_code", "code": code, "redirect_uri": REDIRECT_URI}
            
            resp = requests.post(token_url, headers=headers, data=data).json()
            
            if "access_token" in resp:
                st.session_state.access_token = resp["access_token"]
                st.query_params.clear() # Clean the URL
                st.rerun()
            else:
                st.error("Fitbit rejected the connection.")
                st.write(resp) # Shows exactly why it failed
        except Exception as e:
            st.error(f"Error during login: {e}")

# 3. We are logged in -> Show the Chat
if st.session_state.access_token:
    st.sidebar.success("✅ AI Connected")
    if st.sidebar.button("Logout"):
        st.session_state.access_token = None
        st.session_state.messages = []
        st.rerun()

    h = {"Authorization": f"Bearer {st.session_state.access_token}"}
    
    with st.spinner("Syncing your vitals..."):
        try:
            # Get data for the AI to read
            sleep = requests.get("https://api.fitbit.com/1.2/user/-/sleep/list.json?afterDate=2024-01-01&sort=desc&offset=0&limit=5", headers=h).json()
            steps = requests.get("https://api.fitbit.com/1/user/-/activities/steps/date/today/7d.json", headers=h).json()
            heart = requests.get("https://api.fitbit.com/1/user/-/activities/heart/date/today/1d.json", headers=h).json()
            data_context = f"Context: Sleep logs: {sleep}, Steps: {steps}, Heart: {heart}"
        except:
            data_context = "Data currently unavailable."

    st.subheader("Conversation with your Health Agent")
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("Ask about your trends..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        
        with st.chat_message("assistant"):
            try:
                full_prompt = f"You are a helpful health AI. Using this data: {data_context}, answer this: {prompt}"
                response = model.generate_content(full_prompt)
                st.markdown(response.text)
                st.session_state.messages.append({"role": "assistant", "content": response.text})
            except Exception as e:
                st.error(f"AI Error: {e}")
