"""
SriMasterVoiceRouter - Voice Command Classifier, Intent Router & Security Dispatcher.

Architecture:
[Voice Command]
       │ (e.g.: "மாணவர் ஆப்பிற்கு அழகான ஹோம் பேஜ் டிசைன் செய்து கோட் எழுது")
       ▼
[ஸ்ரீ (SRI) - Master Voice Router] (Key: ...1825)
       │
       ├──► டிசைன் வேலையா?     ──► Stitch AI UI Design Engine (index.html, styles.css, app.js)
       ├──► கோடிங் வேலையா?      ──► Gemini Pro / Antigravity Engine
       ├──► ஆய்வுக்கு / பதிலுக்கு? ──► OpenRouter Multi-Model Reasoning
       │
       ▼
[பாதுகாப்பு சோதனை (Auto-Kill Guard)] ──► SriExecutionGate & SriDesignAndLaunchGuard
       │
       ▼
[உங்களுக்கு பெஸ்ட் ரிசல்ட் & அலர்ட் மெசேஜ்] ──► Telegram + Twilio Tamil Voice Call
"""

import os
import re
from typing import Dict, Any, Tuple
import streamlit as st

from sri_execution_gate import SriExecutionGate
from sri_design_and_launch_guard import SriDesignAndLaunchGuard


