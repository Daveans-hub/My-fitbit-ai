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
                    "matrix": "\n".join(rows),  # Changed from rows[:60]
                    "sleep_logs": slp_clean
                }
                
                st.success(f"✅ Data Weaved! Loaded {len(rows)-1} days of data.")
                st.rerun()
            except Exception as e: 
                st.error(f"Sync failed: {e}")
                import traceback
                st.code(traceback.format_exc())
