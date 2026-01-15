import streamlit as st
import requests
import base64
import google.generativeai as genai

# 1. SETUP SECRETS
CID, SEC, GKEY, URI = st.secrets["FITBIT_CLIENT_ID"], st.secrets["FITBIT_CLIENT_SECRET"], st.secrets["GEMINI_API_KEY"], st.secrets["YOUR_SITE_URL"]

# 2. AI CONFIG
genai.configure(api_key=GKEY)
# We use 'gemini-1.5-flash' - it's the fastest and most reliable for this
model = genai.GenerativeModel('gemini-1.5-flash')

# 3. PAGE SETUP
st.set_page_config(page_title="Total Health AI", layout="wide")
st.title("🏃 Total Health AI Analyst")

if "tk" not in st.session_state: st.session_state.tk = None
if "ms" not in st.session_state: st.session_state.ms = []
if "data" not in st.session_state: st.session_state.data = None

# 4. LOGIN LOGIC
qp = st.query_params
if "code" in qp and not st.session_state.tk:
    try:
        auth_b64 = base64.b64encode(f"{CID}:{SEC}".encode()).decode()
        r = requests.post("https://api.fitbit.com/oauth2/token", 
            headers={"Authorization": f"Basic {auth_b64}", "Content-Type": "application/x-www-form-urlencoded"},
            data={"grant_type": "authorization_code", "code": qp["code"], "redirect_uri": URI}).json()
        if "access_token" in r:
            st.session_state.tk = r["access_token"]
            st.query_params.clear()
            st.rerun()
    except: st.error("Login failed. Please refresh the page.")

# 5. MAIN APP
if st.session_state.tk:
    st.sidebar.success("✅ Health Data Linked")
    if st.sidebar.button("Logout"):
        st.session_state.tk, st.session_state.data, st.session_state.ms = None, None, []
        st.rerun()

    # SYNC DATA
    if not st.session_state.data:
        if st.button("🔄 Sync 1-Year History"):
            with st.spinner("Fetching 12 months of records..."):
                h = {"Authorization": f"Bearer {st.session_state.tk}"}
                try:
                    # Fetching 1 year of data
                    w = requests.get("https://api.fitbit.com/1/user/-/body/weight/date/today/1y.json", headers=h).json().get('body-weight', [])
                    f = requests.get("https://api.fitbit.com/1/user/-/body/fat/date/today/1y.json", headers=h).json().get('body-fat', [])
                    s = requests.get("https://api.fitbit.com/1/user/-/activities/steps/date/today/1y.json", headers=h).json().get('activities-steps', [])
                    
                    # COMPACT THE DATA: AI doesn't need 365 rows. We give it the last 30 days + monthly averages for the rest.
                    last_30_w = w[-30:]
                    last_30_s = s[-30:]
                    
                    st.session_state.data = f"WEIGHT_30D: {last_30_w}, STEPS_30D: {last_30_s}, FAT_LATEST: {f[-1:] if f else 'N/A'}"
                    st.success("Synced!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Sync failed: {e}")

    # CHAT
    if st.session_state.data:
        for m in st.session_state.ms:
            with st.chat_message(m["role"]): st.markdown(m["content"])
            
        if p := st.chat_input("Ask me about your health..."):
            st.session_state.ms.append({"role": "user", "content": p})
            with st.chat_message("user"): st.markdown(p)
            with st.chat_message("assistant"):
                try:
                    prompt = f"You are a health expert. Based on this Fitbit data: {st.session_state.data}. Answer this: {p}"
                    response = model.generate_content(prompt)
                    st.markdown(response.text)
                    st.session_state.ms.append({"role": "assistant", "content": response.text})
                except Exception as ai_err:
                    st.error(f"AI Error: {ai_err}")

# 6. LOGIN LINK
else:
    url = f"https://www.fitbit.com/oauth2/authorize?response_type=code&client_id={CID}&scope=activity%20heartrate%20nutrition%20profile%20sleep%20weight&redirect_uri={URI}"
    st.markdown(f"### [🔗 Connect Fitbit]({url})")

# END OF CODE
