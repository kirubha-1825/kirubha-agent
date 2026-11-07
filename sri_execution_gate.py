"""
SriExecutionGate - Autonomous Agent Boundary & Security Enforcement
Defines allowed workspace zones, permissible agent actions (READ_CODE, WRITE_CODE, DEBUG_CODE),
and auto-kill isolation on security or perimeter violations.
"""

import os
import streamlit as st


class SriExecutionGate:
    def __init__(self):
        self.agent_name = "SRI"
        # நீங்கள் கேட்ட 1825 சாவியை ஒப்பிடுதல்
        secret_val = ""
        try:
            if hasattr(st, "secrets"):
                secret_val = st.secrets.get("SRI_API_KEY", "") or st.secrets.get("SRI_AUTH_SECRET", "")
        except Exception:
            pass
        if not secret_val:
            secret_val = os.getenv("SRI_API_KEY", "") or os.getenv("SRI_AUTH_SECRET", "")

        self.valid_key = secret_val or "SRI_AUTH_SEC_948f2b7a0c91825"

        # அனுமதிக்கப்பட்ட ஏரியாக்களின் பட்டியல் (Allowed Workspaces)
        self.allowed_workspaces = [
            "workspace/student_learning_hub",  # மாணவர் ஆப் ஏரியா
            "workspace/new_project_area",      # நீங்கள் புதிதாகக் கொடுக்கும் ஏரியா
            "google_antigravity_space"         # ஆண்டிகிராவிட்டி ஏரியா
        ]

        # 2. Code Editing அனுமதிக்கப்பட்ட வேலைகள்
        self.allowed_actions = ["READ_CODE", "WRITE_CODE", "DEBUG_CODE"]
        self.is_active = True
        self.kill_reason = ""

    def add_allowed_workspace(self, workspace_path: str):
        """புதிய அனுமதிக்கப்பட்ட ஒர்க்ஸ்பேஸ் ஏரியாவை இணைத்தல்"""
        norm = workspace_path.replace("\\", "/").strip().lstrip("./")
        if norm and norm not in self.allowed_workspaces:
            self.allowed_workspaces.append(norm)

    def is_workspace_allowed(self, file_path: str) -> bool:
        """சரிபார்க்கவும்: பாதை அனுமதிக்கப்பட்ட ஏரியாவில் உள்ளதா என"""
        norm_path = file_path.replace("\\", "/").strip().lstrip("./")
        for ws in self.allowed_workspaces:
            norm_ws = ws.replace("\\", "/").strip().lstrip("./")
            if norm_path == norm_ws or norm_path.startswith(norm_ws + "/") or norm_path.startswith(norm_ws):
                return True
        return False

    def run_agent_task(self, key: str, action: str, file_path: str) -> bool:
        # சாவி சரிபார்ப்பு (கடைசி 1825 சரிபார்க்கப்படும்)
        if not self.is_active:
            print("🛑 [GATE-LOCKED]: ஸ்ரீ ஏஜென்ட் ஏற்கனவே முடக்கப்பட்டுள்ளது (Session Auto-Killed)!")
            return False

        if key != self.valid_key:
            self.trigger_auto_kill("தவறான அல்லது முடக்கப்பட்ட API கீ!")
            return False

        # 1. Workspace Access சரிபார்ப்பு
        if not self.is_workspace_allowed(file_path):
            self.trigger_auto_kill(f"எல்லை மீறல்! அனுமதிக்கப்படாத பகுதி: {file_path}")
            return False

        # 2. Code Editing செயல்முறை சரிபார்ப்பு
        if action not in self.allowed_actions:
            self.trigger_auto_kill(f"அனுமதிக்கப்படாத செயல்முறை: {action}")
            return False

        print(f"✅ ஸ்ரீ வெற்றிகரமாக இயங்குகிறது: {action} on {file_path}")
        return True

    def trigger_auto_kill(self, reason: str):
        """எல்லை மீறினால் உடனடி அழிப்பு"""
        self.is_active = False
        self.kill_reason = reason
        print(f"🛑 [AUTO-KILL]: {reason}")
        print("சிரி (SRI) ஏஜென்ட்டின் அமர்வு முற்றிலுமாக ரத்து செய்யப்பட்டு நீக்கப்பட்டது!")

    def reset_gate(self, admin_key: str) -> bool:
        """அட்மின் சாவியுடன் பாதுகாப்பு வாயிலை மீண்டும் செயல்படுத்துதல்"""
        if admin_key == self.valid_key:
            self.is_active = True
            self.kill_reason = ""
            print("🔄 ஸ்ரீ பாதுகாப்பு வாயில் மீண்டும் செயல்படுத்தப்பட்டது (Gate Re-armed).")
            return True
        print("❌ பாதுகாப்பு வாயிலை மீட்டெடுக்க தவறான அட்மின் சாவி வழங்கப்பட்டது.")
        return False
