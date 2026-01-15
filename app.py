import streamlit as st
import requests
import base64
import json

# 1. LOAD SECRETS
CID = st.secrets["FITBIT_CLIENT_ID"]
SEC = st.secrets["FITBIT_CLIENT_SECRET"]
GKEY = st.secrets["GEMINI_API_KEY"]
URI = st.secrets["YOUR_SITE_URL"]

# 2. AUTO-DETECTING AI FUNCTION
def ask_ai_auto(ctx, q):
    list_url = f"https://generativelanguage.googleapis.com/v1/models?key={GKEY}"
    try:
        m_data = requests.get(list_url).json()
        all_m = [m["name"] for m in m_data.get("models", []) if "generateContent" in m.get("supportedGenerationMethods", [])]
        if not all_m: return "Error: No AI models available for this key."
        target = next((m for m in all_m if "gemini-1.5-flash" in m), all_m[0])
        gen_url = f"https://generativelanguage.googleapis.com/v1/{target}:generateContent?key={GKEY}"
        payload = {"contents": [{"parts": [{"text": f"Fitbit Data: {ctx}. User Question: {q}"}]}]}
        res = requests.post(gen_url, json=payload)
        return res.json()["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        return f"AI Error: {str(e)}"

# 3. PAGE SETUP
st.set_page_config(page_title="Health AI")
st.title("🏃 My Personal Health AI")

if "tk" not in st.session_state: st.session_state.tk = None
if "ms" not in st.session_state: st.session_state.ms = []

# 4. EXCLUSIVE LOGIC (Prevents Ghost Errors)
code = st.query_params.get("code")

# Case A: Already Logged In
if st.session_state.tk:
    st.sidebar.success("✅ Connected")
    if st.sidebar.button("Logout / Reset"):
        st.session_state.tk = None
        st.session_state.ms = []
        st.query_params.clear()
        st.rerun()

    hdr = {"Authorization": f"Bearer {st.session_state.tk}"}
    try:
        slp = requests.get("https://api.fitbit.com/1.2/user/-/sleep/list.json?afterDate=2024-01-01&limit=3", headers=hdr).json()
        stp = requests.get("https://api.fitbit.com/1/user/-/activities/steps/date/today/7d.json", headers=hdr).json()
        ctx = f"Sleep: {slp}, Steps: {stp}"
    except: ctx = "Syncing data..."

    for m in st.session_state.ms:
        with st.chat_message(m["role"]): st.markdown(m["content"])

    if p := st.chat_input("Ask me something..."):
        st.session_state.ms.append({"role": "user", "content": p})
        with st.chat_message("user"): st.markdown(p)
        with st.chat_message("assistant"):
            with st.spinner("AI is thinking..."):
                ans = ask_ai_auto(ctx, p)
                st.markdown(ans)
                st.session_state.ms.append({"role": "assistant", "content": ans})

# Case B: Just returned from Fitbit with a code
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
        else:
            st.error("Login failed. Please try the link again.")
    except:
        st.error("Connection issue during login.")

# Case C: First visit, not logged in
else:
    link = f"https://www.fitbit.com/oauth2/authorize?response_type=code&client_id={CID}&scope=activity%20heartrate%20profile%20sleep%20weight&redirect_uri={URI}"
    st.markdown(f"### [🔗 Click here to Connect Fitbit]({link})")

# END OF CODE
