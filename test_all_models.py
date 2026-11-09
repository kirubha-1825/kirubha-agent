import sys
import streamlit as st
import google.generativeai as genai
from openai import OpenAI

# Ensure UTF-8 output on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

print("\n" + "="*50)
print("       ALL LLM MODELS DIAGNOSTIC TEST       ")
print("="*50 + "\n")

# 1. TEST GOOGLE GEMINI (gemini-2.5-flash with 120s timeout)
print("--- [1/4] TESTING GOOGLE GEMINI ---")
gemini_key = st.secrets.get("GEMINI_API_KEY")
if not gemini_key:
    print("❌ GEMINI_API_KEY not found in secrets.toml")
else:
    try:
        genai.configure(api_key=gemini_key)
        model = genai.GenerativeModel("gemini-2.5-flash")
        res = model.generate_content("Hi", request_options={"timeout": 120})
        print("✅ Gemini Call Success! Model: gemini-2.5-flash, Response:", res.text.strip())
    except Exception as e:
        print("❌ Gemini Error:", e)

# 2. TEST NVIDIA BUILD
print("\n--- [2/4] TESTING NVIDIA BUILD ---")
nvidia_key = st.secrets.get("NVIDIA_API_KEY")
if not nvidia_key:
    print("❌ NVIDIA_API_KEY not found in secrets.toml")
else:
    try:
        client = OpenAI(
            base_url="https://integrate.api.nvidia.com/v1",
            api_key=nvidia_key
        )
        res = client.chat.completions.create(
            model="meta/llama-3.3-70b-instruct",
            messages=[{"role": "user", "content": "Hi"}],
            max_tokens=10
        )
        content = res.choices[0].message.content or getattr(res.choices[0].message, 'reasoning', '') or ""
        print("✅ NVIDIA Call Success! Response:", content.strip())
    except Exception as e:
        print("❌ NVIDIA Error:", e)

# 3. TEST GROQ
print("\n--- [3/4] TESTING GROQ ---")
groq_key = st.secrets.get("GROQ_API_KEY")
if not groq_key:
    print("❌ GROQ_API_KEY not found in secrets.toml")
else:
    try:
        client = OpenAI(
            base_url="https://api.groq.com/openai/v1",
            api_key=groq_key
        )
        res = client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[{"role": "user", "content": "Hi"}],
            max_tokens=10
        )
        content = res.choices[0].message.content or getattr(res.choices[0].message, 'reasoning', '') or ""
        print("✅ Groq Call Success! Response:", content.strip())
    except Exception as e:
        print("❌ Groq Error:", e)

# 4. TEST OPENROUTER FREE MULTI-MODEL FALLBACK LOOP
print("\n--- [4/4] TESTING OPENROUTER FREE MULTI-MODEL LOOP ---")
openrouter_key = st.secrets.get("OPENROUTER_API_KEY")
if not openrouter_key:
    print("❌ OPENROUTER_API_KEY not found in secrets.toml")
else:
    OPENROUTER_FREE_MODELS = [
        "google/gemini-2.0-flash-exp:free",
        "meta-llama/llama-3.3-70b-instruct:free",
        "deepseek/deepseek-chat-v3-0324:free",
        "qwen/qwen-2.5-coder-32b-instruct:free",
        "mistralai/mistral-small-3.1-24b-instruct:free",
        "openrouter/free"
    ]
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=openrouter_key,
        default_headers={
            "HTTP-Referer": "https://reakiruba.app",
            "X-Title": "SRI Diagnostic Test"
        }
    )
    succeeded = False
    for idx, model_name in enumerate(OPENROUTER_FREE_MODELS, 1):
        print(f"🔄 Trying OpenRouter Free Model [{idx}/{len(OPENROUTER_FREE_MODELS)}]: '{model_name}' (max_tokens=2048)...")
        try:
            res = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=2048,
                timeout=30
            )
            msg = res.choices[0].message
            content = msg.content or getattr(msg, 'reasoning', '') or ""
            if content and content.strip():
                print(f"✅ OpenRouter Success with '{model_name}'! Response: {content.strip()[:60]}...")
                succeeded = True
                break
            else:
                print(f"⚠️ Model '{model_name}' returned empty content, switching to next...")
        except Exception as e:
            print(f"⚠️ Model '{model_name}' failed: {e}")
            if idx < len(OPENROUTER_FREE_MODELS):
                print(f"↪️ Switching to next free model: '{OPENROUTER_FREE_MODELS[idx]}'...")

    if not succeeded:
        print("❌ All OpenRouter free models failed.")

print("\n" + "="*50)
print("                 TEST COMPLETE               ")
print("="*50 + "\n")
