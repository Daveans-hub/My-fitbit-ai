import streamlit as st
import requests
import base64
import json

# 1. LOAD SECRETS
CID, SEC, GKEY, URI = st.secrets["FITBIT_CLIENT_ID"], st.secrets["FITBIT_CLIENT_SECRET"], st.secrets["GEMINI_API_KEY"], st.secrets["YOUR_SITE_URL"]

# 2. THE PERFORMANCE COACH AI ENGINE
def ask_ai(ctx, q):
    try:
        list_url = f"https://generativelanguage.googleapis.com/v1beta/models?key={GKEY}"
        m_list = requests.get(list_url).json()
        available = [m['name'] for m in m_list.get('models', []) if 'generateContent' in m.get('supportedGenerationMethods', [])]
        model_path = next((m for m in available if "1.5-flash" in m), available[0])
        gen_url = f"https://generativelanguage.googleapis.com/v1beta/{model_path}:generateContent?key={GKEY}"
        
        prompt = f"""
        You are an Elite Performance Coach. Analyze the health metrics below.
        
        REQUIRED CALCULATIONS:
        - Muscle Mass (Lean Mass) = Weight * (1 - (Fat% / 100)). Use this for the 'Muscle' analysis.
        
        COACHING STYLE:
        - Be numeric and specific. 
        - Look for "Drivers": Does high protein correlate with muscle stability? Do high steps improve sleep?
        - If data is missing (shown as 0), mention it briefly but focus on the trends that ARE present.
        
        DATASET:
        {ctx}
        
        USER REQUEST:
        {q}
        """
        
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        r = requests.post(gen_url, json=payload, timeout=90)
        res = r.json()
        if "candidates" in res:
            return res["candidates"][0]["content"]["parts"][0]["text"]
        return f"AI Snag: {res}"
    except Exception as e:
        return f"System Error: {str(e)}"

# 3. PAGE SETUP
st.set_page_config(page_title="Performance Coach AI", layout="wide")
st.title("🔬 Elite Performance & Health Analyst")

