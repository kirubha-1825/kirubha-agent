import os
import streamlit as st
import google.generativeai as genai
from openai import OpenAI
import requests
from dotenv import load_dotenv

# Optional Mic Recorder import with safe initialization
try:
    from streamlit_mic_recorder import mic_recorder
    MIC_RECORDER_AVAILABLE = True
except ImportError:
    mic_recorder = None
    MIC_RECORDER_AVAILABLE = False

# Load local environment variables from .env if present
load_dotenv()

# ==============================================================================
# 1. PAGE CONFIGURATION & AESTHETIC THEME
# ==============================================================================
st.set_page_config(
    page_title="Kirubakaran's Ultimate AI Agent",
    page_icon="🤖",
    layout="centered",
    initial_sidebar_state="expanded"
)

# Custom Styling for polished, modern look
st.markdown("""
<style>
    .main-title {
        font-size: 2.1rem;
        font-weight: 700;
        background: linear-gradient(90deg, #4A90E2, #9013FE);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.3rem;
    }
    .sub-title {
        color: #7A828E;
        font-size: 0.95rem;
        margin-bottom: 1.2rem;
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-title">🤖 Kirubakaran\'s 24/7 Ultimate Autonomous Agent</div>', unsafe_allow_html=True)
st.write(
    "வணக்கம்! Google Gemini, NVIDIA Build, Groq, OpenRouter, Mistral, Cohere, Hugging Face மற்றும் LiteLLM ஆகிய AI மாடல்களின் வலுவான Fallback அமைப்பு மற்றும் Telegram அறிவிப்புகளுடன் பாதுகாப்பாக இயங்குகிறது."
)

# ==============================================================================
# 2. SECURE SECRETS MANAGEMENT (st.secrets with os.getenv fallback)
# ==============================================================================
def get_secret(key_name: str) -> str:
    """
    Securely fetches credentials first from st.secrets (Streamlit Cloud or .streamlit/secrets.toml),
    then falls back to os.getenv (.env or system environment variables).
    Never throws FileNotFoundError or KeyError if secrets are missing.
    """
    try:
        if hasattr(st, "secrets") and key_name in st.secrets:
            val = st.secrets[key_name]
            if val:
                return str(val).strip()
    except Exception:
        pass
    env_val = os.getenv(key_name)
    return env_val.strip() if env_val else ""

# Fetch all AI Provider API Keys dynamically without hardcoding
gemini_key = get_secret("GEMINI_API_KEY")
nvidia_key = get_secret("NVIDIA_API_KEY")
groq_key = get_secret("GROQ_API_KEY")
openrouter_key = get_secret("OPENROUTER_API_KEY")
mistral_key = get_secret("MISTRAL_API_KEY")
cohere_key = get_secret("COHERE_API_KEY")
huggingface_key = get_secret("HUGGINGFACE_API_KEY")
litellm_key = get_secret("LITELLM_API_KEY")

# Fetch Telegram Credentials dynamically
telegram_token = get_secret("TELEGRAM_BOT_TOKEN")
telegram_chat_id = get_secret("TELEGRAM_CHAT_ID")

# System instruction for AI interactions
system_instruction = """
You are Kirubakaran's personal 24/7 autonomous AI agent.
1. When chatting with the user in the Streamlit UI, reply conversationally, helpfully, and accurately. Support Tamil, English, and Tanglish naturally.
2. Provide clear problem-solving, structured summaries, and actionable steps.
3. Keep notifications and reports concise and well-structured for instant reading.
"""

if gemini_key:
    try:
        genai.configure(api_key=gemini_key)
    except Exception:
        pass

# ==============================================================================
# 3. TELEGRAM NOTIFICATION SYSTEM
# ==============================================================================
def send_telegram_message(message: str) -> dict:
    """Sends a notification message to the configured Telegram bot and chat ID."""
    if not telegram_token or not telegram_chat_id:
        return {"ok": False, "description": "Telegram token or chat ID is missing."}
    
    url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
    max_chunk = 4000
    chunks = [message[i:i + max_chunk] for i in range(0, len(message), max_chunk)]
    last_response = {"ok": True}
    
    for chunk in chunks:
        payload = {
            "chat_id": telegram_chat_id,
            "text": chunk,
            "disable_web_page_preview": True
        }
        try:
            res = requests.post(url, json=payload, timeout=12)
            last_response = res.json()
            if not last_response.get("ok"):
                return last_response
        except Exception as e:
            return {"ok": False, "description": str(e)}
            
    return last_response

# ==============================================================================
# 4. MULTI-MODEL FALLBACK ENGINE WITH LIVE LOGS
# ==============================================================================
def update_logs(logs: list, message: str, log_container=None):
    """Helper to append and refresh logs in real time."""
    logs.append(message)
    if log_container is not None:
        log_container.code("\n".join(logs))

def ask_ai_agent(prompt: str, log_container=None):
    """
    Executes prompt against up to 8 AI providers with sequential fallback redundancy:
    1. Google Gemini Flash
    2. NVIDIA Build (Llama 3.1 70B)
    3. Groq Cloud (Llama 3.3 / Llama 3)
    4. OpenRouter
    5. Mistral AI (Official)
    6. Cohere AI (Command-R+)
    7. Hugging Face Inference API
    8. LiteLLM Gateway
    """
    logs = []

    # 1st: Google Gemini
    if gemini_key:
        update_logs(logs, "⏳ 1வது முயற்சி: Google Gemini சரிபார்க்கப்படுகிறது...", log_container)
        try:
            for m_name in ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.5-flash"]:
                try:
                    m = genai.GenerativeModel(m_name, system_instruction=system_instruction)
                    response = m.generate_content(prompt)
                    if response and response.text:
                        update_logs(logs, f"✅ வெற்றி: Google Gemini ({m_name}) மூலம் பதில் பெறப்பட்டது!", log_container)
                        return response.text, f"Google Gemini ({m_name})", logs
                except Exception as inner_e:
                    update_logs(logs, f"⚠️ {m_name} பிழை: {inner_e}", log_container)
                    continue
        except Exception as e:
            update_logs(logs, f"❌ Gemini பொதுவான பிழை: {e}", log_container)

    # 2nd: NVIDIA Build
    if nvidia_key:
        update_logs(logs, "⏳ 2வது முயற்சி: NVIDIA Build (Llama 3.1 70B) சரிபார்க்கப்படுகிறது...", log_container)
        try:
            client = OpenAI(
                base_url="https://integrate.api.nvidia.com/v1",
                api_key=nvidia_key
            )
            completion = client.chat.completions.create(
                model="meta/llama-3.1-70b-instruct",
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.5,
                max_tokens=1500,
            )
            ans = completion.choices[0].message.content
            if ans:
                update_logs(logs, "✅ வெற்றி: NVIDIA Build மூலம் பதில் பெறப்பட்டது!", log_container)
                return ans, "NVIDIA Build (Llama 3.1)", logs
        except Exception as e:
            update_logs(logs, f"❌ NVIDIA பிழை: {e}", log_container)

    # 3rd: Groq API
    if groq_key:
        update_logs(logs, "⏳ 3வது முயற்சி: Groq API சரிபார்க்கப்படுகிறது...", log_container)
        try:
            client = OpenAI(
                base_url="https://api.groq.com/openai/v1",
                api_key=groq_key
            )
            for g_model in ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "llama3-70b-8192"]:
                try:
                    completion = client.chat.completions.create(
                        model=g_model,
                        messages=[
                            {"role": "system", "content": system_instruction},
                            {"role": "user", "content": prompt}
                        ],
                        temperature=0.5,
                        max_tokens=1500
                    )
                    ans = completion.choices[0].message.content
                    if ans:
                        update_logs(logs, f"✅ வெற்றி: Groq API ({g_model}) மூலம் பதில் பெறப்பட்டது!", log_container)
                        return ans, f"Groq API ({g_model})", logs
                except Exception:
                    continue
        except Exception as e:
            update_logs(logs, f"❌ Groq பிழை: {e}", log_container)

    # 4th: OpenRouter
    if openrouter_key:
        update_logs(logs, "⏳ 4வது முயற்சி: OpenRouter சரிபார்க்கப்படுகிறது...", log_container)
        try:
            client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=openrouter_key
            )
            for o_model in [
                "meta-llama/llama-3.1-8b-instruct:free",
                "mistralai/mistral-7b-instruct:free",
                "openrouter/auto"
            ]:
                try:
                    completion = client.chat.completions.create(
                        model=o_model,
                        messages=[
                            {"role": "system", "content": system_instruction},
                            {"role": "user", "content": prompt}
                        ],
                        temperature=0.5,
                        max_tokens=1500
                    )
                    ans = completion.choices[0].message.content
                    if ans:
                        update_logs(logs, f"✅ வெற்றி: OpenRouter ({o_model}) மூலம் பதில் பெறப்பட்டது!", log_container)
                        return ans, f"OpenRouter ({o_model})", logs
                except Exception:
                    continue
        except Exception as e:
            update_logs(logs, f"❌ OpenRouter பிழை: {e}", log_container)

    # 5th: Mistral AI (Official)
    if mistral_key:
        update_logs(logs, "⏳ 5வது முயற்சி: Mistral AI சரிபார்க்கப்படுகிறது...", log_container)
        try:
            client = OpenAI(
                base_url="https://api.mistral.ai/v1",
                api_key=mistral_key
            )
            for m_model in ["mistral-small-latest", "open-mistral-7b", "mistral-tiny"]:
                try:
                    completion = client.chat.completions.create(
                        model=m_model,
                        messages=[
                            {"role": "system", "content": system_instruction},
                            {"role": "user", "content": prompt}
                        ],
                        temperature=0.5,
                        max_tokens=1500
                    )
                    ans = completion.choices[0].message.content
                    if ans:
                        update_logs(logs, f"✅ வெற்றி: Mistral AI ({m_model}) மூலம் பதில் பெறப்பட்டது!", log_container)
                        return ans, f"Mistral AI ({m_model})", logs
                except Exception:
                    continue
        except Exception as e:
            update_logs(logs, f"❌ Mistral பிழை: {e}", log_container)

    # 6th: Cohere AI
    if cohere_key:
        update_logs(logs, "⏳ 6வது முயற்சி: Cohere AI சரிபார்க்கப்படுகிறது...", log_container)
        try:
            headers = {
                "Authorization": f"Bearer {cohere_key}",
                "Content-Type": "application/json"
            }
            for c_model in ["command-r-plus", "command-r", "command"]:
                try:
                    payload = {"model": c_model, "message": prompt}
                    response = requests.post(
                        "https://api.cohere.ai/v1/chat",
                        headers=headers,
                        json=payload,
                        timeout=20
                    )
                    res_json = response.json()
                    if "text" in res_json and res_json["text"]:
                        update_logs(logs, f"✅ வெற்றி: Cohere AI ({c_model}) மூலம் பதில் பெறப்பட்டது!", log_container)
                        return res_json["text"], f"Cohere AI ({c_model})", logs
                except Exception:
                    continue
        except Exception as e:
            update_logs(logs, f"❌ Cohere பிழை: {e}", log_container)

    # 7th: Hugging Face Inference API
    if huggingface_key:
        update_logs(logs, "⏳ 7வது முயற்சி: Hugging Face சரிபார்க்கப்படுகிறது...", log_container)
        try:
            headers = {"Authorization": f"Bearer {huggingface_key}"}
            payload = {"inputs": prompt, "parameters": {"max_new_tokens": 512, "return_full_text": False}}
            hf_endpoints = [
                "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.2",
                "https://router.huggingface.co/hf-inference/models/mistralai/Mistral-7B-Instruct-v0.2"
            ]
            for endpoint in hf_endpoints:
                try:
                    response = requests.post(endpoint, headers=headers, json=payload, timeout=25)
                    res_json = response.json()
                    if isinstance(res_json, list) and len(res_json) > 0:
                        ans = res_json[0].get("generated_text")
                        if ans:
                            update_logs(logs, "✅ வெற்றி: Hugging Face மூலம் பதில் பெறப்பட்டது!", log_container)
                            return ans, "Hugging Face", logs
                    elif isinstance(res_json, dict) and "generated_text" in res_json:
                        ans = res_json.get("generated_text")
                        if ans:
                            update_logs(logs, "✅ வெற்றி: Hugging Face மூலம் பதில் பெறப்பட்டது!", log_container)
                            return ans, "Hugging Face", logs
                except Exception:
                    continue
        except Exception as e:
            update_logs(logs, f"❌ Hugging Face பிழை: {e}", log_container)

    # 8th: LiteLLM Gateway
    if litellm_key:
        update_logs(logs, "⏳ 8வது முயற்சி: LiteLLM Gateway சரிபார்க்கப்படுகிறது...", log_container)
        try:
            client = OpenAI(
                base_url="https://api.litellm.ai/v1",
                api_key=litellm_key
            )
            completion = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.5,
            )
            ans = completion.choices[0].message.content
            if ans:
                update_logs(logs, "✅ வெற்றி: LiteLLM Gateway மூலம் பதில் பெறப்பட்டது!", log_container)
                return ans, "LiteLLM Gateway", logs
        except Exception as e:
            update_logs(logs, f"❌ LiteLLM பிழை: {e}", log_container)

    # All engines failed
    update_logs(logs, "❌ அனைத்து AI மாடல்களும் தோல்வியடைந்தன அல்லது ஒதுக்கீட்டு வரம்பு முடிந்தது!", log_container)
    return "மன்னிக்கவும்! அனைத்து AI மாடல்களின் அழைப்பும் தோல்வியடைந்துள்ளது அல்லது ஒதுக்கீட்டு வரம்பு (Quota Limit) முடிந்துவிட்டது. தயவுசெய்து உங்கள் API கீ-களை சரிபார்க்கவும்.", "Failure", logs

# ==============================================================================
# 5. SIDEBAR CONTROLS & MONITORING
# ==============================================================================
with st.sidebar:
    st.header("⚙️ கணினி கட்டுப்பாடுகள் (System Status)")
    st.markdown("**செயலில் உள்ள AI மாடல்கள்:**")
    
    models_status = [
        ("Google Gemini", bool(gemini_key)),
        ("NVIDIA Build", bool(nvidia_key)),
        ("Groq API", bool(groq_key)),
        ("OpenRouter", bool(openrouter_key)),
        ("Mistral AI", bool(mistral_key)),
        ("Cohere AI", bool(cohere_key)),
        ("Hugging Face", bool(huggingface_key)),
        ("LiteLLM", bool(litellm_key)),
    ]
    
    cols = st.columns(2)
    for idx, (m_name, is_ready) in enumerate(models_status):
        col = cols[idx % 2]
        if is_ready:
            col.markdown(f"🟢 **{m_name}**")
        else:
            col.markdown(f"⚪ *{m_name}*")
            
    st.markdown("---")
    st.subheader("📬 Telegram Notifications")
    
    tg_configured = bool(telegram_token and telegram_chat_id)
    if tg_configured:
        st.caption("🟢 Telegram Bot: Configured")
    else:
        st.caption("⚪ Telegram Bot: Not Configured")
    
    if st.button("🔔 Test Telegram Notification", use_container_width=True, disabled=not tg_configured):
        with st.spinner("டெலிகிராமிற்கு சோதனை செய்தி அனுப்பப்படுகிறது..."):
            test_resp = send_telegram_message("🚀 வணக்கம் Kirubakaran! உங்கள் 8-AI Autonomous Agent Telegram அறிவிப்பு அமைப்பு வெற்றிகரமாகச் செயல்படுகிறது!")
            if isinstance(test_resp, dict) and test_resp.get("ok"):
                st.success("✅ Telegram சோதனை செய்தி வெற்றிகரமாக அனுப்பப்பட்டது!")
            else:
                err_desc = test_resp.get("description", "Unknown error") if isinstance(test_resp, dict) else str(test_resp)
                st.error(f"❌ Telegram பிழை: {err_desc}")

    st.markdown("---")
    if st.button("🧹 வரலாற்றை அழி (Clear Chat)", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

# ==============================================================================
# 6. SESSION STATE & CHAT HISTORY
# ==============================================================================
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display previous chat messages
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Background live logs container
with st.expander("🛠️ பின்னணி செயல்பாடு & AI Process Display (Live Logs)", expanded=False):
    log_placeholder = st.empty()
    log_placeholder.code("ஏஜென்ட் இயக்கத்திற்காகக் காத்திருக்கிறது... (System Idle)")

# ==============================================================================
# 7. VOICE & TEXT INPUT PROCESSING
# ==============================================================================
user_prompt = None

# Audio input: Try native st.audio_input first, fallback to mic_recorder
audio_file = None
if hasattr(st, "audio_input"):
    audio_file = st.audio_input("🎤 வாய்ஸ் நோட் மூலம் பேச இங்கே பதிவு செய்யவும்:")
elif MIC_RECORDER_AVAILABLE and mic_recorder is not None:
    st.write("🎙️ *அல்லது குரல் மூலம் பேச இங்கே கிளிக் செய்யவும்:*")
    recorded_audio = mic_recorder(start_prompt="🎙️ Start Recording", stop_prompt="⏹️ Stop Recording", key='mic')
    if recorded_audio and isinstance(recorded_audio, dict) and "bytes" in recorded_audio:
        with st.spinner("🎙️ உங்கள் குரல் பதிவு கேட்கப்பட்டு உரை மாற்றப்படுகிறது..."):
            try:
                if gemini_key:
                    genai.configure(api_key=gemini_key)
                    audio_m = genai.GenerativeModel("gemini-1.5-flash")
                    audio_part = {"mime_type": "audio/wav", "data": recorded_audio["bytes"]}
                    audio_res = audio_m.generate_content([
                        audio_part,
                        "Listen to this audio and transcribe the instruction clearly in text."
                    ])
                    if audio_res and audio_res.text:
                        user_prompt = audio_res.text
                        st.info(f"🎙️ **குரலில் நீங்கள் கேட்டது:** {user_prompt}")
            except Exception as e:
                st.error(f"குரல் பதிவை மாற்றுவதில் பிழை: {e}")

if audio_file is not None:
    with st.spinner("🎙️ உங்கள் குரல் பதிவு கேட்கப்பட்டு உரை மாற்றப்படுகிறது..."):
        try:
            if gemini_key:
                genai.configure(api_key=gemini_key)
                audio_model = genai.GenerativeModel("gemini-1.5-flash")
                audio_bytes = audio_file.getvalue()
                audio_part = {"mime_type": audio_file.type or "audio/wav", "data": audio_bytes}
                audio_res = audio_model.generate_content([
                    audio_part,
                    "Transcribe and clearly extract the user instruction or task from this audio recording."
                ])
                if audio_res and audio_res.text:
                    user_prompt = audio_res.text
                    st.info(f"🎙️ **குரலில் நீங்கள் கேட்டது:** {user_prompt}")
            else:
                st.warning("குரல் பதிவை வாசிக்க Google Gemini API Key தேவைப்படுகிறது.")
        except Exception as audio_err:
            st.error(f"குரல் பதிவை மாற்றுவதில் பிழை: {audio_err}")

# Text input section
chat_input = st.chat_input("உங்கள் டாஸ்க்கை இங்கே டைப் செய்யுங்கள்...")
if chat_input:
    user_prompt = chat_input

# ==============================================================================
# 8. EXECUTION & AUTOMATIC NOTIFICATION DISPATCH
# ==============================================================================
if user_prompt:
    st.session_state.messages.append({"role": "user", "content": user_prompt})
    with st.chat_message("user"):
        st.markdown(user_prompt)

    with st.chat_message("assistant"):
        with st.spinner("ஏஜென்ட் AI மாடல்களைச் சோதித்து வேலை செய்கிறது..."):
            ai_response, used_model, process_logs = ask_ai_agent(user_prompt, log_placeholder)
            
            if used_model != "Failure":
                st.success(f"பதில் பெறப்பட்டது ({used_model} மூலம்):")
            else:
                st.error("அனைத்து மாடல்களும் தோல்வியடைந்தன.")
                
            st.markdown(ai_response)
            st.session_state.messages.append({"role": "assistant", "content": ai_response})

            # Telegram Dispatch (if configured)
            if telegram_token and telegram_chat_id:
                with st.spinner("டெலிகிராமிற்கு ரிப்போர்ட் அனுப்பப்படுகிறது..."):
                    tg_message = f"🤖 *Agent Execution Report*\n\n📌 *Selected Model:* {used_model}\n📝 *Task:*\n{user_prompt}\n\n💡 *Response:*\n{ai_response}"
                    tg_result = send_telegram_message(tg_message)
                    
                    if isinstance(tg_result, dict) and tg_result.get("ok"):
                        st.toast("✅ ரிப்போர்ட் Telegram-க்கு வெற்றிகரமாக அனுப்பப்பட்டது!")
                    else:
                        err_msg = tg_result.get("description", "Unknown error") if isinstance(tg_result, dict) else str(tg_result)
                        st.caption(f"ℹ️ Telegram dispatch notice: {err_msg}")
