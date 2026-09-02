import os
import requests
from groq import Groq
from openai import OpenAI
import logging

def generate_gemini(prompt):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key: raise ValueError("GEMINI_API_KEY missing")
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite:generateContent?key={api_key}"
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
        client = Groq(api_key=api_key, max_retries=0)
        chat_completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="openai/gpt-oss-20b",
            max_tokens=1024
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
            max_retries=0
        )
        completion = client.chat.completions.create(
            model="nvidia/nemotron-3.5-lightning:free",
            messages=[{"role": "user", "content": prompt}]
        )
        return completion.choices[0].message.content
    except Exception as e:
        logging.error(f"OpenRouter API Error: {e}")
        raise e

def generate_ollama(prompt):
    url = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
    payload = {
        "model": os.getenv("OLLAMA_MODEL", "gpt-oss:20b"),
        "prompt": prompt,
        "stream": False
    }
    headers = {}
    api_key = os.getenv("OLLAMA_API_KEY")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
        
    response = requests.post(url, json=payload, headers=headers, timeout=120)
    response.raise_for_status()
    return response.json()["response"]

def generate_openai(prompt):
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key: raise ValueError("OPENAI_API_KEY missing")
    try:
        client = OpenAI(api_key=api_key, max_retries=0)
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )
        return completion.choices[0].message.content
    except Exception as e:
        logging.error(f"OpenAI API Error: {e}")
        raise e

def generate_cerebras(prompt):
    api_key = os.getenv("CEREBRAS_API_KEY")
    if not api_key: raise ValueError("CEREBRAS_API_KEY missing")
    try:
        client = OpenAI(
            base_url="https://api.cerebras.ai/v1",
            api_key=api_key,
            max_retries=0
        )
        completion = client.chat.completions.create(
            model="llama3.1-70b",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1024
        )
        return completion.choices[0].message.content
    except Exception as e:
        logging.error(f"Cerebras API Error: {e}")
        raise e

def generate_huggingface(prompt):
    api_key = os.getenv("HUGGINGFACE_API_KEY")
    if not api_key: raise ValueError("HUGGINGFACE_API_KEY missing")
    try:
        # Use HuggingFace Inference API (Serverless)
        client = OpenAI(
            base_url="https://api-inference.huggingface.co/models/openai/gpt-oss-20b/v1/",
            api_key=api_key,
            max_retries=0
        )
        completion = client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1024
        )
        return completion.choices[0].message.content
    except Exception as e:
        logging.error(f"HuggingFace API Error: {e}")
        raise e

def generate_mistral(prompt):
    api_key = os.getenv("MISTRAL_API_KEY")
    if not api_key: raise ValueError("MISTRAL_API_KEY missing")
    try:
        client = OpenAI(
            base_url="https://api.mistral.ai/v1",
            api_key=api_key,
            max_retries=0
        )
        completion = client.chat.completions.create(
            model="ministral-8b-latest",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1024
        )
        return completion.choices[0].message.content
    except Exception as e:
        logging.error(f"Mistral API Error: {e}")
        raise e

def generate_cohere(prompt):
    api_key = os.getenv("COHERE_API_KEY")
    if not api_key: raise ValueError("COHERE_API_KEY missing")
    
    url = "https://api.cohere.ai/v1/chat"
    payload = {
        "model": "command-r7b-12-2024",
        "message": prompt
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=120)
        response.raise_for_status()
        return response.json()["text"]
    except Exception as e:
        logging.error(f"Cohere API Error: {e}")
        raise e

def generate_nvidia(prompt):
    api_key = os.getenv("NVIDIA_API_KEY")
    if not api_key: raise ValueError("NVIDIA_API_KEY missing")
    try:
        client = OpenAI(
            base_url="https://integrate.api.nvidia.com/v1",
            api_key=api_key,
            max_retries=0
        )
        completion = client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1024
        )
        return completion.choices[0].message.content
    except Exception as e:
        logging.error(f"Nvidia API Error: {e}")
        raise e

