import streamlit as st
import requests
import base64
import json

# 1. LOAD SECRETS
CID, SEC, GKEY, URI = st.secrets["FITBIT_CLIENT_ID"], st.secrets["FITBIT_CLIENT_SECRET"], st.secrets["GEMINI_API_KEY"], st.secrets["YOUR_SITE_URL"]

# 2. THE SELF-HEALING AI ENGINE
def ask_ai(ctx, q):
    try:
        # STEP A: Discovery - Ask Google what models are active for your key right now
        # We try v1beta as it is currently the most compatible for model listing
        list_url = f"https://generativelanguage.googleapis.com/v1beta/models?key={GKEY}"
        model_list = requests.get(list_url).json()
        
        # Filter for models that actually support chat/content generation
        available = [
            m['name'] for m in model_list.get('models', []) 
            if 'generateContent' in m.get('supportedGenerationMethods', [])
        ]
        
        if not available:
            return "AI Snag: No models found for this API key. Please check Google AI Studio."

        # STEP B: Selection - Automatically pick the best model from the list
        # Prefer 1.5 Flash, then Pro, otherwise take the first valid one
        selected_model = next((m for m in available if "1.5-flash" in m), 
                         next((m for m in available if "gemini-pro" in m), available[0]))

        # STEP C: Execution - Use the full path provided by Google
        gen_url = f"https://generativelanguage.googleapis.com/v1beta/{selected_model}:generateContent?key={GKEY}"
        
        payload = {
            "contents": [{"parts": [{"text": f"You are a Health Data Scientist. DATA: {str(ctx)[:15000]}. QUESTION: {q}"}]}],
            "safetySettings": [{"category": c, "threshold": "BLOCK_NONE"} for c in ["HARM_CATEGORY_HARASSMENT", "HARM_CATEGORY_HATE_SPEECH", "HARM_CATEGORY_SEXUALLY_EXPLICIT", "HARM_CATEGORY_DANGEROUS_CONTENT"]]
        }

        r = requests.post(gen_url, json=payload, timeout=90)
        res = r.json()
        
        if "candidates" in res:
            return res["candidates"][0]["content"]["parts"][0]["text"]
        return f"AI Snag: Google refused the request. Details: {res}"
        
    except Exception as e:
        return f"System Snag: {str(e)}"

# 3. PAGE SETUP
st.set_page_config(page_title="Health Analyst Pro", layout="wide")
st.title("🔬 Lifetime Correlation & Regression AI")

if "tk" not in st.session_state: st.session_state.tk = None
if "ms" not in st.session_state: st.session_state.ms = []
if "data" not in st.session_state: st.session_state.data = None

# 4. LOGIN LOGIC
qp = st.query_params
if "code" in qp and not st.session_state.tk:
    try:
        auth_b = base64.b64encode(f"{CID}:{SEC}".encode()).decode()
        r = requests.post("https://api.fitbit.com/oauth2/token", 
            headers={"Authorization": f"Basic {auth_b}", "Content-Type": "application/x-www-form-urlencoded"},
            data={"grant_type": "authorization_code", "code": qp["code"], "redirect_uri": URI}).json()
        if "access_token" in r:
            st.session_state.tk = r["access_token"]
            st.query_params.clear()
            st.rerun()
    except: st.error("Login failed.")

# 5. MAIN APP
if st.session_state.tk:
    # --- SIDEBAR: ASK AI SECTION ---
    st.sidebar.success("✅ Linked to Fitbit")
    st.sidebar.divider()
    st.sidebar.header("Ask AI")
    
    if st.sidebar.button("Can you see my data?"):
        if st.session_state.data:
            st.session_state.ms.append({"role": "user", "content": "Can you see my data?"})
        else:
            st.sidebar.error("Sync data first!")

    if st.sidebar.button("Logout / Reset"):
        st.session_state.tk, st.session_state.data, st.session_state.ms = None, None, []
        st.query_params.clear()
        st.rerun()

    # --- DATA SYNC ---
    if not st.session_state.data:
        if st.button("🔄 Sync 12-Month Master Table"):
            with st.spinner("Analyzing 12 months of records..."):
                h = {"Authorization": f"Bearer {st.session_state.tk}"}
                try:
                    s = requests.get("https://api.fitbit.com/1/user/-/activities/steps/date/today/1y.json", headers=h).json().get('activities-steps', [])
                    w = requests.get("https://api.fitbit.com/1/user/-/body/weight/date/today/1y.json", headers=h).json().get('body-weight', [])
                    f = requests.get("https://api.fitbit.com/1/user/-/body/fat/date/today/1y.json", headers=h).json().get('body-fat', [])
                    ci = requests.get("https://api.fitbit.com/1/user/-/foods/log/caloriesIn/date/today/1y.json", headers=h).json().get('foods-log-caloriesIn', [])
                    
                    master = {}
                    for i in s: master[i['dateTime']] = [i['value'], "0", "0", "0"]
                    for i in w: 
                        if i['dateTime'] in master: master[i['dateTime']][1] = i['value']
                    for i in f: 
                        if i['dateTime'] in master: master[i['dateTime']][2] = i['value']
                    for i in ci: 
                        if i['dateTime'] in master: master[i['dateTime']][3] = i['value']

                    rows = ["Date,Steps,Weight,Fat%,CalIn"]
                    for d in sorted(master.keys(), reverse=True):
                        v = master[d]
                        if v[1] != "0": 
                            rows.append(f"{d},{v[0]},{v[1]},{v[2]},{v[3]}")
                    
                    st.session_state.data = "\n".join(rows[:60])
                    st.success("Synced!")
                    st.rerun()
                except Exception as e: st.error(f"Sync failed: {e}")

    # --- CHAT UI ---
    if st.session_state.data:
        for m in st.session_state.ms:
            with st.chat_message(m["role"]): st.markdown(m["content"])
            
        # Automatic response for the Sidebar Button
        if st.session_state.ms and st.session_state.ms[-1]["role"] == "user" and st.session_state.ms[-1]["content"] == "Can you see my data?":
            if "last_processed" not in st.session_state or st.session_state.last_processed != len(st.session_state.ms):
                with st.chat_message("assistant"):
                    with st.spinner("Checking records..."):
                        ans = ask_ai(st.session_state.data, "Confirm exactly what metrics you see and the date range.")
                        st.markdown(ans)
                        st.session_state.ms.append({"role": "assistant", "content": ans})
                        st.session_state.last_processed = len(st.session_state.ms)

        # Chat Input
        if p := st.chat_input("Ask for analysis..."):
            st.session_state.ms.append({"role": "user", "content": p})
            with st.chat_message("user"): st.markdown(p)
            with st.chat_message("assistant"):
                with st.spinner("Calculating..."):
                    ans = ask_ai(st.session_state.data, p)
                    st.markdown(ans)
                    st.session_state.ms.append({"role": "assistant", "content": ans})

else:
    url = f"https://www.fitbit.com/oauth2/authorize?response_type=code&client_id={CID}&scope=activity%20heartrate%20nutrition%20profile%20sleep%20weight&redirect_uri={URI}"
    st.markdown(f"### [🔗 Connect Fitbit]({url})")

# --- END OF APP ---
