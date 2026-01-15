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
    # Fallback names to handle different server versions
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

st.set_page_config(page_title="Fitbit AI Assistant", layout="wide")
st.title("🏃
