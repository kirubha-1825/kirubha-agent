"""
SriDesignAndLaunchGuard - Stitch AI & Frontend UI Design / Deployment Guard.
Enforces strict restrictions: only frontend artifacts (index.html, styles.css, app.js)
and allowed design/deploy actions (FRONTEND_UI_DESIGN, STITCH_AI_SYNC, WRITE_CODE, DEPLOY_APP).
Triggers auto-kill if any unauthorized files or actions are attempted.
"""

import os
import streamlit as st


class SriDesignAndLaunchGuard:
    def __init__(self):
        self.agent_name = "SRI"
        secret_val = ""
        try:
            if hasattr(st, "secrets"):
                secret_val = st.secrets.get("SRI_API_KEY", "") or st.secrets.get("SRI_AUTH_SECRET", "")
        except Exception:
            pass
        if not secret_val:
            secret_val = os.getenv("SRI_API_KEY", "") or os.getenv("SRI_AUTH_SECRET", "")

        self.valid_key = secret_val or "SRI_AUTH_SEC_948f2b7a0c91825"

        # அனுமதிக்கப்பட்ட வேலைகள் (Stitch AI ஃபிரண்ட்-எண்ட் டிசைன் உட்பட)
        self.allowed_actions = [
            "FRONTEND_UI_DESIGN",
            "STITCH_AI_SYNC",
            "WRITE_CODE",
            "DEPLOY_APP",
        ]

        # அனுமதிக்கப்பட்ட ஃபைல்கள் மட்டுமே
        self.allowed_files = ["index.html", "styles.css", "app.js", "server.js"]
        self.is_active = True
        self.kill_reason = ""

    def authorize_design_task(
        self, input_key: str, action: str, target_file: str
    ) -> bool:
        if not self.is_active:
            print(
                "🛑 [GUARD-LOCKED]: ஸ்ரீ டிசைன் & லான்ச் கார்ட் ஏற்கனவே முடக்கப்பட்டுள்ளது!"
            )
            return False

        if input_key != self.valid_key:
            self.auto_kill("தவறான API கீ அல்லது அமர்வு முடக்கப்பட்டுள்ளது!")
            return False

        # Stitch AI டிசைன் அல்லது அனுமதிக்கப்பட்ட கோடிங் வேலையா எனச் சரிபார்த்தல்
        if action not in self.allowed_actions:
            self.auto_kill(f"எல்லை மீறல்! அனுமதிக்கப்படாத செயல்: {action}")
            return False

        # ஃபிரண்ட்-எண்ட் கோப்புகளைத் தவிர வேறு சிஸ்டம் கோப்புகளைத் தொட்டால் உடனே ரிமூவ்
        base_file = os.path.basename(target_file.strip().replace("\\", "/"))
        if (
            target_file not in self.allowed_files
            and base_file not in self.allowed_files
        ):
            self.auto_kill(f"அனுமதிக்கப்படாத கோப்பு அணுகல்: {target_file}")
            return False

        print(f"✅ ஸ்ரீ (SRI) அனுமதி பெற்றது: {action} -> {target_file}")
        return True

    def auto_kill(self, reason: str):
        self.is_active = False
        self.kill_reason = reason
        print(f"🛑 [AUTO-KILL ACTIVATED]: {reason}")
        print("ஸ்ரீ ஏஜென்ட்டின் அணுகல் உடனடியாக நீக்கப்பட்டது!")

    def reset_guard(self, admin_key: str) -> bool:
        """அட்மின் சாவியுடன் டிசைன் & லான்ச் கார்டை மீண்டும் செயல்படுத்துதல்"""
        if admin_key == self.valid_key:
            self.is_active = True
            self.kill_reason = ""
            print(
                "🔄 ஸ்ரீ டிசைன் & லான்ச் கார்ட் மீண்டும் செயல்படுத்தப்பட்டது (Design Guard Re-armed)."
            )
            return True
        print("❌ கார்டை மீட்டெடுக்க தவறான அட்மின் சாவி வழங்கப்பட்டது.")
        return False

