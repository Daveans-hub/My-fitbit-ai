import streamlit as st
import requests
import base64
import google.generativeai as genai

# --- CLOUD CONFIG ---
CLIENT_ID = st.secrets["FITBIT_CLIENT_ID"]
CLIENT_SECRET = st.secrets["FITBIT_CLIENT_SECRET"]
GEMINI_KEY = st.secrets["GEMINI_API_KEY"]
REDIRECT_URI = st.secrets["YOUR_SITE_URL"] 

# Setup AI
genai.configure(api_key=GEMINI_KEY)

# --- RESILIENT AI FUNCTION ---
def ask_ai(data_context, user_question):
    # Try different model names to bypass cloud 404 errors
    model_names = [
        'gemini-1.5-flash-latest', 
        'gemini-1.5-flash', 
        'models/gemini-1.5-flash',
        'gemini-pro'
    ]
    
    error_log = []
    for name in model_names:
        try:
            model = genai.GenerativeModel(name)
            full_prompt = f"You are a professional health analyst. Context: {data_context}. Question: {user_question}"
            response = model.generate_content(full_prompt)
            return response.text
        except Exception as e:
            error_log.append(f"{name}: {str(e)}")
            continue
            
    return f"AI Error: Could not connect to models. Details: {error_log}"

# --- PAGE SETUP ---
st.set_page_config(page_title="Fitbit AI Assistant", layout="wide")
st.title("🏃 My Personal Health AI")

if "access_token" not in st.session_state:
    st.session_state.access_token = None
if "messages" not in st.session_state:
    st.session_state.messages = []

# --- AUTH LOGIC ---
code = st.query_params.get("code")

if not st.session_state.access_token and not code:
    scope = "activity%20heartrate%20profile%20sleep%20weight%20nutrition"
    auth_url = f"https://www.fitbit.com/oauth2/authorize?response_type=code&client_id={CLIENT_ID}&scope={scope}&redirect_uri={REDIRECT_URI}"
    st.info("Your AI is offline. Please connect your Fitbit.")
    st.markdown(f'### [🔗 Click here to Connect Fitbit]({auth_url})')

elif code and not st.session_state.access_token:
    try:
        token_url = "https://api.fitbit.com/oauth2/token"
        basic_auth = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
        headers = {"Authorization": f"Basic {basic_auth}", "Content-Type": "application/x-www-form-urlencoded"}
        data = {"grant_type": "authorization_code", "code": code, "redirect_uri": REDIRECT_URI}
        resp = requests.post(token_url, headers=headers, data=data).json()
        if "access_token" in resp:
            st.session_state.access_token = resp["access_token"]
            st.query_params.clear()
            st.rerun()
    except Exception as e:
        st.error(f"Login Error: {e}")

# --- MAIN APP ---
if st.session_state.access_token:
    st.sidebar.success("✅ AI Connected")
    if st.sidebar.button("Logout"):
        st.session_state.access_token = None
        st.session_state.messages = []
        st.rerun()

    h = {"Authorization": f"Bearer {st.session_state.access_token}"}
    
    with st.spinner("Syncing your vitals..."):
        try:
            sleep = requests.get("https://api.fitbit.com/1.2/user/-/sleep/list.json?afterDate=2024-01-01&sort=desc&offset=0&limit=5", headers=h).json()
            steps = requests.get("https://api.fitbit.com/1/user/-/activities/steps/date/today/7d.json", headers=h).json()
            heart = requests.get("https://api.fitbit.com/1/user/-/activities/heart/date/today/1d.json", headers=h).json()
            data_context = f"Sleep: {sleep}, Steps: {steps}, Heart: {heart}"
        except:
            data_context = "Data currently syncing..."

    st.subheader("Conversation with your Health Agent")
    
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("Ask about your trends..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        
        with st.chat_message("assistant"):
            with st.spinner("AI is analyzing..."):
                answer = ask_ai(data_context, prompt)
                st.markdown(answer)
                st.session_state.messages.append({"role": "assistant", "content": answer})