# Initialize session state IMMEDIATELY
if "tk" not in st.session_state: st.session_state.tk = None
if "ms" not in st.session_state: st.session_state.ms = []
if "data" not in st.session_state: st.session_state.data = None
if "last_ans" not in st.session_state: st.session_state.last_ans = 0

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
    st.sidebar.success("✅ Fitbit Link Active")
    st.sidebar.divider()
    
    # --- SIDEBAR BUTTONS ---
    st.sidebar.header("Step 1: Trend Analysis")
    if st.sidebar.button("⚖️ What's impacting my Weight/Fat%?"):
        st.session_state.ms.append({"role": "user", "content": "What is having the most impact on my weight and body fat %? Look at my calories in/out and activity trends."})
    
    if st.sidebar.button("🌙 What's impacting my Sleep?"):
        st.session_state.ms.append({"role": "user", "content": "What is having the most impact on my sleep? Analyze my activity, heart rate, and macros to find correlations."})
        
    if st.sidebar.button("💪 What's impacting my Muscle Mass?"):
        st.session_state.ms.append({"role": "user", "content": "What is having the most impact on my muscle mass? Compare my protein intake and activity levels to my calculated muscle mass logs."})

    st.sidebar.header("Step 2: Action Plan")
    if st.sidebar.button("🚀 How do I improve this?"):
        if st.session_state.ms:
            topic = st.session_state.ms[-1]["content"]
            st.session_state.ms.append({"role": "user", "content": f"Based on the analysis of '{topic}', how do I improve this? Give me a highly specific action plan."})
        else: st.sidebar.warning("Run an analysis first.")

    st.sidebar.header("Step 3: Deep Correlations")
    if st.sidebar.button("🍗 Protein vs Muscle Gains"):
        st.session_state.ms.append({"role": "user", "content": "Analyze the relationship between my protein intake and my muscle mass logs. Am I eating enough protein to see gains?"})
    
    if st.sidebar.button("🚶 Steps vs Deep Sleep"):
        st.session_state.ms.append({"role": "user", "content": "Compare my deep sleep minutes to my daily step count. Do I get more deep sleep on days when I walk over 15,000 steps?"})
    
    if st.sidebar.button("🍎 Food Log Analysis"):
        st.session_state.ms.append({"role": "user", "content": "Look at my food logs. Is there anything impacting my weight loss, muscle gain, or sleep?"})

    st.sidebar.divider()
    if st.sidebar.button("Logout"):
        st.session_state.tk, st.session_state.data, st.session_state.ms = None, None, []
        st.rerun()

    # --- DATA WEAVER (The fix for empty rows) ---
    if not st.session_state.data:
        if st.button("🔄 Sync Total Performance History"):
            with st.spinner("Weaving 90 days of performance vitals..."):
                h = {"Authorization": f"Bearer {st.session_state.tk}"}
                try:
                    # Fetching - Store responses for debugging
                    s_resp = requests.get("https://api.fitbit.com/1/user/-/activities/steps/date/today/90d.json", headers=h).json()
                    w_resp = requests.get("https://api.fitbit.com/1/user/-/body/weight/date/today/90d.json", headers=h).json()
                    f_resp = requests.get("https://api.fitbit.com/1/user/-/body/fat/date/today/90d.json", headers=h).json()
                    cin_resp = requests.get("https://api.fitbit.com/1/user/-/foods/log/caloriesIn/date/today/90d.json", headers=h).json()
                    prot_resp = requests.get("https://api.fitbit.com/1/user/-/foods/log/protein/date/today/90d.json", headers=h).json()
                    carb_resp = requests.get("https://api.fitbit.com/1/user/-/foods/log/carbs/date/today/90d.json", headers=h).json()
                    slp_resp = requests.get("https://api.fitbit.com/1.2/user/-/sleep/list.json?afterDate=2024-10-01&limit=90&sort=desc", headers=h).json()

                    # Extract data arrays
                    s = s_resp.get('activities-steps', [])
                    w = w_resp.get('body-weight', [])
                    f = f_resp.get('body-fat', [])
                    cin = cin_resp.get('foods-log-caloriesIn', [])
                    prot = prot_resp.get('foods-log-protein', [])
                    carb = carb_resp.get('foods-log-carbs', [])
                    slp_r = slp_resp.get('sleep', [])

                    # Debug: Show what we received
                    st.write(f"Debug: Steps entries: {len(s)}, Weight: {len(w)}, Fat: {len(f)}, Calories: {len(cin)}, Protein: {len(prot)}, Carbs: {len(carb)}")

                    # Normalize dates across all lists
                    master = {}
                    def ingest(data_list, key_name):
                        for entry in data_list:
                            d = entry.get('dateTime') or entry.get('date')
                            if d:
                                if d not in master: 
                                    master[d] = {"s":"0","w":"0","f":"0","cal":"0","p":"0","c":"0"}
                                # Handle both string and numeric values
                                val = entry.get('value', 0)
                                master[d][key_name] = str(val) if val else "0"

                    ingest(s, "s"); ingest(w, "w"); ingest(f, "f")
                    ingest(cin, "cal"); ingest(prot, "p"); ingest(carb, "c")

                    # Build the CSV table
                    rows = ["Date,Steps,Weight,Fat%,Calories,Protein,Carbs"]
                    for d in sorted(master.keys(), reverse=True):
                        v = master[d]
                        rows.append(f"{d},{v['s']},{v['w']},{v['f']},{v['cal']},{v['p']},{v['c']}")
                    
                    # Show how many data rows we built
                    st.write(f"Debug: Built {len(rows)-1} data rows")
                    
                    # Process sleep data
                    slp_clean = []
                    for x in slp_r:
                        if 'levels' in x and 'summary' in x['levels']:
                            deep_mins = x['levels']['summary'].get('deep', {}).get('minutes', 0)
                        else:
                            deep_mins = 0
                        slp_clean.append({
                            "date": x.get('dateOfSleep', 'unknown'), 
                            "deep": deep_mins, 
                            "total": x.get('minutesAsleep', 0)
                        })
                    
                    # Store ALL rows, not just 60
                    st.session_state.data = {
                        "matrix": "\n".join(rows),
                        "sleep_logs": slp_clean
                    }
                    
                    st.success(f"✅ Data Weaved! Loaded {len(rows)-1} days of data.")
                    st.rerun()
                except Exception as e: 
                    st.error(f"Sync failed: {e}")
                    import traceback
                    st.code(traceback.format_exc())

    # --- CHAT UI ---
    if st.session_state.data:
        for m in st.session_state.ms:
            with st.chat_message(m["role"]): st.markdown(m["content"])
            
        if st.session_state.ms and st.session_state.ms[-1]["role"] == "user":
            if st.session_state.last_ans != len(st.session_state.ms):
                with st.chat_message("assistant"):
                    with st.spinner("Coach is analyzing..."):
                        ans = ask_ai(st.session_state.data, st.session_state.ms[-1]["content"])
                        st.markdown(ans)
                        st.session_state.ms.append({"role": "assistant", "content": ans})
                        st.session_state.last_ans = len(st.session_state.ms)

        if p := st.chat_input("Custom question..."):
            st.session_state.ms.append({"role": "user", "content": p})
            st.rerun()

else:
    scope = "activity%20heartrate%20nutrition%20profile%20sleep%20weight"
    link = f"https://www.fitbit.com/oauth2/authorize?response_type=code&client_id={CID}&scope={scope}&redirect_uri={URI}"
    st.markdown(f"### [🔗 Connect Total Health Data]({link})")
