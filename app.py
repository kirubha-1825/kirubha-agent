import os
import streamlit as st
import google.generativeai as genai
from twilio.rest import Client
from streamlit_mic_recorder import mic_recorder
from dotenv import load_dotenv

# Load environment variables if available
load_dotenv()

# ==========================================
# 1. CONFIGURATION (உங்கள் விவரங்கள்)
# ==========================================
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AQ.Ab8RN6LoTqAW_mMDEv7ynyKHA4sObMIllOKGFE63RsBu3Y7c3w")
genai.configure(api_key=GEMINI_API_KEY)

# Twilio வாட்ஸ்அப் விவரங்கள்
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "AC6cc4da7507387fe28fc91906a9a891d2")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "d7aa17e51733679aa4db87dbfdc1fffe")
TWILIO_WHATSAPP_FROM = os.getenv("TWILIO_WHATSAPP_FROM", "whatsapp:+1 737 250 8034")  # Twilio சான்ச்பாக்ஸ் நம்பர்
USER_WHATSAPP_TO = os.getenv("USER_WHATSAPP_TO", "whatsapp:+917695992593")  # உங்கள் வாட்ஸ்அப் எண்

# ==========================================
# 2. SYSTEM INSTRUCTIONS (இரட்டை மொழி வசதி)
# ==========================================
system_instruction = """
You are Kirubakaran's personal autonomous AI agent. 
Your behavior rules:
1. When chatting with the user in the Streamlit UI, reply conversationally and helpfully in a mix of Tamil and English (Tanglish) as requested.
2. Review project tasks, analyze files, and organize data.
3. Whenever you prepare a final execution report to be sent to WhatsApp, format that specific report strictly in clear, professional English so it is easy to read.
"""

model = genai.GenerativeModel(
    model_name="gemini-3.1-pro-preview",
    system_instruction=system_instruction
)

# ==========================================
# 3. TWILIO WHATSAPP SENDER FUNCTION
# ==========================================
def send_whatsapp_report(message):
    try:
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        from_num = TWILIO_WHATSAPP_FROM.replace(" ", "")
        to_num = USER_WHATSAPP_TO.replace(" ", "")
        
        # Ensure 'whatsapp:' prefix
        if not from_num.startswith("whatsapp:"):
            from_num = f"whatsapp:{from_num}"
        if not to_num.startswith("whatsapp:"):
            to_num = f"whatsapp:{to_num}"

        whatsapp_message = client.messages.create(
            body=message,
            from_=from_num,
            to=to_num
        )
        return True, whatsapp_message.sid
    except Exception as e:
        err_msg = str(e)
        print(f"Twilio WhatsApp Error: {err_msg}")
        return False, err_msg

# ==========================================
# 4. STREAMLIT CHAT UI & VOICE INPUT
# ==========================================
st.set_page_config(page_title="Kirubakaran's Personal Agent", page_icon="🤖", layout="centered")
st.title("🤖 Kirubakaran's Personal Agent")
st.write("வணக்கம்! இது உங்கள் பர்சனல் AI ஏஜென்ட். என்னிடம் குரல் மூலமாகவோ அல்லது டெக்ஸ்ட் மூலமாகவோ பேசுங்கள், நான் உங்கள் வேலையைச் செய்து வாட்ஸ்அப்பிற்கு ஆங்கிலத்தில் ரிப்போர்ட் அனுப்புவேன்!")

# Sidebar for testing & quick controls
with st.sidebar:
    st.header("⚙️ அமைப்புகள் (Settings)")
    st.markdown(f"**அனுப்புநர் (From):** `{TWILIO_WHATSAPP_FROM}`")
    st.markdown(f"**பெறுநர் (To):** `{USER_WHATSAPP_TO}`")
    
    if st.button("🔔 Test WhatsApp Connection"):
        with st.spinner("சோதனை செய்தி அனுப்பப்படுகிறது..."):
            ok, res = send_whatsapp_report("Hello Kirubakaran! Antigravity Agent Twilio WhatsApp is connected.")
            if ok:
                st.success(f"வாட்ஸ்அப் செய்தி வெற்றிகரமாக அனுப்பப்பட்டது! (SID: {res[:8]}...)")
            else:
                st.error(f"பிழை: {res}")
                if "ContentSid Required" in res or "21608" in res:
                    st.warning("💡 **Twilio குறிப்பு**: நீங்கள் Twilio Sandbox எண்ணிற்கு (`+1 415 523 8886` அல்லது Twilio Console-ல் உள்ள எண்ணிற்கு) உங்கள் வாட்ஸ்அப்பிலிருந்து `join <code-name>` என முதலில் செய்தி அனுப்ப வேண்டும்.")

    st.markdown("---")
    if st.button("🧹 வரலாற்றை அழி (Clear Chat)"):
        st.session_state.messages = []
        st.rerun()

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# மைக் மூலம் பேசுவதற்கான பட்டன் (Voice Chat / Mic Recorder)
st.write("🎙️ *அல்லது குரல் மூலம் பேச இங்கே கிளிக் செய்யவும்:*")
audio = mic_recorder(start_prompt="🎙️ Start Recording", stop_prompt="⏹️ Stop Recording", key='mic')

user_input = None

if audio:
    with st.spinner("உங்கள் குரலை ஏஜென்ட் கேட்டுப் புரிந்து கொள்கிறது..."):
        try:
            audio_bytes = audio['bytes']
            audio_file_part = {"mime_type": "audio/wav", "data": audio_bytes}
            response = model.generate_content([audio_file_part, "Listen to this audio and reply or process the task requested by the user in Tanglish."])
            user_input = response.text
            st.info(f"நீங்கள் சொன்னது: {user_input}")
        except Exception as e:
            st.error(f"குரலைப் புரிந்துகொள்வதில் பிழை: {e}")

# சாதாரண டெக்ஸ்ட் இன்புட்
text_input = st.chat_input("அல்லது உங்கள் டாஸ்க்கை இங்கே டைப் செய்யவும்...")

if text_input:
    user_input = text_input

# ==========================================
# 5. AGENT EXECUTION & WHATSAPP
# ==========================================
if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        with st.spinner("ஏஜென்ட் வேலையைச் செய்து கொண்டிருக்கிறது..."):
            try:
                chat = model.start_chat(history=[
                    {"role": m["role"], "parts": [m["content"]]} 
                    for m in st.session_state.messages[:-1]
                ])
                response = chat.send_message(user_input)
                agent_reply = response.text
                
                # Twilio மூலம் வாட்ஸ்அப்பிற்கு ஆங்கில ரிப்போர்ட்டை அனுப்புவது
                whatsapp_sent, whatsapp_status = send_whatsapp_report(agent_reply)
                
                if whatsapp_sent:
                    agent_reply += "\n\n*(✅ இந்த ரிப்போர்ட் ஆங்கிலத்தில் வெற்றிகரமாக உங்கள் வாட்ஸ்அப்புக்கு அனுப்பப்பட்டுவிட்டது!)*"
                else:
                    agent_reply += f"\n\n*(⚠️ ரிப்போர்ட் தயார், ஆனால் வாட்ஸ்அப் அனுப்புவதில் சிறிய தியக்கம் ஏற்பட்டது: {whatsapp_status})*"
                
                st.markdown(agent_reply)
                st.session_state.messages.append({"role": "assistant", "content": agent_reply})
            
            except Exception as e:
                st.error(f"பிழை ஏற்பட்டுள்ளது: {e}")
