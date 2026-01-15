def ask_ai(master_table, sleep_data, user_query):
    # Using v1 API (more stable)
    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={GKEY}"
    
    prompt = f"""
    You are a professional health data scientist. 
    Analyze the following 12-month dataset for correlations and regressions.
    
    DATA (Date, Steps, Weight, Fat%, CaloriesIn, CaloriesOut):
    {master_table}
    
    SLEEP HISTORY:
    {sleep_data}
    
    USER QUESTION: {user_query}
    
    OUTPUT: Provide a statistical analysis. If a correlation is weak, say so. 
    Focus on patterns between activity, sleep, and weight.
    """
    
    safety_settings = [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
    ]
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "safetySettings": safety_settings
    }
    
    try:
        res = requests.post(url, json=payload, timeout=60)
        data = res.json()
        
        if "candidates" in data and len(data["candidates"]) > 0:
            return data["candidates"][0]["content"]["parts"][0]["text"]
        elif "error" in data:
            return f"Google API Error: {data['error']['message']}"
        else:
            return f"AI Refusal. Data received: {json.dumps(data)[:500]}"
            
    except Exception as e:
        return f"System Error: {str(e)}"
