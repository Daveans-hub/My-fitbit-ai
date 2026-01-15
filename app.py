import streamlit as st
import requests
import base64
import json

# 1. LOAD SECRETS
CID, SEC, GKEY, URI = st.secrets["FITBIT_CLIENT_ID"], st.secrets["FITBIT_CLIENT_SECRET"], st.secrets["GEMINI_API_KEY"], st.secrets["YOUR_SITE_URL"]

# 2. THE "INTELLIGENT" AI FUNCTION
def ask_ai_dynamic(data_summary, user_query):
    # Step A: Ask Google for the list of models you are allowed to use
    try:
        model_list_url = f"https://generativelanguage.googleapis.com/v1/models?key={GKEY}"
        model_data = requests.get(model_list_url).json()
        
        # Find all models that support generating text
        available = [m["name"] for m in model_data.get("models", []) if "generateContent" in m.get("supportedGenerationMethods", [])]
        
        if not available:
            return "AI Error: Your API key does not have access to any models. Check AI Studio."

        # Pick the best model (Flash 1.5 if it exists, otherwise the first one)
        selected_model = next((m for m in available if "1.5-flash" in m), available[0])
        
        # Step B: Talk to that specific model using the stable v1 endpoint
        gen_url = f"https://generativelanguage.googleapis.com/v1/{selected_model}:generateContent?key={GKEY}"
        
        prompt = f"You are a total health analyst. Analyze this 1-year data summary: {data_summary}. User Question: {user_query}. (Note: Fitbit API excludes Menstrual data; analyze Heart/Weight for correlations if asked)."
        
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        res = requests.post(gen_url, json=payload, timeout=30)
        return res.json()["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        return f"AI Snag: {str(e)}"

# 3. PAGE SETUP
st.set_page_config(page_title="Total Health AI", layout="wide")
st.title("🏃 Total Health AI Analyst")

if "tk" not in st.session_state: st.session_state.tk = None
if "ms" not in st.session_state: st.session_state.ms = []
if "health_data" not in st.session_state: st.session_state.health_data = None

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
    except: st.error("Login failed. Please refresh.")

# 5. MAIN APP
if st.session_state.tk:
    st.sidebar.success("✅ Linked")
    if st.sidebar.button("Logout"):
        st.session_state.tk, st.session_state.health_data, st.session_state.ms = None, None, []
        st.query_params.clear()
        st.rerun()

    # THE "TOTAL SYNC"
    if not st.session_state.health_data:
        if st.button("🔄 Sync Everything (12 Months of Data)"):
            with st.spinner("Fetching weight, fat%, steps, calories, and sleep..."):
                h = {"Authorization": f"Bearer {st.session_state.tk}"}
                try:
                    # Pull all metrics
                    w = requests.get("https://api.fitbit.com/1/user/-/body/weight/date/today/1y.json", headers=h).json().get('body-weight', [])
                    f = requests.get("https://api.fitbit.com/1/user/-/body/fat/date/today/1y.json", headers=h).json().get('body-fat', [])
                    s = requests.get("https://api.fitbit.com/1/user/-/activities/steps/date/today/1y.json", headers=h).json().get('activities-steps', [])
                    c = requests.get("https://api.fitbit.com/1/user/-/activities/calories/date/today/1y.json", headers=h).json().get('activities-calories', [])
                    sl = requests.get("https://api.fitbit.com/1.2/user/-/sleep/list.json?afterDate=2024-01-01&limit=20&sort=desc", headers=h).json().get('sleep', [])
                    
                    # Reverse so AI sees Today first
                    w.reverse(); f.reverse(); s.reverse(); c.reverse()
                    
                    # COMPACT SUMMARY: Daily for last 14 days, Monthly for rest of year
                    summary = {
                        "DAILY_RECENT": {"Weight": w[:14], "Steps": s[:14], "Calories": c[:14]},
                        "SLEEP_LAST_20": [{"date": i['dateOfSleep'], "hrs": round(i['minutesAsleep']/60, 1)} for i in sl],
                        "FAT_PERCENT_LATEST": f[:5]
                    }
                    st.session_state.health_data = str(summary)
                    st.success("Total Health History Loaded!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Sync failed: {e}")

    # CHAT UI
    if st.session_state.health_data:
        for m in st.session_state.ms:
            with st.chat_message(m["role"]): st.markdown(m["content"])
            
        if p := st.chat_input("Ask about your trends (weight, sleep, calories, etc.)"):
            st.session_state.ms.append({"role": "user", "content": p})
            with st.chat_message("user"): st.markdown(p)
            with st.chat_message("assistant"):
                with st.spinner("AI is analyzing..."):
                    ans = ask_ai_dynamic(st.session_state.health_data, p)
                    st.markdown(ans)
                    st.session_state.ms.append({"role": "assistant", "content": ans})

else:
    # Scope includes activity, heartrate, nutrition, sleep, weight
    scope = "activity%20heartrate%20nutrition%20profile%20sleep%20weight"
    link = f"https://www.fitbit.com/oauth2/authorize?response_type=code&client_id={CID}&scope={scope}&redirect_uri={URI}"
    st.markdown(f"### [🔗 Connect Fitbit for Total Analysis]({link})")

# END OF CODE
