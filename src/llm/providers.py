import os
import requests
from groq import Groq
from openai import OpenAI
import logging

def generate_gemini(prompt):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key: raise ValueError("GEMINI_API_KEY missing")
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ],
        "tools": [
            {
                "googleSearch": {}
            }
        ]
    }
    
    response = requests.post(url, json=payload)
    if response.status_code != 200:
        raise Exception(f"Gemini API Error {response.status_code}: {response.text}")
        
    data = response.json()
    try:
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except KeyError:
        raise Exception(f"Unexpected Gemini response format: {data}")

def generate_groq(prompt):
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key: raise ValueError("GROQ_API_KEY missing")
    try:
        client = Groq(api_key=api_key)
        chat_completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.1-8b-instant",
        )
        return chat_completion.choices[0].message.content
    except Exception as e:
        logging.error(f"Groq API Error: {e}")
        raise e

def generate_openrouter(prompt):
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key: raise ValueError("OPENROUTER_API_KEY missing")
    try:
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
        )
        completion = client.chat.completions.create(
            model="mistralai/mistral-7b-instruct:free",
            messages=[{"role": "user", "content": prompt}]
        )
        return completion.choices[0].message.content
    except Exception as e:
        logging.error(f"OpenRouter API Error: {e}")
        raise e

def generate_ollama(prompt):
    url = "http://localhost:11434/api/generate"
    payload = {
        "model": "llama3",
        "prompt": prompt,
        "stream": False
    }
    response = requests.post(url, json=payload, timeout=30)
    response.raise_for_status()
    return response.json()["response"]

# The Fallback Chain order
PROVIDERS = [
    ("Gemini", generate_gemini),
    ("Groq", generate_groq),
    ("OpenRouter", generate_openrouter),
    ("Ollama", generate_ollama)
]
