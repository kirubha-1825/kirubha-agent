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

# 1. TEST GOOGLE GEMINI
print("--- [1/4] TESTING GOOGLE GEMINI ---")
gemini_key = st.secrets.get("GEMINI_API_KEY")
if not gemini_key:
    print("❌ GEMINI_API_KEY not found in secrets.toml")
else:
    try:
        genai.configure(api_key=gemini_key)
        model = genai.GenerativeModel("gemini-3.8-flash")
        res = model.generate_content("Hi")
        print("✅ Gemini Call Success! Response:", res.text.strip())
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

# 4. TEST OPENROUTER
print("\n--- [4/4] TESTING OPENROUTER ---")
openrouter_key = st.secrets.get("OPENROUTER_API_KEY")
if not openrouter_key:
    print("❌ OPENROUTER_API_KEY not found in secrets.toml")
else:
    try:
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=openrouter_key
        )
        res = client.chat.completions.create(
            model="openrouter/auto",
            messages=[{"role": "user", "content": "Hi"}],
            max_tokens=10
        )
        content = res.choices[0].message.content or getattr(res.choices[0].message, 'reasoning', '') or ""
        print("✅ OpenRouter Call Success! Response:", content.strip() if content else "[OK - Empty/Reasoning Content]")
    except Exception as e:
        print("❌ OpenRouter Error:", e)

print("\n" + "="*50)
print("                 TEST COMPLETE               ")
print("="*50 + "\n")
