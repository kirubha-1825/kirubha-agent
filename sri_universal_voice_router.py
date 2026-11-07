"""
SriUniversalVoiceRouter - Universal Voice Command Processor & Best-AI Router.

Routes:
1. டிசைன் / UI வேலை -> Stitch AI (Frontend Specialist) -> index.html
2. கோடிங் / லாஜிக் வேலை -> Gemini Pro / Antigravity Workspace -> app.js
3. பொதுவான ஆய்வு / பல மாடல் ஒப்பீடு -> OpenRouter Multi-Model Best Selector -> server.js

Auto-Kill Guard:
Enforces allowed files: ["index.html", "styles.css", "app.js", "server.js"]
Guards key ending in 1825 (SRI_AUTH_SEC_948f2b7a0c91825).
"""

import os
import streamlit as st

try:
    import speech_recognition as sr

    SR_AVAILABLE = True
except ImportError:
    sr = None
    SR_AVAILABLE = False


class SriUniversalVoiceRouter:
    def __init__(self):
        self.agent_name = "SRI"
        secret_val = ""
        try:
            if hasattr(st, "secrets"):
                secret_val = st.secrets.get("SRI_API_KEY", "") or st.secrets.get(
                    "SRI_AUTH_SECRET", ""
                )
        except Exception:
            pass
        if not secret_val:
            secret_val = os.getenv("SRI_API_KEY", "") or os.getenv(
                "SRI_AUTH_SECRET", ""
            )

        self.valid_key = secret_val or "SRI_AUTH_SEC_948f2b7a0c91825"
        self.allowed_files = ["index.html", "styles.css", "app.js", "server.js"]
        self.is_active = True
        self.kill_reason = ""

    def listen_voice_command(self):
        """உங்கள் குரல் கட்டளையைப் புரிந்துகொள்ளும் பகுதி (தமிழ் & ஆங்கிலம்)"""
        if not SR_AVAILABLE:
            if hasattr(st, "warning"):
                st.warning("⚠️ speech_recognition library is not available.")
            return None

        try:
            recognizer = sr.Recognizer()
            with sr.Microphone() as source:
                if hasattr(st, "info"):
                    st.info(
                        "🎙️ ஸ்ரீ (SRI) கவனித்துக் கொண்டிருக்கிறது... உங்கள் கட்டளையைப் பேசுங்கள்:"
                    )
                audio = recognizer.listen(source, timeout=5)
                # தமிழ் மற்றும் ஆங்கிலம் இரண்டையும் புரிந்துகொள்ளும்
                command = recognizer.recognize_google(audio, language="ta-IN")
                return command
        except Exception as e:
            # If Microphone / PyAudio hardware is unavailable or timed out
            print(
                f"🎙️ [Voice Notice]: Microphone capture unavailable or timed out: {e}"
            )
            return None

    def route_to_best_ai(self, input_key: str, command_text: str):
        """கட்டளைக்கு ஏற்ப எந்த AI சிறந்தது என்பதைத் தேர்ந்தெடுத்து இயக்கும் முறை"""
        if input_key != self.valid_key or not self.is_active:
            self.auto_kill("தவறான API கீ! அணுகல் துண்டிக்கப்பட்டது.")
            return None

        cmd_lower = command_text.lower()

        # 1. டிசைன் / UI வேலை என்றால் -> Stitch AI
        if any(
            word in cmd_lower
            for word in ["டிசைன்", "design", "ui", "பக்கம்", "front"]
        ):
            chosen_ai = "Stitch AI (Frontend Specialist)"
            target_file = "index.html"

        # 2. கோடிங் / லாஜிக் வேலை என்றால் -> Gemini / Antigravity
        elif any(
            word in cmd_lower
            for word in ["கோடு", "code", "லாஜிக்", "logic", "பக்", "error"]
        ):
            chosen_ai = "Gemini Pro / Antigravity Workspace"
            target_file = "app.js"

        # 3. பொதுவான ஆய்வு / பல மாடல் ஒப்பீடு என்றால் -> OpenRouter
        else:
            chosen_ai = "OpenRouter Multi-Model Best Selector"
            target_file = "server.js"

        # பாதுகாப்பு எல்லைச் சோதனை
        if target_file not in self.allowed_files:
            self.auto_kill(f"எல்லை மீறல்! {target_file} அணுக அனுமதி இல்லை.")
            return None

        if hasattr(st, "success"):
            st.success(f"🤖 ஸ்ரீ தேர்ந்தெடுத்த சிறந்த AI: *{chosen_ai}*")
            st.write(f"📂 இலக்கு கோப்பு: {target_file} | கட்டளை: {command_text}")
        print(f"🤖 ஸ்ரீ தேர்ந்தெடுத்த சிறந்த AI: {chosen_ai}")
        print(f"📂 இலக்கு கோப்பு: {target_file} | கட்டளை: {command_text}")
        return chosen_ai, target_file

    def auto_kill(self, reason: str):
        self.is_active = False
        self.kill_reason = reason
        if hasattr(st, "error"):
            st.error(f"🛑 [AUTO-KILL ACTIVATED]: {reason}")
        print(f"🛑 [AUTO-KILL ACTIVATED]: {reason}")
        print("ஸ்ரீ ஏஜென்ட்டின் அணுகல் உடனடியாக நீக்கப்பட்டது!")

    def reset_router(self, admin_key: str) -> bool:
        """அட்மின் சாவியுடன் ரவுட்டரை மீண்டும் செயல்படுத்துதல்"""
        if admin_key == self.valid_key:
            self.is_active = True
            self.kill_reason = ""
            print(
                "🔄 ஸ்ரீ யுனிவர்சல் வாய்ஸ் ரவுட்டர் மீண்டும் செயல்படுத்தப்பட்டது (Voice Router Re-armed)."
            )
            return True
        print("❌ ரவுட்டரை மீட்டெடுக்க தவறான அட்மின் சாவி வழங்கப்பட்டது.")
        return False

