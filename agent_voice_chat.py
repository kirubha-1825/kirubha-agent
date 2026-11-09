"""
agent_voice_chat.py - Two-Way Voice Assistant & Live Status Query Engine for SRI.
Enables user to speak or type status queries in Tamil or English:
- "இந்த ப்ராஜெக்ட் எங்க போயிட்டு இருக்கு?"
- "இப்ப என்ன பண்ணுது?"
- "எந்த மாடல் யூஸ் பண்ணுது?"
Generates natural conversational replies and speaks them aloud via browser Web Speech API.
"""

import os
import re
import json
import html
from datetime import datetime
from typing import Dict, Any, Optional, Tuple

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tasks_db.json")


def load_tasks_db() -> Dict[str, Any]:
    """Safely loads tasks_db.json."""
    if not os.path.exists(DB_FILE):
        return {"tasks": {}, "metrics": {}}
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"tasks": {}, "metrics": {}}


def is_tamil_query(text: str) -> bool:
    """Detects if query is written in Tamil script or Tanglish."""
    # Check Unicode range for Tamil block (U+0B80 to U+0BFF)
    if re.search(r"[\u0B80-\u0BFF]", text):
        return True
    # Distinct Tanglish status question keywords (excluding common English words like 'project', 'model', 'task')
    distinct_tanglish_words = [
        "enga", "poitu", "irukku", "enna", "pannuthu", "mudinjatha",
        "mudinjutha", "epdi", "eppadi", "sollinga", "sollu", "solunga", "solra",
        "vanakkam", "yenna", "ethu", "eppo", "aachu", "aayiducha", "pannu",
        "seiyuthu", "seithu", "kekkuthu", "pesu", "nandri"
    ]
    words = re.findall(r"\b[a-zA-Z]+\b", text.lower())
    if any(w in distinct_tanglish_words for w in words):
        return True
    return False


