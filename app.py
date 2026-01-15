import streamlit as st
import requests
import base64
import json

# 1. LOAD SECRETS
CID, SEC, GKEY, URI = st.secrets["FITBIT_CLIENT_ID"], st.secrets["FITBIT_CLIENT_SECRET"], st.secrets["GEMINI_API_KEY"], st.secrets["YOUR_SITE_URL"]

# 2. OPTIMIZED AI FUNCTION
def ask_ai(master_table, sleep_data, user_query):
    try:
        # Increase timeout to 60s for heavy analysis
        url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={GKEY}"
        
        prompt = f"""
        You are a health data scientist. Use the following 12-month data table to perform correlations, 
        regressions, and trend analysis. Newest dates are at the top.
        
        DATA TABLE (Date, Steps, Weight, Fat%, CalIn, CalOut):
        {master_table}
        
        RECENT SLEEP LOGS:
        {sleep_data}
        
        USER QUESTION: {user_query}
        
        INSTRUCTIONS: 
        - Look for statistical links (e.g., 'When steps increase, weight follows X trend').
        - If 'Calories In' is 0, ignore that specific day for nutrition analysis.
        - Be precise and professional.
        """
        
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        res = requests.post(url, json=payload, timeout=60)
        return res.json()["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        return f"AI Analysis Snag: {str(e)}"

# 3. PAGE SETUP
st.set_page_config(page_title="Health Data Scientist", layout="wide")
st.title("🔬 Lifetime Correlation & Regression AI")

if "tk" not in st.session_state: st.session_state.tk = None
if "ms" not in st.session_state: st.session_state.ms = []
if "master_data" not in st.session_state: st.session_state.master_data = None

# 4. LOGIN LOGIC
qp = st.query_params
if "code" in qp and not st.session_state.tk:
    try:
        auth_b = base64.b64encode(f"{CID}:{SEC}".encode()).decode()
        r = requests.post("https://api.fitbit.com/oauth2/token", 
            headers={"Authorization": f"Basic {auth_b}", "Content-Type": "application/x-www-form-urlencoded"},
            data={"grant_type": "authorization_code", "code": qp["code"], "redirect_uri": URI}).json()
        st.session_state.tk = r.get("access_token")
        st.query_params.clear()
        st.rerun()
    except: st.error("Login failed.")

# 5. MAIN APP
if st.session_state.tk:
    st.sidebar.success("✅ Linked")
    if st.sidebar.button("Logout / Reset"):
        st.session_state.tk, st.session_state.master_data, st.session_state.ms = None, None, []
        st.rerun()

    # THE MASTER SYNC (12 Months of Raw Data)
    if not st.session_state.master_data:
        if st.button("🔄 Perform Full 12-Month Data Sync"):
            with st.spinner("Building your lifetime health table..."):
                h = {"Authorization": f"Bearer {st.session_state.tk}"}
                try:
                    # 1. Fetch 1 year for all 5 major metrics
                    s_raw = requests.get("https://api.fitbit.com/1/user/-/activities/steps/date/today/1y.json", headers=h).json().get('activities-steps', [])
                    w_raw = requests.get("https://api.fitbit.com/1/user/-/body/weight/date/today/1y.json", headers=h).json().get('body-weight', [])
                    f_raw = requests.get("https://api.fitbit.com/1/user/-/body/fat/date/today/1y.json", headers=h).json().get('body-fat', [])
                    co_raw = requests.get("https://api.fitbit.com/1/user/-/activities/calories/date/today/1y.json", headers=h).json().get('activities-calories', [])
                    ci_raw = requests.get("https://api.fitbit.com/1/user/-/foods/log/caloriesIn/date/today/1y.json", headers=h).json().get('foods-log-caloriesIn', [])
                    slp = requests.get("https://api.fitbit.com/1.2/user/-/sleep/list.json?afterDate=2024-01-01&limit=50&sort=desc", headers=h).json().get('sleep', [])

                    # 2. Align data by date into a compact Master Table
                    master_dict = {}
                    for item in s_raw: master_dict[item['dateTime']] = [item['value'], "0", "0", "0", "0"] # Steps, Weight, Fat, CalIn, CalOut
                    for item in w_raw: 
                        if item['dateTime'] in master_dict: master_dict[item['dateTime']][1] = item['value']
                    for item in f_raw: 
                        if item['dateTime'] in master_dict: master_dict[item['dateTime']][2] = item['value']
                    for item in ci_raw: 
                        if item['dateTime'] in master_dict: master_dict[item['dateTime']][3] = item['value']
                    for item in co_raw: 
                        if item['dateTime'] in master_dict: master_dict[item['dateTime']][4] = item['value']

                    # 3. Create a clean CSV-style string (Most recent first)
                    table_rows = ["Date,Steps,Wgt,Fat%,In,Out"]
                    dates_sorted = sorted(master_dict.keys(), reverse=True)
                    for d in dates_sorted:
                        v = master_dict[d]
                        table_rows.append(f"{d},{v[0]},{v[1]},{v[2]},{v[3]},{v[4]}")
                    
                    sleep_summary = [{"date": s['dateOfSleep'], "hrs": round(s['minutesAsleep']/60, 1)} for s in slp]

                    st.session_state.master_data = {"table": "\n".join(table_rows), "sleep": sleep_summary}
                    st.success("Sync Complete! 12 months of daily data aligned.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Sync failed: {e}")

    # CHAT UI
    if st.session_state.master_data:
        for m in st.session_state.ms:
            with st.chat_message(m["role"]): st.markdown(m["content"])
            
        if p := st.chat_input("Perform correlation (e.g. 'What is the correlation between my steps and weight loss?')"):
            st.session_state.ms.append({"role": "user", "content": p})
            with st.chat_message("user"): st.markdown(p)
            with st.chat_message("assistant"):
                with st.spinner("Running statistical analysis..."):
                    ans = ask_ai(st.session_state.master_data["table"], st.session_state.master_data["sleep"], p)
                    st.markdown(ans)
                    st.session_state.ms.append({"role": "assistant", "content": ans})
        
        with st.expander("View the 12-Month Master Table aligned for AI"):
            st.text(st.session_state.master_data["table"])

else:
    url = f"https://www.fitbit.com/oauth2/authorize?response_type=code&client_id={CID}&scope=activity%20heartrate%20nutrition%20profile%20sleep%20weight&redirect_uri={URI}"
    st.markdown(f"### [🔗 Connect Fitbit]({url})")

# END OF CODE
