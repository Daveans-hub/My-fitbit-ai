import streamlit as st
import requests
import base64
import json
from datetime import datetime, timedelta

# 1. LOAD SECRETS
CID, SEC, GKEY, URI = st.secrets["FITBIT_CLIENT_ID"], st.secrets["FITBIT_CLIENT_SECRET"], st.secrets["GEMINI_API_KEY"], st.secrets["YOUR_SITE_URL"]

# 2. PERFORMANCE COACH AI ENGINE
def ask_ai(ctx, q):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GKEY}"
    payload = {
        "contents": [{"parts": [{"text": f"You are an Elite Performance Coach & Data Scientist. Analyze this master dataset for correlations and regressions. \n\n DATA: {ctx} \n\n REQUEST: {q}"}]}],
        "safetySettings": [{"category": c, "threshold": "BLOCK_NONE"} for c in ["HARM_CATEGORY_HARASSMENT", "HARM_CATEGORY_HATE_SPEECH", "HARM_CATEGORY_SEXUALLY_EXPLICIT", "HARM_CATEGORY_DANGEROUS_CONTENT"]]
    }
    try:
        r = requests.post(url, json=payload, timeout=60)
        return r.json()['candidates'][0]['content']['parts'][0]['text']
    except Exception as e:
        return f"Coach is busy. Error: {e}"

# 3. PAGE SETUP & STYLING
st.set_page_config(page_title="Performance AI", layout="wide")

# Custom CSS for Aquamarine Sidebar and Uniform Buttons
st.markdown("""
    <style>
        [data-testid="stSidebar"] {
            background-color: #7FFFD4;
        }
        .stButton>button {
            width: 100%;
            border-radius: 5px;
            height: 3em;
            background-color: white;
            color: black;
            border: 1px solid #ccc;
        }
    </style>
    """, unsafe_allow_html=True)