def generate_cloudflare(prompt):
    account_id = os.getenv("CLOUDFLARE_ACCOUNT_ID")
    token = os.getenv("CLOUDFLARE_API_TOKEN")
    if not account_id or not token: raise ValueError("Cloudflare credentials missing")
    
    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/@cf/openai/gpt-oss-20b"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = {
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 1024
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=120)
        response.raise_for_status()
        return response.json()["result"]["choices"][0]["message"]["content"]
    except Exception as e:
        logging.error(f"Cloudflare AI Error: {e}")
        raise e

def generate_zhipu(prompt):
    api_key = os.getenv("ZHIPU_API_KEY")
    if not api_key: raise ValueError("ZHIPU_API_KEY missing")
    try:
        client = OpenAI(
            base_url="https://open.bigmodel.cn/api/paas/v4/",
            api_key=api_key,
            max_retries=0
        )
        completion = client.chat.completions.create(
            model="glm-4.5-air",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1024
        )
        return completion.choices[0].message.content
    except Exception as e:
        logging.error(f"Zhipu API Error: {e}")
        raise e

def generate_pollinations(prompt):
    api_key = os.getenv("POLLINATIONS_API_KEY")
    if not api_key: raise ValueError("POLLINATIONS_API_KEY missing")
    try:
        client = OpenAI(
            base_url="https://text.pollinations.ai/openai/",
            api_key=api_key,
            max_retries=0,
            default_headers={"User-Agent": "Mozilla/5.0"}
        )
        completion = client.chat.completions.create(
            model="gpt-oss-20b",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1024
        )
        return completion.choices[0].message.content
    except Exception as e:
        logging.error(f"Pollinations API Error: {e}")
        raise e

def generate_llm7(prompt):
    api_key = os.getenv("LLM7_API_KEY")
    if not api_key: raise ValueError("LLM7_API_KEY missing")
    try:
        client = OpenAI(
            base_url="https://api.llm7.io/v1",
            api_key=api_key,
            max_retries=0
        )
        completion = client.chat.completions.create(
            model="gpt-oss",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1024
        )
        return completion.choices[0].message.content
    except Exception as e:
        logging.error(f"LLM7 API Error: {e}")
        raise e

def generate_sambanova(prompt):
    api_key = os.getenv("SAMBANOVA_API_KEY")
    if not api_key: raise ValueError("SAMBANOVA_API_KEY missing")
    try:
        client = OpenAI(
            base_url="https://api.sambanova.ai/v1",
            api_key=api_key,
            max_retries=0
        )
        completion = client.chat.completions.create(
            model="Meta-Llama-3.3-70B-Instruct",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1024
        )
        return completion.choices[0].message.content
    except Exception as e:
        logging.error(f"SambaNova API Error: {e}")
        raise e

def generate_vercel(prompt):
    api_key = os.getenv("VERCEL_AI_GATEWAY_API_KEY")
    if not api_key: raise ValueError("VERCEL_AI_GATEWAY_API_KEY missing")
    try:
        client = OpenAI(
            base_url="https://ai-gateway.vercel.sh/v1",
            api_key=api_key,
            max_retries=0
        )
        completion = client.chat.completions.create(
            model="openai/gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1024
        )
        return completion.choices[0].message.content
    except Exception as e:
        logging.error(f"Vercel AI Gateway Error: {e}")
        raise e

# The Fallback Chain order
PROVIDERS = [
    ("Ollama", generate_ollama),
    ("Groq", generate_groq),
    ("OpenRouter", generate_openrouter),
    ("Nvidia", generate_nvidia),
    ("Cloudflare", generate_cloudflare),
    ("HuggingFace", generate_huggingface),
    ("Mistral", generate_mistral),
    ("LLM7", generate_llm7),
    ("OpenAI", generate_openai),
    ("Gemini", generate_gemini),
    ("Cohere", generate_cohere),
    ("Zhipu", generate_zhipu)
]