class SriMasterVoiceRouter:
    def __init__(self):
        self.router_name = "SRI Master Voice Router"
        secret_val = ""
        try:
            if hasattr(st, "secrets"):
                secret_val = st.secrets.get("SRI_API_KEY", "") or st.secrets.get("SRI_AUTH_SECRET", "")
        except Exception:
            pass
        if not secret_val:
            secret_val = os.getenv("SRI_API_KEY", "") or os.getenv("SRI_AUTH_SECRET", "")

        self.valid_key = secret_val or "SRI_AUTH_SEC_948f2b7a0c91825"
        self.execution_gate = SriExecutionGate()
        self.design_guard = SriDesignAndLaunchGuard()

        # Tamil and English keyword triggers
        self.design_keywords = [
            "டிசைன்", "ஹோம் பேஜ்", "பக்கம்", "அழகான", "இன்டர்பேஸ்", "தோற்றம்",
            "கார்டு", "நேவ்பார்", "லேஅவுட்", "மாணவர் ஆப்", "மாணவர்", "வலைத்தளம்",
            "design", "ui", "ux", "frontend", "stitch", "landing page",
            "home page", "dashboard", "html", "css", "layout", "student", "web",
            "button", "navbar", "card", "view", "theme", "screen"
        ]

        self.coding_keywords = [
            "கோட்", "நிரல்", "ஸ்கிரிப்ட்", "செயல்முறை", "லாஜிக்", "எழுது",
            "பக் பிக்ஸ்", "பைதான்", "அல்காரிதம்", "பணி", "மென்பொருள்",
            "code", "coding", "python", "script", "backend", "algorithm",
            "function", "api", "debug", "logic", "database", "sql", "server"
        ]

        self.research_keywords = [
            "ஆய்வு", "விளக்கம்", "கேள்வி", "பதில்", "ஏன்", "எப்படி",
            "ஒப்பீடு", "ஆராய்க", "பகுப்பாய்வு", "தகவல்",
            "research", "explain", "why", "how", "compare", "review",
            "analyze", "answer", "reason", "summary", "report", "difference"
        ]

    def classify_intent(self, prompt: str) -> Dict[str, Any]:
        """
        Classifies incoming voice/text command into:
        1. DESIGN (Stitch AI)
        2. CODING (Gemini Pro / Antigravity)
        3. RESEARCH (OpenRouter)
        """
        p_lower = prompt.lower().strip()

        design_score = sum(1 for kw in self.design_keywords if kw in p_lower)
        coding_score = sum(1 for kw in self.coding_keywords if kw in p_lower)
        research_score = sum(1 for kw in self.research_keywords if kw in p_lower)

        # High priority for frontend student learning apps
        if "மாணவர்" in p_lower or "student" in p_lower or "டிசைன்" in p_lower or "design" in p_lower or "html" in p_lower:
            design_score += 3

        if design_score >= coding_score and design_score >= research_score and design_score > 0:
            route = "DESIGN"
            tamil_title = "டிசைன் வேலை (Stitch AI UI Engine)"
            engine = "Stitch AI Frontend Designer"
            target_workspace = "workspace/student_learning_hub"
            target_files = ["index.html", "styles.css", "app.js"]
            explanation = "பயனர் அழகான UI / ஹோம் பேஜ் டிசைன் கோரியுள்ளார். Stitch AI ஃபிரண்ட்-எண்ட் என்ஜின் செயல்படுத்தப்படும்."

        elif research_score > coding_score and research_score > design_score:
            route = "RESEARCH"
            tamil_title = "ஆய்வு & பதில் வேலை (OpenRouter Reasoning)"
            engine = "OpenRouter Auto-Reasoning Engine"
            target_workspace = "google_antigravity_space"
            target_files = ["research_report.md"]
            explanation = "பயனர் ஆய்வு, விளக்கம் அல்லது பகுப்பாய்வு கோரியுள்ளார். OpenRouter பல-மாடல் என்ஜின் தேர்ந்தெடுக்கப்பட்டது."

        else:
            route = "CODING"
            tamil_title = "கோடிங் வேலை (Gemini Pro / Antigravity)"
            engine = "Google Gemini 3.8 / Pro & Antigravity Core"
            target_workspace = "workspace/new_project_area"
            target_files = ["main.py", "index.html"]
            explanation = "பயனர் லாஜிக் / கோட் உருவாக்கம் கோரியுள்ளார். Gemini Pro / Antigravity கோடிங் கோர் தேர்ந்தெடுக்கப்பட்டது."

        return {
            "route": route,
            "tamil_title": tamil_title,
            "engine": engine,
            "target_workspace": target_workspace,
            "target_files": target_files,
            "explanation": explanation,
            "scores": {
                "design": design_score,
                "coding": coding_score,
                "research": research_score
            }
        }

    def validate_and_route(
        self,
        prompt: str,
        auth_key: str = "",
        folder_name: str = ""
    ) -> Tuple[bool, Dict[str, Any], str]:
        """
        Validates authentication and executes pre-flight security guards
        (SriExecutionGate & SriDesignAndLaunchGuard).
        Returns: (success: bool, route_info: dict, error_message: str)
        """
        effective_key = auth_key.strip() if auth_key else self.valid_key

        # Key verification (checking for secret ending with 1825)
        if effective_key != self.valid_key and not effective_key.endswith("1825"):
            self.execution_gate.trigger_auto_kill("தவறான அல்லது அங்கீகரிக்கப்படாத API கீ!")
            return False, {}, "Authentication Failure: Invalid SRI API Key."

        # Classify voice command intent
        classification = self.classify_intent(prompt)
        target_ws = folder_name.strip() if folder_name else classification["target_workspace"]

        # Run Security Gate checks
        if not self.execution_gate.is_active:
            return False, classification, f"Auto-Kill Active in SriExecutionGate: {self.execution_gate.kill_reason}"

        if not self.design_guard.is_active:
            return False, classification, f"Auto-Kill Active in SriDesignAndLaunchGuard: {self.design_guard.kill_reason}"

        # If DESIGN route, enforce SriDesignAndLaunchGuard files
        if classification["route"] == "DESIGN":
            for tf in classification["target_files"]:
                if not self.design_guard.authorize_design_task(self.valid_key, "FRONTEND_UI_DESIGN", tf):
                    return False, classification, f"SriDesignAndLaunchGuard Auto-Kill: Disallowed file {tf}"

        return True, classification, ""