if "tk" not in st.session_state: st.session_state.tk = None
if "cached_data" not in st.session_state: st.session_state.cached_data = None
if "ms" not in st.session_state: st.session_state.ms = []

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
    # --- SIDEBAR ---
    st.sidebar.title("Coach Control")
    
    st.sidebar.subheader("Step 1. Trends")
    if st.sidebar.button("⚖️ Weight & Fat% Impact"):
        st.session_state.ms.append({"role": "user", "content": "What is having the most impact on my weight and body fat %? Analyze calories in/out, steps, and macronutrient trends."})
    
    if st.sidebar.button("🌙 Sleep Quality Impact"):
        st.session_state.ms.append({"role": "user", "content": "What is having the most impact on my sleep score? Analyze activity, heart rate, and macros."})
        
    if st.sidebar.button("💪 Muscle Mass Impact"):
        st.session_state.ms.append({"role": "user", "content": "What is having the most impact on my muscle mass? Compare protein/activity to my calculated lean mass."})

    st.sidebar.subheader("Step 2. Coaching")
    if st.sidebar.button("🚀 How do I improve this?"):
        if st.session_state.ms:
            prev = st.session_state.ms[-1]["content"]
            st.session_state.ms.append({"role": "user", "content": f"Based on the analysis of '{prev}', give me a 3-step specific action plan to improve these metrics."})
        else: st.sidebar.warning("Run a trend analysis first!")

    st.sidebar.divider()
    if st.sidebar.button("Logout / Reset"):
        st.session_state.tk, st.session_state.cached_data, st.session_state.ms = None, None, []
        st.query_params.clear()
        st.rerun()

    # --- CENTER PAGE ---
    st.title("🔬 Total Performance Analyst")

    if not st.session_state.cached_data:
        st.info("Your dashboard is empty. We need to weave your 90-day history.")
        if st.button("🔄 Sync & Weave Master Dataset"):
            with st.status("Fetching performance vitals...", expanded=True) as status:
                h = {"Authorization": f"Bearer {st.session_state.tk}"}
                try:
                    # Fetching
                    s = requests.get("https://api.fitbit.com/1/user/-/activities/steps/date/today/90d.json", headers=h).json().get('activities-steps', [])
                    w = requests.get("https://api.fitbit.com/1/user/-/body/weight/date/today/90d.json", headers=h).json().get('body-weight', [])
                    f = requests.get("https://api.fitbit.com/1/user/-/body/fat/date/today/90d.json", headers=h).json().get('body-fat', [])
                    cout = requests.get("https://api.fitbit.com/1/user/-/activities/calories/date/today/90d.json", headers=h).json().get('activities-calories', [])
                    slp_raw = requests.get("https://api.fitbit.com/1.2/user/-/sleep/list.json?afterDate=2024-01-01&limit=50&sort=desc", headers=h).json().get('sleep', [])

                    # Macro Loop
                    macros = []
                    pb = st.progress(0)
                    for i in range(1, 91):
                        pb.progress(i/90)
                        d_str = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
                        log = requests.get(f"https://api.fitbit.com/1/user/-/foods/log/date/{d_str}.json", headers=h).json().get('summary', {})
                        if log and log.get('calories', 0) > 0:
                            macros.append({"date": d_str, "p": log.get('protein', 0), "f": log.get('fat', 0), "c": log.get('carbs', 0), "in": log.get('calories', 0)})
                    
                    # WEAVER
                    master = {}
                    def ingest(d_list, key, label, val_key='value'):
                        for x in d_list:
                            d = x.get('dateTime') or x.get('date')
                            if d:
                                if d not in master: master[d] = {"s":0,"w":0,"f":0,"out":0,"in":0,"p":0,"carb":0,"fat":0,"score":0}
                                master[d][label] = x.get(val_key, 0)

                    ingest(s, 'value', 's'); ingest(w, 'weight', 'w', 'weight'); ingest(f, 'fat', 'f', 'fat'); ingest(cout, 'value', 'out')
                    for m in macros:
                        if m['date'] in master: master[m['date']].update({"in": m['in'], "p": m['p'], "carb": m['c'], "fat": m['fat']})
                    for sl in slp_raw:
                        if sl['dateOfSleep'] in master: master[sl['dateOfSleep']]['score'] = sl.get('efficiency', 0)

                    rows = ["Date,Steps,Weight,Fat%,MuscleMass,CalIn,CalOut,Protein,Carbs,Fat,SleepScore"]
                    for d in sorted(master.keys(), reverse=True):
                        v = master[d]
                        muscle = round(float(v['w']) * (1 - (float(v['f'])/100)), 2) if float(v['f']) > 0 else 0
                        rows.append(f"{d},{v['s']},{v['w']},{v['f']},{muscle},{v['in']},{v['out']},{v['p']},{v['carb']},{v['fat']},{v['score']}")

                    st.session_state.cached_data = "\n".join(rows)
                    status.update(label="✅ Weaving Complete!", state="complete")
                    st.rerun()
                except Exception as e: st.error(f"Sync failed: {e}")

    # --- CHAT UI ---
    if st.session_state.cached_data:
        for m in st.session_state.ms:
            with st.chat_message(m["role"]): st.markdown(m["content"])
        
        if st.session_state.ms and st.session_state.ms[-1]["role"] == "user":
            if "l_ans" not in st.session_state or st.session_state.l_ans != len(st.session_state.ms):
                with st.chat_message("assistant"):
                    with st.spinner("Coach is analyzing..."):
                        ans = ask_ai(st.session_state.cached_data, st.session_state.ms[-1]["content"])
                        st.markdown(ans)
                        st.session_state.ms.append({"role": "assistant", "content": ans})
                        st.session_state.l_ans = len(st.session_state.ms)

        if p := st.chat_input("Ask a follow-up question..."):
            st.session_state.ms.append({"role": "user", "content": p})
            st.rerun()

else:
    # LANDING PAGE
    st.title("🏃 Performance Coach AI")
    url = f"https://www.fitbit.com/oauth2/authorize?response_type=code&client_id={CID}&scope=activity%20heartrate%20nutrition%20profile%20sleep%20weight&redirect_uri={URI}"
    st.markdown(f"### [🔗 Connect Performance Coach]({url})")

# --- END OF APP ---
