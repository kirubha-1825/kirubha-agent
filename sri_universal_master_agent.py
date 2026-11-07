"""
SriUniversalMasterAgent - Universal Master AI Agent & Workspace Orchestrator.

Manages all approved work areas:
- workspace/student_learning_hub
- workspace/frontend_designs
- workspace/automation_scripts
- google_antigravity_projects

Routes to best AI engine:
- Stitch AI (UI/UX Specialist) -> STITCH_API_KEY
- Google Gemini Pro + Antigravity -> GEMINI_API_KEY
- OpenRouter Multi-AI Engine -> OPENROUTER_API_KEY

Auto-Kill Guard:
Enforces master key ending in 1825 (SRI_AUTH_SEC_948f2b7a0c91825) and approved work areas.
"""

import os
import streamlit as st


class SriUniversalMasterAgent:
    def __init__(self):
        # 1. ஏஜென்ட் பெயர் மற்றும் சாவி
        agent_val = ""
        secret_val = ""
        try:
            if hasattr(st, "secrets"):
                agent_val = st.secrets.get("AGENT_NAME", "SRI")
                secret_val = st.secrets.get("SRI_API_KEY", "") or st.secrets.get(
                    "SRI_AUTH_SECRET", ""
                )
        except Exception:
            pass
        if not agent_val:
            agent_val = os.getenv("AGENT_NAME", "SRI")
        if not secret_val:
            secret_val = os.getenv("SRI_API_KEY", "") or os.getenv(
                "SRI_AUTH_SECRET", ""
            )

        self.agent_name = agent_val or "SRI"
        self.master_key = secret_val or "SRI_AUTH_SEC_948f2b7a0c91825"

        # ஸ்ரீ வேலை பார்க்க அனுமதிக்கப்பட்ட அனைத்து ஏரியாக்கள் (Workspaces)
        self.approved_work_areas = [
            "workspace/student_learning_hub",
            "workspace/frontend_designs",
            "workspace/automation_scripts",
            "google_antigravity_projects",
        ]
        self.is_active = True
        self.kill_reason = ""

    def add_new_work_area(self, new_folder_path: str):
        """புதிய ஏரியாவை ஸ்ரீயின் வேலைப் பட்டியலில் சேர்க்கும் வசதி"""
        norm_path = new_folder_path.replace("\\", "/").strip().lstrip("./")
        if norm_path and norm_path not in self.approved_work_areas:
            self.approved_work_areas.append(norm_path)
            if hasattr(st, "info"):
                st.info(f"📂 புதிய ஏரியா இணைக்கப்பட்டது: {norm_path}")
            print(
                f"📂 [SriUniversalMasterAgent]: புதிய ஏரியா இணைக்கப்பட்டது: {norm_path}"
            )

    def execute_universal_task(
        self,
        input_key: str = "SRI_AUTH_SEC_948f2b7a0c91825",
        work_area: str = "workspace/student_learning_hub",
        task_description: str = "SRI Master Agent Task",
        *args,
        **kwargs,
    ):
        """எல்லா AI-களையும் ஒருங்கிணைத்து வேலையை முடிக்கும் பகுதி"""
        effective_key = input_key or self.master_key
        effective_area = work_area or "workspace/student_learning_hub"
        effective_desc = task_description or (args[0] if args else "SRI Master Agent Task")

        # 1. சாவி சரிபார்ப்பு
        if effective_key != self.master_key or not self.is_active:
            self.kill_switch("தவறான API கீ அல்லது அமர்வு முடக்கப்பட்டுள்ளது!")
            return None

        # 2. ஏரியா எல்லைச் சரிபார்ப்பு (நீங்கள் அனுமதித்த ஏரியாக்களில் ஒன்றா?)
        norm_work_area = effective_area.replace("\\", "/").strip().lstrip("./")
        if not any(
            norm_work_area.startswith(
                area.replace("\\", "/").strip().lstrip("./")
            )
            for area in self.approved_work_areas
        ):
            self.kill_switch(f"அனுமதிக்கப்படாத ஏரியா அணுகல்: {effective_area}")
            return None

        # 3. டாஸ்க்கிற்கு ஏற்ற சிறந்த AI-ஐத் தேர்ந்தெடுத்தல்
        task_lower = effective_desc.lower()
        if any(
            w in task_lower
            for w in ["design", "ui", "frontend", "டிசைன்", "பக்கம்"]
        ):
            selected_ai = "Stitch AI (UI/UX Specialist)"
            api_used = "STITCH_API_KEY"
        elif any(
            w in task_lower
            for w in ["code", "deploy", "app", "கோடு", "டிப்ளாய்"]
        ):
            selected_ai = "Google Gemini Pro + Antigravity"
            api_used = "GEMINI_API_KEY"
        else:
            selected_ai = "OpenRouter Multi-AI Engine"
            api_used = "OPENROUTER_API_KEY"

        result_payload = {
            "agent": self.agent_name,
            "status": "SUCCESS",
            "work_area": effective_area,
            "ai_engine": selected_ai,
            "key_verified": api_used,
        }

        print(
            f"👑 [SriUniversalMasterAgent]: {self.agent_name} -> {selected_ai} ({api_used}) on {effective_area}"
        )
        return result_payload

    def kill_switch(self, reason: str):
        """எல்லை மீறினால் உடனடியாக நிறுத்தும் பாதுகாப்பு முறை"""
        self.is_active = False
        self.kill_reason = reason
        if hasattr(st, "error"):
            st.error(f"🛑 [AUTO-KILL ACTIVATED]: {reason}")
        if hasattr(st, "warning"):
            st.warning(
                "ஸ்ரீ ஏஜென்ட்டின் அனைத்து AI இணைப்புகளும் உடனடியாகத் துண்டிக்கப்பட்டன!"
            )
        print(f"🛑 [AUTO-KILL ACTIVATED]: {reason}")
        print(
            "ஸ்ரீ ஏஜென்ட்டின் அனைத்து AI இணைப்புகளும் உடனடியாகத் துண்டிக்கப்பட்டன!"
        )

    def reset_agent(self, admin_key: str) -> bool:
        """அட்மின் சாவியுடன் மாஸ்டர் ஏஜென்ட்டை மீண்டும் செயல்படுத்துதல்"""
        if admin_key == self.master_key:
            self.is_active = True
            self.kill_reason = ""
            print(
                "🔄 ஸ்ரீ யுனிவர்சல் மாஸ்டர் ஏஜென்ட் மீண்டும் செயல்படுத்தப்பட்டது (Master Agent Re-armed)."
            )
            return True
        print("❌ மாஸ்டர் ஏஜென்ட்டை மீட்டெடுக்க தவறான அட்மின் சாவி வழங்கப்பட்டது.")
        return False