def get_agent_voice_status_reply(user_query: str, db_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Core Question-Answering Engine for Two-Way Voice Assistant:
    Inspects live tasks_db.json and formulates a spoken reply in Tamil or English.
    """
    raw_query = (user_query or "").strip()
    is_tamil = is_tamil_query(raw_query) if raw_query else True

    db = db_data if db_data is not None else load_tasks_db()
    tasks = db.get("tasks", {})

    # 1. Look for currently RUNNING tasks
    running_task = None
    most_recent_task = None
    all_sorted = sorted(
        tasks.values(),
        key=lambda t: t.get("updated_at") or t.get("created_at") or "",
        reverse=True
    )

    for t in all_sorted:
        if t.get("status") == "RUNNING" and not running_task:
            running_task = t
            break

    if all_sorted:
        most_recent_task = all_sorted[0]

    # Target task to report on
    target_task = running_task or most_recent_task

    # If no tasks exist in database at all
    if not target_task:
        if is_tamil:
            spoken = "வணக்கம்! தற்போது எந்தப் புராஜெக்ட்டும் இயங்கவில்லை. நீங்கள் புதிய டாஸ்க்கைத் தொடங்கலாம்."
            display = "👋 வணக்கம்! தற்போது எந்தப் புராஜெக்ட்டும் இயங்கவில்லை. முகப்புப் பக்கத்தில் உங்கள் டாஸ்க்கைக் கொடுத்துத் தொடங்கலாம்."
        else:
            spoken = "Hello! There are no active tasks running at the moment. You can start a new task anytime."
            display = "👋 Hello! There are no active tasks in the queue. Enter your requirement above to dispatch a task."
        return {
            "spoken_text": spoken,
            "display_text": display,
            "lang": "ta-IN" if is_tamil else "en-US",
            "task_id": None,
            "task_status": "IDLE",
            "current_step": 0,
            "progress_percent": 0,
            "current_action": "Idle",
            "active_model": "None"
        }

    # Extract task metadata
    tid = target_task.get("id", "task")
    title = target_task.get("title", "புராஜெக்ட்")
    status = target_task.get("status", "RUNNING")
    step = target_task.get("current_step", 1)
    max_steps = target_task.get("max_steps", 5)
    progress = target_task.get("progress_percent", min(100, step * 20))
    action = target_task.get("current_action", "பணி ஆய்வு செய்யப்படுகிறது")
    model = target_task.get("active_model_or_bridge") or target_task.get("model_used") or "Gemini / OpenRouter Free Loop"
    out_file = target_task.get("output_file") or target_task.get("workspace_file", "")
    folder = target_task.get("folder_name", "workspace")

    # Clean the latest log message
    logs = target_task.get("logs", [])
    last_log = logs[-1] if logs else ""
    clean_log = re.sub(r"^\[\d{2}:\d{2}:\d{2}\]\s*", "", last_log).strip()
    if len(clean_log) > 100:
        clean_log = clean_log[:100] + "..."

    q_lower = raw_query.lower()

    # Case A: Task is currently RUNNING
    if status == "RUNNING":
        # Question type 1: "எந்த மாடல் யூஸ் பண்ணுது?" / "Which model?"
        if any(w in q_lower for w in ["மாடல்", "model", "எந்த", "which model", "engine"]):
            if is_tamil:
                spoken = f"தற்போது '{title}' புராஜெக்ட்டிற்குப் பயன்படுத்தப்படும் மாடல்: {model}. இப்போது {step}-வது கட்டத்தில் {progress}% பணி நிறைவடைந்துள்ளது."
                display = f"🤖 **பயன்படுத்தப்படும் மாடல் / என்ஜின்:** `{model}`\n\n📌 **நிலை:** {step}/{max_steps} கட்டம் ({progress}% நிறைவு)"
            else:
                spoken = f"The active model currently running for '{title}' is {model}. Progress is at step {step} of {max_steps}, about {progress} percent complete."
                display = f"🤖 **Active Model/Engine:** `{model}`\n\n📌 **Progress:** Step {step}/{max_steps} ({progress}%)"

        # Question type 2: "இப்ப என்ன பண்ணுது?" / "What is it doing right now?"
        elif any(w in q_lower for w in ["என்ன பண்ணுது", "என்ன செய்கிறது", "doing", "current action", "what"]):
            if is_tamil:
                spoken = f"இப்போது ஏஜென்ட் {action} என்ற பணியைச் செய்து கொண்டிருக்கிறது. சமீபத்திய பதிவு: {clean_log}."
                display = f"⚡ **தற்போதைய செயல்பாடு:** {action}\n\n📝 **சமீபத்திய லாக்:** `{clean_log}`\n\n📊 **முன்னேற்றம்:** {progress}%"
            else:
                spoken = f"Right now the agent is working on: {action}. The latest log says: {clean_log}."
                display = f"⚡ **Current Action:** {action}\n\n📝 **Latest Log:** `{clean_log}`\n\n📊 **Progress:** {progress}%"

        # Question type 3: "எங்க போயிட்டு இருக்கு?" / "Where is this project at?" / general status
        else:
            if is_tamil:
                spoken = f"வணக்கம்! தற்போது '{title}' புராஜெக்ட் {step}-வது கட்டத்தில் இயங்கிக் கொண்டிருக்கிறது. {progress}% முடிந்துள்ளது. தற்போதைய பணி: {action}."
                display = f"🔄 **புராஜெக்ட் நிலை:** `{title}`\n\n- 🎯 **கட்டம்:** {step} / {max_steps} ({progress}%)\n- ⚡ **செயல்பாடு:** {action}\n- 🤖 **மாடல்:** {model}\n- 📁 **ஃபோல்டர்:** `workspace/{folder}`"
            else:
                spoken = f"Hello! The project '{title}' is currently running at Step {step} of {max_steps}, {progress} percent complete. Current activity: {action}."
                display = f"🔄 **Live Task Status:** `{title}`\n\n- 🎯 **Stage:** Step {step} / {max_steps} ({progress}%)\n- ⚡ **Current Action:** {action}\n- 🤖 **Engine:** {model}\n- 📁 **Workspace Folder:** `workspace/{folder}`"

    # Case B: Task has COMPLETED
    elif status == "COMPLETED":
        if is_tamil:
            spoken = f"உங்கள் புராஜெக்ட் '{title}' வெற்றிகரமாக முடிவடைந்துவிட்டது! 100% பணிகள் நிறைவுற்று, கோப்புகள் பாதுகாப்பாகச் சேமிக்கப்பட்டுள்ளன."
            display = f"✅ **புராஜெக்ட் நிறைவடைந்தது:** `{title}`\n\n- 🏆 **முடிவு:** வெற்றிகரமாக முடிந்தது (100%)\n- 🤖 **மாடல்:** {model}\n- 📦 **சேமிக்கப்பட்ட கோப்பு:** `{out_file or 'workspace/' + folder}`"
        else:
            spoken = f"Your project '{title}' has completed successfully! All steps are 100 percent complete and the output files are ready."
            display = f"✅ **Task Completed:** `{title}`\n\n- 🏆 **Status:** 100% Finished\n- 🤖 **Engine:** {model}\n- 📦 **Saved File:** `{out_file or 'workspace/' + folder}`"

    # Case C: Task FAILED or TIMED OUT
    else:
        err = target_task.get("error", "Unknown error")
        if is_tamil:
            spoken = f"புராஜெக்ட் '{title}' இயங்குவதில் ஒரு சிக்கல் ஏற்பட்டுள்ளது. பிழை விவரம்: {err[:60]}."
            display = f"⚠️ **புராஜெக்ட் நிலை ({status}):** `{title}`\n\n- ❌ **பிழை:** {err}\n- 🤖 **மாடல்:** {model}"
        else:
            spoken = f"The project '{title}' ended with status {status}. The error reported was: {err[:60]}."
            display = f"⚠️ **Task Status ({status}):** `{title}`\n\n- ❌ **Error:** {err}\n- 🤖 **Engine:** {model}"

    return {
        "spoken_text": spoken,
        "display_text": display,
        "lang": "ta-IN" if is_tamil else "en-US",
        "task_id": tid,
        "task_title": title,
        "task_status": status,
        "progress_percent": progress,
        "current_step": step,
        "current_action": action,
        "active_model": model
    }


def generate_speech_synthesis_html(spoken_text: str, lang: str = "ta-IN", autoplay: bool = True) -> str:
    """
    Renders browser Web Speech API component.
    Executes window.speechSynthesis to speak back naturally in Tamil (ta-IN) or English (en-US).
    Includes speech controls and animated visualizer.
    """
    # Safe JSON string encoding for JavaScript
    safe_text_js = json.dumps(spoken_text)
    safe_lang_js = json.dumps(lang)
    safe_text_display = html.escape(spoken_text)

    component_html = f"""
<div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: rgba(15, 23, 42, 0.95); border: 1.5px solid #8B5CF6; border-radius: 12px;
            padding: 14px 18px; margin: 10px 0; color: #F8FAFC; box-shadow: 0 4px 20px rgba(139, 92, 246, 0.15);">
    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px;">
        <div style="display: flex; align-items: center; gap: 8px;">
            <span style="font-size: 1.3rem; animation: pulse-voice 1.5s infinite;">🎙️</span>
            <span style="font-weight: 700; color: #C084FC; font-size: 0.95rem;">
                SRI Voice Assistant Speaks ({'தமிழ் (ta-IN)' if 'ta' in lang else 'English'})
            </span>
        </div>
        <div style="display: flex; gap: 6px;">
            <button id="sriSpeakBtn" onclick="speakAgentResponse()"
                    style="background: #8B5CF6; color: white; border: none; border-radius: 6px; padding: 4px 10px;
                           font-size: 0.8rem; font-weight: 600; cursor: pointer; transition: background 0.2s;">
                🔊 மீண்டும் பேசு (Replay)
            </button>
            <button onclick="stopAgentSpeech()"
                    style="background: #334155; color: #94A3B8; border: none; border-radius: 6px; padding: 4px 10px;
                           font-size: 0.8rem; font-weight: 600; cursor: pointer;">
                ⏹️ நிறுத்து (Stop)
            </button>
        </div>
    </div>
    <div style="font-size: 0.9rem; line-height: 1.45; color: #E2E8F0; background: rgba(30, 41, 59, 0.6);
                border-radius: 8px; padding: 10px 12px; border-left: 3px solid #8B5CF6;">
        "{safe_text_display}"
    </div>
    <div id="voiceStatusMsg" style="font-size: 0.75rem; color: #94A3B8; margin-top: 6px; display: flex; align-items: center; gap: 5px;">
        <span style="display: inline-block; width: 6px; height: 6px; border-radius: 50%; background: #10B981;"></span>
        Web Speech API Active • Ready to talk back
    </div>
</div>

<style>
@keyframes pulse-voice {{
    0% {{ transform: scale(1); opacity: 0.9; }}
    50% {{ transform: scale(1.15); opacity: 1; }}
    100% {{ transform: scale(1); opacity: 0.9; }}
}}
</style>

<script>
const agentSpokenText = {safe_text_js};
const agentSpeechLang = {safe_lang_js};

function speakAgentResponse() {{
    if (!('speechSynthesis' in window)) {{
        const el = document.getElementById('voiceStatusMsg');
        if (el) el.innerHTML = "⚠️ Web Speech API not supported in this browser.";
        return;
    }}
    window.speechSynthesis.cancel();

    const utterance = new SpeechSynthesisUtterance(agentSpokenText);
    utterance.lang = agentSpeechLang;
    utterance.rate = 0.95; // Crisp, clear conversational pace
    utterance.pitch = 1.0;

    // Pick best matching native voice if available
    const voices = window.speechSynthesis.getVoices();
    let selectedVoice = null;
    if (agentSpeechLang.startsWith('ta')) {{
        selectedVoice = voices.find(v => v.lang.startsWith('ta') || v.name.toLowerCase().includes('tamil'));
    }} else {{
        selectedVoice = voices.find(v => v.lang.includes('IN') || v.lang.includes('US') || v.lang.includes('en'));
    }}
    if (selectedVoice) {{
        utterance.voice = selectedVoice;
    }}

    utterance.onstart = function() {{
        const el = document.getElementById('voiceStatusMsg');
        if (el) el.innerHTML = "🔊 ஏஜென்ட் பேசிக்கொண்டிருக்கிறார்... (Speaking...)";
    }};

    utterance.onend = function() {{
        const el = document.getElementById('voiceStatusMsg');
        if (el) el.innerHTML = "✓ பேச்சு நிறைவடைந்தது (Speech Finished).";
    }};

    utterance.onerror = function(e) {{
        const el = document.getElementById('voiceStatusMsg');
        if (el) el.innerHTML = "⚠️ Voice notice: " + (e.error || 'Speech synthesis error');
    }};

    window.speechSynthesis.speak(utterance);
}}

function stopAgentSpeech() {{
    if ('speechSynthesis' in window) {{
        window.speechSynthesis.cancel();
        const el = document.getElementById('voiceStatusMsg');
        if (el) el.innerHTML = "⏹️ பேச்சு நிறுத்தப்பட்டது (Stopped).";
    }}
}}

// Initialize voices and optionally autoplay
if ('speechSynthesis' in window) {{
    window.speechSynthesis.onvoiceschanged = function() {{
        // voices ready
    }};
    {'setTimeout(speakAgentResponse, 400);' if autoplay else ''}
}}
</script>
"""
    return component_html
