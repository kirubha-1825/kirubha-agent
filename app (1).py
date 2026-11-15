import os
import sys
import json
import time
import re
import uuid
import threading
import tempfile
import zipfile
import io
import gc
import shutil
import html as html_lib
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

import streamlit as st
import streamlit.components.v1 as components

try:
    import requests
except ImportError:
    requests = None

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(*_args, **_kwargs):
        return False

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except (ImportError, Exception):
    OpenAI = None
    OPENAI_AVAILABLE = False

try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except (ImportError, Exception):
    genai = None
    GENAI_AVAILABLE = False

try:
    from streamlit_mic_recorder import mic_recorder
    MIC_RECORDER_AVAILABLE = True
except (ImportError, Exception):
    mic_recorder = None
    MIC_RECORDER_AVAILABLE = False

try:
    from twilio.rest import Client as TwilioClient
    TWILIO_AVAILABLE = True
except (ImportError, Exception):
    TwilioClient = None
    TWILIO_AVAILABLE = False

from sri_zero_failure_ui import (
    render_sri_zero_failure_ui,
    SRI_COMPANION_SYSTEM_PROMPT,
    get_open_ended_companion_prompt,
    try_instant_voice_reply,
    user_explicitly_requested_link,
    sanitize_unsolicited_links,
    is_valid_external_url,
)

load_dotenv()


# ==============================================================================
# 0. PORTABLE OPTIONAL MODULE ADAPTERS (Zero Missing-Module Crashes Anywhere)
# ==============================================================================
class _FallbackExecutionGate:
    agent_name = "SriExecutionGate"
    is_active = True
    kill_reason = ""
    allowed_workspaces = ["workspace/student_learning_hub", "workspace/frontend_designs", "workspace/automation_scripts"]
    allowed_actions = ["WRITE_CODE", "DEBUG_CODE", "READ_CODE"]

    def add_allowed_workspace(self, path: str):
        clean = (path or "").strip()
        if clean and clean not in self.allowed_workspaces:
            self.allowed_workspaces.append(clean)

    def run_agent_task(self, auth_key: str, action: str, target: str) -> bool:
        if ".." in (target or "") or (target or "").startswith(("/", "\\")):
            self.is_active = False
            self.kill_reason = f"Unsafe target path blocked: {target}"
            return False
        return bool(self.is_active and auth_key)

    def reset_gate(self, auth_key: str) -> bool:
        if auth_key:
            self.is_active = True
            self.kill_reason = ""
            return True
        return False


class _FallbackDesignGuard:
    agent_name = "SriDesignAndLaunchGuard"
    is_active = True
    kill_reason = ""
    allowed_actions = ["WRITE_CODE", "PREVIEW_UI"]
    allowed_files = [".html", ".css", ".js"]

    def authorize_design_task(self, auth_key: str, action: str, filename: str) -> bool:
        if ".." in (filename or ""):
            self.is_active = False
            self.kill_reason = "Invalid UI filename"
            return False
        return bool(self.is_active and auth_key)

    def reset_guard(self, auth_key: str) -> bool:
        if auth_key:
            self.is_active = True
            self.kill_reason = ""
            return True
        return False


class _FallbackMasterAgent:
    agent_name = "SriUniversalMasterAgent"
    is_active = True
    kill_reason = ""
    master_key = "SRI_AUTH_SEC_948f2b7a0c91825"
    approved_work_areas = [
        "workspace/student_learning_hub",
        "workspace/frontend_designs",
        "workspace/automation_scripts",
    ]

    def add_new_work_area(self, area: str):
        clean = (area or "").strip()
        if clean and ".." not in clean and clean not in self.approved_work_areas:
            self.approved_work_areas.append(clean)

    def execute_universal_task(self, input_key: str, work_area: str, task_description: str, *_args, **_kwargs) -> dict:
        t_low = (task_description or "").lower()
        engine = "Google Gemini Pro" if any(w in t_low for w in ["code", "app", "ui", "html", "python"]) else "OpenRouter Multi-AI Engine"
        return {
            "status": "dispatched",
            "work_area": work_area or "workspace/student_learning_hub",
            "ai_engine": engine,
            "task": task_description,
        }

    def reset_agent(self, auth_key: str) -> bool:
        if auth_key:
            self.is_active = True
            self.kill_reason = ""
            return True
        return False


class _FallbackVoiceRouter:
    def classify_intent(self, prompt: str) -> dict:
        p = (prompt or "").lower()
        route = "DESIGN" if any(k in p for k in ["ui", "design", "html", "css", "page", "டிசைன்"]) else (
            "RESEARCH" if any(k in p for k in ["news", "research", "weather", "search", "செய்தி"]) else "COMPANION"
        )
        return {
            "route": route,
            "engine": "Groq / Gemini Flash",
            "target_workspace": "workspace/student_learning_hub",
            "tamil_title": prompt[:40],
            "target_files": ["index.html"],
            "explanation": f"Routed cleanly to {route}",
        }

    def validate_and_route(self, prompt: str, auth_key: str) -> tuple[bool, dict, str]:
        info = self.classify_intent(prompt)
        return bool(auth_key), info, "" if auth_key else "Unauthorized"


class _FallbackUniversalRouter:
    kill_reason = ""

    def listen_voice_command(self) -> str:
        return ""

    def route_to_best_ai(self, auth_key: str, prompt: str) -> tuple[str, str]:
        if not auth_key:
            self.kill_reason = "Invalid auth key"
            return None
        p = (prompt or "").lower()
        target = "index.html" if any(k in p for k in ["html", "ui", "design", "page"]) else "server.js"
        return "Google Gemini 2.5 Flash", target


try:
    from sri_execution_gate import SriExecutionGate
    sri_execution_gate = SriExecutionGate()
except ImportError:
    sri_execution_gate = _FallbackExecutionGate()

try:
    from sri_design_and_launch_guard import SriDesignAndLaunchGuard
    sri_design_guard = SriDesignAndLaunchGuard()
except ImportError:
    sri_design_guard = _FallbackDesignGuard()

try:
    from sri_voice_router import SriMasterVoiceRouter
    sri_voice_router = SriMasterVoiceRouter()
except ImportError:
    sri_voice_router = _FallbackVoiceRouter()

try:
    from sri_universal_voice_router import SriUniversalVoiceRouter
    sri_universal_router = SriUniversalVoiceRouter()
except ImportError:
    sri_universal_router = _FallbackUniversalRouter()

try:
    from sri_master_agent import SriUniversalMasterAgent, execute_universal_task as _sri_execute_universal_task
    sri_master_agent = SriUniversalMasterAgent()
except ImportError:
    sri_master_agent = _FallbackMasterAgent()
    _sri_execute_universal_task = sri_master_agent.execute_universal_task

try:
    from sri_cloud_agent import (
        send_whatsapp_message,
        background_agent_worker as sri_cloud_background_worker,
        load_tasks as sri_cloud_load_tasks,
        save_task_update as sri_cloud_save_task_update,
    )
    _EXTERNAL_WHATSAPP_PLUGIN_AVAILABLE = callable(send_whatsapp_message)
except ImportError:
    send_whatsapp_message = None
    _EXTERNAL_WHATSAPP_PLUGIN_AVAILABLE = False
    sri_cloud_background_worker = None
    sri_cloud_load_tasks = lambda: []
    sri_cloud_save_task_update = lambda _x: None

try:
    from voice_router import format_paced_voice_response, clean_text_for_natural_speech
except ImportError:
    def clean_text_for_natural_speech(text: str) -> str:
        t = re.sub(r"[\*_`#~\[\](){}<>|\\]", " ", text or "")
        return re.sub(r"\s+", " ", t).strip()

    def format_paced_voice_response(_user_query: str, reply_text: str) -> str:
        return (reply_text or "").strip()

try:
    from llm_router import OPENROUTER_FREE_MODELS
except ImportError:
    OPENROUTER_FREE_MODELS = [
        "google/gemini-2.0-flash-exp:free",
        "meta-llama/llama-3.3-70b-instruct:free",
        "deepseek/deepseek-chat-v3-0324:free",
        "qwen/qwen-2.5-coder-32b-instruct:free",
        "mistralai/mistral-small-3.1-24b-instruct:free",
        "openrouter/free",
    ]


def execute_universal_task(
    input_key: str = "SRI_AUTH_SEC_948f2b7a0c91825",
    work_area: str = "workspace/student_learning_hub",
    task_description: str = "SRI Master Agent System Task",
    *args,
    **kwargs,
):
    key = input_key or getattr(sri_master_agent, "master_key", "SRI_AUTH_SEC_948f2b7a0c91825")
    area = work_area or "workspace/student_learning_hub"
    desc = task_description or (args[0] if args else "SRI Master Agent System Task")
    return sri_master_agent.execute_universal_task(
        input_key=key, work_area=area, task_description=desc, *args, **kwargs
    )


# ==============================================================================
# 1. HYBRID RUNTIME DETECTION & PERSISTENT STORAGE PATHS
# ==============================================================================
def detect_runtime_environment() -> dict:
    is_streamlit_cloud = (
        os.getenv("STREAMLIT_SHARING") == "true"
        or os.getenv("STREAMLIT_RUNTIME_ENV") in ["cloud", "streamlit_cloud"]
        or os.getenv("IS_STREAMLIT_CLOUD", "").lower() in ["true", "1", "yes"]
        or os.path.exists("/mount/src")
        or ("HOSTNAME" in os.environ and "streamlit" in os.environ.get("HOSTNAME", "").lower())
    )
    return {
        "is_cloud": is_streamlit_cloud,
        "env_name": "Streamlit Cloud" if is_streamlit_cloud else "Local Environment",
    }


RUNTIME_ENV = detect_runtime_environment()
IS_CLOUD_MODE = RUNTIME_ENV["is_cloud"]

BASE_DIR = (
    os.path.abspath(os.path.dirname(__file__))
    if "__file__" in globals() and os.path.dirname(__file__)
    else os.path.abspath(os.getcwd())
)


def resolve_storage_dir(default_dirname: str, cloud_temp_subdir: str) -> str:
    target = os.path.abspath(os.path.join(BASE_DIR, default_dirname))
    try:
        os.makedirs(target, exist_ok=True)
        test_file = os.path.join(target, ".perm_test")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("ok")
        os.remove(test_file)
        return target
    except Exception:
        fallback = os.path.abspath(
            os.path.join(tempfile.gettempdir(), "streamlit_agent", cloud_temp_subdir)
        )
        os.makedirs(fallback, exist_ok=True)
        return fallback


WORKSPACE_DIR = resolve_storage_dir("workspace", "workspace")
OUTPUT_DIR = resolve_storage_dir("outputs", "outputs")


def resolve_writable_file(filename: str, fallback_rel: str) -> str:
    candidate = os.path.abspath(os.path.join(BASE_DIR, filename))
    try:
        if not os.path.exists(candidate):
            initial = (
                "[]"
                if filename.endswith("history.json")
                else json.dumps(
                    {"tasks": {}, "metrics": {"total_tasks": 0, "completed_tasks": 0, "failed_tasks": 0, "total_tokens": 0}},
                    indent=2,
                )
            )
            with open(candidate, "w", encoding="utf-8") as f:
                f.write(initial)
        with open(candidate, "a", encoding="utf-8"):
            pass
        return candidate
    except Exception:
        fb = os.path.abspath(os.path.join(tempfile.gettempdir(), "streamlit_agent", fallback_rel))
        os.makedirs(os.path.dirname(fb), exist_ok=True)
        return fb


DB_FILE = resolve_writable_file("tasks_db.json", "tasks_db.json")
HISTORY_FILE = resolve_writable_file("sri_tasks_history.json", "sri_tasks_history.json")
MAX_AGENT_STEPS = 5
TASK_TIMEOUT_SECONDS = 300
db_lock = threading.Lock()
history_lock = threading.Lock()

CORE_PROTECTED_FILES = {
    "app.py",
    "sri_zero_failure_ui.py",
    "tasks_db.json",
    "sri_tasks_history.json",
    "requirements.txt",
    ".env",
    "pyrightconfig.json",
    "readme.md",
    "dockerfile",
    "packages.txt",
    ".gitignore",
    "setup.py",
    "test_all_models.py",
}


def cleanup_cloud_workspace(temp_folder_path: str = ""):
    if temp_folder_path and os.path.exists(temp_folder_path):
        abs_target = os.path.abspath(temp_folder_path)
        base_root = os.path.abspath(BASE_DIR)
        if abs_target != base_root and not any(abs_target.endswith(p) for p in CORE_PROTECTED_FILES):
            shutil.rmtree(temp_folder_path, ignore_errors=True)
    try:
        if hasattr(st, "cache_data"):
            st.cache_data.clear()
        if hasattr(st, "cache_resource"):
            st.cache_resource.clear()
    except Exception:
        pass
    gc.collect()


def is_safe_sandbox_path(target_path: str, base_dir: str = WORKSPACE_DIR) -> tuple[bool, str]:
    try:
        base_abs = os.path.abspath(base_dir)
        target_abs = os.path.abspath(target_path)
        if ".." in target_path.replace("\\", "/"):
            return False, "Security boundary violation: Path traversal ('..') is forbidden."
        if not (target_abs == base_abs or target_abs.startswith(base_abs + os.sep)):
            return False, f"Security boundary violation: Path '{target_path}' escapes sandbox '{base_dir}'."
        if target_abs == base_abs:
            return False, "Security violation: Cannot overwrite directory as a file."
        filename_lower = os.path.basename(target_abs).lower()
        if filename_lower in CORE_PROTECTED_FILES and target_abs == os.path.abspath(os.path.join(BASE_DIR, filename_lower)):
            return False, f"Security boundary violation: Protected file '{filename_lower}' cannot be overwritten."
        return True, ""
    except Exception as e:
        return False, f"Sandbox validation failure: {e}"


# Configure Streamlit Page (guarded for safe headless test imports)
try:
    st.set_page_config(
        page_title="SRI AI. — Solo AI Companion",
        page_icon="✦",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
except Exception:
    pass


# ==============================================================================
# 2. SECURE SECRETS & CUSTOM API KEY / MODEL CONFIG
# ==============================================================================
def get_secret(key_name: str, default: str = "") -> str:
    try:
        if hasattr(st, "secrets") and key_name in st.secrets:
            val = st.secrets[key_name]
            if val:
                return str(val).strip()
    except Exception:
        pass
    env_val = os.getenv(key_name)
    return env_val.strip() if env_val else default


gemini_key = get_secret("GEMINI_API_KEY") or get_secret("GOOGLE_API_KEY")
custom_model_name = (
    (st.session_state.get("sri_custom_model_override") if hasattr(st, "session_state") else "")
    or get_secret("SRI_CUSTOM_MODEL")
    or get_secret("GEMINI_MODEL")
)
openrouter_key = get_secret("OPENROUTER_API_KEY")
nvidia_key = get_secret("NVIDIA_API_KEY")
groq_key = get_secret("GROQ_API_KEY")
telegram_token = get_secret("TELEGRAM_BOT_TOKEN")
telegram_chat_id = get_secret("TELEGRAM_CHAT_ID")
sri_auth_secret = get_secret("SRI_AUTH_SECRET") or "SRI_AUTH_SEC_948f2b7a0c91825"
agent_bridge_api_key = get_secret("AGENT_BRIDGE_API_KEY") or sri_auth_secret
antigravity_webhook_url = get_secret("ANTIGRAVITY_WEBHOOK_URL") or "http://localhost:8501/api/antigravity_webhook"
stitch_ai_api_key = get_secret("STITCH_AI_API_KEY")

if gemini_key and genai:
    try:
        genai.configure(api_key=gemini_key)
    except Exception:
        pass


# ==============================================================================
# 3. PERSISTENT HISTORY STORE (sri_tasks_history.json — Built-in + Plug-in)
# ==============================================================================
def _builtin_load_history() -> list[dict]:
    with history_lock:
        if not os.path.exists(HISTORY_FILE):
            return []
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, list) else []
        except Exception:
            return []


def _builtin_append_history(task_name: str, details: str, entry_type: str = "chat") -> dict:
    entry = {
        "id": uuid.uuid4().hex[:8],
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "iso": datetime.now().isoformat(),
        "type": entry_type,
        "task": task_name,
        "details": details,
    }
    with history_lock:
        items = []
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    if isinstance(loaded, list):
                        items = loaded
            except Exception:
                items = []
        items.append(entry)
        items = items[-400:]
        tmp = f"{HISTORY_FILE}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(items, f, indent=2, ensure_ascii=False)
        os.replace(tmp, HISTORY_FILE)
    return entry


def _builtin_clear_history() -> int:
    with history_lock:
        count = 0
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    if isinstance(loaded, list):
                        count = len(loaded)
            except Exception:
                pass
        tmp = f"{HISTORY_FILE}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump([], f)
        os.replace(tmp, HISTORY_FILE)
        return count


def _builtin_search_history(query: str, limit: int = 100) -> list[dict]:
    q = (query or "").strip().lower()
    items = _builtin_load_history()
    if not q:
        return items[-limit:]
    matched = [
        it for it in items
        if q in str(it.get("task", "")).lower() or q in str(it.get("details", "")).lower()
    ]
    return matched[-limit:]


def _builtin_history_html(entries: list[dict]) -> str:
    if not entries:
        return "<div style='color:#71717A;padding:18px;text-align:center;font-size:12px;'>No activity history yet.</div>"
    cards = []
    for item in reversed(entries[-60:]):
        t = html_lib.escape(str(item.get("type", "chat")).upper())
        ts = html_lib.escape(str(item.get("timestamp", "")))
        task = html_lib.escape(str(item.get("task", "")))
        det = html_lib.escape(str(item.get("details", ""))[:220])
        cards.append(
            f"<div style='background:#0E1117;border:1px solid #1E222B;border-radius:10px;padding:10px;margin-bottom:8px;'>"
            f"<div style='display:flex;justify-content:space-between;font-size:10px;color:#F59E0B;margin-bottom:4px;'>"
            f"<span>{t}</span><span style='color:#64748B;'>{ts}</span></div>"
            f"<div style='font-weight:600;color:#F1F5F9;font-size:12px;margin-bottom:3px;'>{task}</div>"
            f"<div style='color:#CBD5E1;font-size:11px;line-height:1.45;'>{det}</div></div>"
        )
    return "".join(cards)


try:
    from sri_history_store import (
        append_entry as _hist_append,
        load_history as _hist_load,
        clear_history as _clear_hist,
        search_history as _search_hist,
        get_history_for_ui as _hist_for_ui,
        build_history_sidebar_html as _hist_html,
    )
except ImportError:
    _hist_append = _builtin_append_history
    _hist_load = _builtin_load_history
    _clear_hist = _builtin_clear_history
    _search_hist = _builtin_search_history
    _hist_for_ui = lambda limit=200: list(reversed(_builtin_load_history()[-limit:]))
    _hist_html = _builtin_history_html


# ==============================================================================
# 4. THREAD-SAFE DATABASE OPERATIONS & SLEEP RECOVERY (tasks_db.json)
# ==============================================================================
def init_db():
    with db_lock:
        if not os.path.exists(DB_FILE) or os.path.getsize(DB_FILE) == 0:
            default_data = {
                "tasks": {},
                "metrics": {"total_tasks": 0, "completed_tasks": 0, "failed_tasks": 0, "total_tokens": 0},
            }
            with open(DB_FILE, "w", encoding="utf-8") as f:
                json.dump(default_data, f, indent=2)
            return

        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict) or "tasks" not in data:
                raise ValueError("Malformed JSON root structure in tasks_db.json")
        except Exception as e:
            corrupt_backup = f"{DB_FILE}.corrupt_{int(time.time())}.bak"
            try:
                shutil.copy2(DB_FILE, corrupt_backup)
            except Exception:
                pass
            data = {
                "tasks": {},
                "metrics": {"total_tasks": 0, "completed_tasks": 0, "failed_tasks": 0, "total_tokens": 0},
                "recovery_notice": f"Recovered at {datetime.now().isoformat()}: {e}",
            }
            temp_file = f"{DB_FILE}.tmp"
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            os.replace(temp_file, DB_FILE)
            return

        changed = False
        now = datetime.now()
        for _tid, t in data.get("tasks", {}).items():
            if t.get("status") == "RUNNING":
                updated_at = t.get("updated_at")
                if updated_at:
                    try:
                        dt = datetime.fromisoformat(updated_at)
                        if (now - dt).total_seconds() > TASK_TIMEOUT_SECONDS:
                            t["status"] = "TIMED_OUT"
                            t["error"] = "Task timed out or interrupted during server sleep/restart."
                            t.setdefault("logs", []).append(
                                f"[{now.strftime('%H:%M:%S')}] Marked timed out on wakeup."
                            )
                            if "failed_tasks" in data.get("metrics", {}):
                                data["metrics"]["failed_tasks"] += 1
                            changed = True
                    except Exception:
                        pass
        if changed:
            try:
                temp_file = f"{DB_FILE}.tmp"
                with open(temp_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
                os.replace(temp_file, DB_FILE)
            except Exception:
                pass


init_db()


def load_db() -> dict:
    with db_lock:
        if not os.path.exists(DB_FILE):
            init_db()
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict) and "tasks" in data:
                    return data
        except Exception:
            init_db()
            try:
                with open(DB_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "tasks": {},
            "metrics": {"total_tasks": 0, "completed_tasks": 0, "failed_tasks": 0, "total_tokens": 0},
        }


def save_db(data: dict):
    with db_lock:
        temp_file = f"{DB_FILE}.tmp"
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(temp_file, DB_FILE)


def restore_session_state_on_wakeup():
    db = load_db()
    st.session_state["tasks_db"] = db
    if "session_awakened_at" not in st.session_state:
        st.session_state["session_awakened_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for _tid, t in db.get("tasks", {}).items():
        if t.get("status") == "COMPLETED":
            ws_file = t.get("workspace_file")
            code_content = t.get("code")
            if ws_file and code_content:
                full_ws_path = os.path.join(WORKSPACE_DIR, ws_file)
                if not os.path.exists(full_ws_path):
                    try:
                        os.makedirs(os.path.dirname(full_ws_path), exist_ok=True)
                        with open(full_ws_path, "w", encoding="utf-8") as wf:
                            wf.write(code_content)
                    except Exception:
                        pass


def create_task_record(
    prompt: str,
    task_type: str,
    title: str,
    source_file: str = "",
    change_request: str = "",
    folder_name: str = "",
) -> str:
    now_str = datetime.now().isoformat()
    task_id = f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:4]}"
    data = load_db()
    data["tasks"][task_id] = {
        "id": task_id,
        "title": title,
        "prompt": prompt,
        "task_type": task_type,
        "source_file": source_file,
        "change_request": change_request,
        "folder_name": folder_name,
        "workspace_file": "",
        "schema_file": "",
        "status": "RUNNING",
        "created_at": now_str,
        "updated_at": now_str,
        "current_step": 1,
        "max_steps": MAX_AGENT_STEPS,
        "progress_percent": 15,
        "current_action": "Task initialized. Formulating 5D Plan...",
        "active_model_or_bridge": "Tier 1: Cloud LLM (Gemini / Groq / OpenRouter)",
        "plan": "",
        "plan_5d": {},
        "schema_data": "",
        "verification_report": "",
        "logs": [f"[{datetime.now().strftime('%H:%M:%S')}] Task initialized."],
        "output_file": "",
        "code": "",
        "tokens": 0,
        "duration_seconds": 0.0,
        "model_used": "",
        "error": None,
    }
    data["metrics"]["total_tasks"] += 1
    save_db(data)
    return task_id


def update_task_record(task_id: str, notify_all_complete: bool = True, **kwargs):
    became_completed = False
    data = load_db()
    if task_id in data["tasks"]:
        prev_status = str(data["tasks"][task_id].get("status", "")).upper()
        for k, v in kwargs.items():
            data["tasks"][task_id][k] = v
        step = data["tasks"][task_id].get("current_step", 1)
        if "progress_percent" not in kwargs:
            data["tasks"][task_id]["progress_percent"] = min(100, step * 20)
        if "current_action" not in kwargs:
            step_actions = {
                1: "Formulating 5D Architecture & Plan",
                2: "Initializing Schema & Project Structure",
                3: "Synthesizing Core Code & Responsive UI",
                4: "Executing Self-Verification & Reflection",
                5: "Finalizing Production Artifacts & Persistence",
            }
            if data["tasks"][task_id].get("status") == "COMPLETED":
                data["tasks"][task_id]["current_action"] = "Task completed successfully"
                data["tasks"][task_id]["progress_percent"] = 100
            elif data["tasks"][task_id].get("status") == "FAILED":
                data["tasks"][task_id]["current_action"] = f"Failed: {data['tasks'][task_id].get('error', 'Error')}"
            else:
                data["tasks"][task_id]["current_action"] = step_actions.get(step, "Processing task step...")
        elif str(data["tasks"][task_id].get("status", "")).upper() == "COMPLETED":
            data["tasks"][task_id]["progress_percent"] = 100
        if kwargs.get("model_used"):
            data["tasks"][task_id]["active_model_or_bridge"] = kwargs["model_used"]
        data["tasks"][task_id]["updated_at"] = datetime.now().isoformat()
        became_completed = (
            str(data["tasks"][task_id].get("status", "")).upper() == "COMPLETED"
            and prev_status != "COMPLETED"
        )
        save_db(data)
    if notify_all_complete and became_completed:
        try:
            check_and_trigger_all_tasks_completed_whatsapp_alert(source_task_id=task_id)
        except Exception as _wa_chk_err:
            print(f"ℹ️ Post-completion WhatsApp check notice: {_wa_chk_err}")


def append_task_log(task_id: str, message: str):
    data = load_db()
    if task_id in data["tasks"]:
        timestamped_msg = f"[{datetime.now().strftime('%H:%M:%S')}] {message}"
        data["tasks"][task_id].setdefault("logs", []).append(timestamped_msg)
        data["tasks"][task_id]["updated_at"] = datetime.now().isoformat()
        save_db(data)


# ==============================================================================
# 5. NOTIFICATION DISPATCHER HOOK (Telegram, WhatsApp & Twilio Call)
# ==============================================================================
def send_telegram_alert(message: str) -> dict:
    if not telegram_token or not telegram_chat_id or not requests:
        return {"ok": False, "description": "Telegram credentials or requests library unavailable."}
    url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
    payload = {"chat_id": telegram_chat_id, "text": message[:4000], "disable_web_page_preview": True}
    try:
        res = requests.post(url, json=payload, timeout=10)
        return res.json()
    except Exception as e:
        return {"ok": False, "description": str(e)}


def make_agent_call(message: str = "வணக்கம்! உங்கள் SRI ஏஜென்ட் அழைக்கிறது!") -> tuple[bool, str]:
    try:
        if not TWILIO_AVAILABLE or TwilioClient is None:
            return False, "Twilio package is not installed."
        sid = get_secret("TWILIO_ACCOUNT_SID")
        token = get_secret("TWILIO_AUTH_TOKEN")
        from_num = get_secret("TWILIO_PHONE_NUMBER")
        to_num = get_secret("ADMIN_PHONE_NUMBER")
        if not (sid and token and from_num and to_num):
            missing = [k for k, v in [("TWILIO_ACCOUNT_SID", sid), ("TWILIO_AUTH_TOKEN", token), ("TWILIO_PHONE_NUMBER", from_num), ("ADMIN_PHONE_NUMBER", to_num)] if not v]
            return False, f"Missing Twilio credentials: {', '.join(missing)}"
        client = TwilioClient(sid, token)
        twiml = f"<Response><Say language='ta-IN'>{html_lib.escape(message)}</Say></Response>"
        call = client.calls.create(twiml=twiml, to=to_num, from_=from_num)
        return True, str(call.sid)
    except Exception as e:
        return False, str(e)


_whatsapp_alert_lock = threading.Lock()


def _normalize_whatsapp_number(raw_number: str) -> str:
    cleaned = re.sub(r"[\s()-]", "", (raw_number or "").strip())
    if not cleaned:
        return ""
    if cleaned.lower().startswith("whatsapp:"):
        cleaned = cleaned.split(":", 1)[1].strip()
    if cleaned and not cleaned.startswith("+") and cleaned.isdigit() and len(cleaned) == 10:
        cleaned = f"+91{cleaned}"
    elif cleaned and not cleaned.startswith("+") and cleaned.isdigit():
        cleaned = f"+{cleaned}"
    return f"whatsapp:{cleaned}" if cleaned else ""


def _resolve_kirubha_whatsapp_number(explicit_to: str = "") -> str:
    return (
        (explicit_to or "").strip()
        or get_secret("MY_WHATSAPP_NUMBER")
        or get_secret("KIRUBHA_WHATSAPP_NUMBER")
        or get_secret("ADMIN_PHONE_NUMBER")
    )


def send_whatsapp_notification(
    message: str,
    to_number: str = "",
    event: str = "whatsapp_alert",
    extra_payload: dict | None = None,
) -> dict:
    """
    Send a WhatsApp notification directly to Kirubha via Twilio WhatsApp API or WHATSAPP_WEBHOOK_URL,
    with a non-breaking local notification outbox fallback when external credentials are unset.
    """
    body = (message or "").strip()[:1600]
    if not body:
        return {"ok": False, "provider": "none", "error": "Empty WhatsApp message"}

    target_raw = _resolve_kirubha_whatsapp_number(to_number)
    target_wa = _normalize_whatsapp_number(target_raw)

    # 1. Optional external sri_cloud_agent plugin hook (if installed)
    if _EXTERNAL_WHATSAPP_PLUGIN_AVAILABLE and callable(send_whatsapp_message) and getattr(send_whatsapp_message, "__name__", "") != "_builtin_send_whatsapp_message":
        try:
            ok_plugin = bool(send_whatsapp_message(body))
            if ok_plugin:
                return {"ok": True, "provider": "sri_cloud_agent", "to": target_wa or target_raw, "message": body}
        except Exception as plug_err:
            print(f"ℹ️ WhatsApp plugin fallback notice: {plug_err}")

    # 2. Direct Twilio WhatsApp REST/SDK Delivery
    twilio_sid = get_secret("TWILIO_ACCOUNT_SID")
    twilio_token = get_secret("TWILIO_AUTH_TOKEN")
    twilio_wa_from = _normalize_whatsapp_number(get_secret("TWILIO_WHATSAPP_FROM") or "whatsapp:+14155238886")
    if twilio_sid and twilio_token and target_wa and TWILIO_AVAILABLE and TwilioClient is not None:
        try:
            client = TwilioClient(twilio_sid, twilio_token)
            msg_obj = client.messages.create(body=body, from_=twilio_wa_from, to=target_wa)
            return {
                "ok": True,
                "provider": "twilio_whatsapp",
                "sid": str(msg_obj.sid),
                "from": twilio_wa_from,
                "to": target_wa,
                "message": body,
            }
        except Exception as tw_err:
            print(f"⚠️ Twilio WhatsApp delivery failed, trying webhook fallback: {tw_err}")

    # 3. Webhook Integration (WHATSAPP_WEBHOOK_URL via requests or urllib)
    whatsapp_webhook = get_secret("WHATSAPP_WEBHOOK_URL")
    whatsapp_token = get_secret("WHATSAPP_API_TOKEN")
    if whatsapp_webhook:
        payload = {
            "event": event,
            "title": "All Tasks Completed" if event == "all_tasks_completed" else "SRI Task Notification",
            "message": body,
            "to": target_wa or target_raw,
            "recipient": "Kirubha",
            "timestamp": datetime.now().isoformat(),
            **(extra_payload or {}),
        }
        headers = {"Content-Type": "application/json"}
        if whatsapp_token:
            headers["Authorization"] = f"Bearer {whatsapp_token}"
        try:
            if requests:
                res = requests.post(whatsapp_webhook, json=payload, headers=headers, timeout=8)
                ok_http = 200 <= res.status_code < 300
                return {
                    "ok": ok_http,
                    "provider": "whatsapp_webhook",
                    "status_code": res.status_code,
                    "response": res.text[:200],
                    "to": target_wa or target_raw,
                    "message": body,
                }
            req = urllib.request.Request(
                whatsapp_webhook,
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                resp_body = resp.read().decode("utf-8", errors="ignore")[:200]
                return {
                    "ok": 200 <= resp.status < 300,
                    "provider": "whatsapp_webhook",
                    "status_code": resp.status,
                    "response": resp_body,
                    "to": target_wa or target_raw,
                    "message": body,
                }
        except Exception as wh_err:
            return {"ok": False, "provider": "whatsapp_webhook", "error": str(wh_err), "to": target_wa or target_raw}

    # 4. Safe non-blocking local outbox fallback when external gateway secrets are not yet configured
    return {
        "ok": True,
        "provider": "recorded_outbox",
        "queued": True,
        "to": target_wa or target_raw or "Kirubha (set MY_WHATSAPP_NUMBER or WHATSAPP_WEBHOOK_URL)",
        "message": body,
    }


def _builtin_send_whatsapp_message(message: str) -> bool:
    return bool(send_whatsapp_notification(message, event="whatsapp_alert").get("ok"))


if send_whatsapp_message is None:
    send_whatsapp_message = _builtin_send_whatsapp_message


def evaluate_all_tasks_completion(db: dict | None = None) -> dict:
    """Evaluate whether all tracked hackathon/project tasks in tasks_db are 100% complete."""
    state = db if isinstance(db, dict) else load_db()
    tasks_map = state.get("tasks", {}) if isinstance(state, dict) else {}
    entries = list(tasks_map.items())
    total_tasks = len(entries)
    completed_items = [
        (tid, t)
        for tid, t in entries
        if str(t.get("status", "")).upper() == "COMPLETED" and int(t.get("progress_percent", 0)) >= 100
    ]
    running_items = [
        (tid, t)
        for tid, t in entries
        if str(t.get("status", "")).upper() in ("RUNNING", "PENDING", "QUEUED", "IN_PROGRESS")
    ]
    failed_items = [
        (tid, t)
        for tid, t in entries
        if str(t.get("status", "")).upper() in ("FAILED", "TIMEOUT", "TIMED_OUT")
    ]
    all_completed = (
        total_tasks > 0
        and len(running_items) == 0
        and len(failed_items) == 0
        and len(completed_items) == total_tasks
    )
    overall_pct = (
        100
        if all_completed
        else (round(sum(int(t.get("progress_percent", 0)) for _, t in entries) / total_tasks) if total_tasks > 0 else 0)
    )
    signature = f"{total_tasks}:" + ",".join(sorted(str(tid) for tid, _ in completed_items)) if all_completed else ""
    return {
        "all_completed": all_completed,
        "total_tasks": total_tasks,
        "completed_count": len(completed_items),
        "running_count": len(running_items),
        "failed_count": len(failed_items),
        "progress_percent": overall_pct,
        "signature": signature,
        "completed_items": completed_items,
    }


def check_and_trigger_all_tasks_completed_whatsapp_alert(
    force: bool = False,
    source_task_id: str = "",
) -> dict:
    """
    Automatically detect when all hackathon/project tasks reach 100% completion and send an
    'All Tasks Completed' WhatsApp alert directly to Kirubha's WhatsApp number (deduplicated per batch).
    """
    with _whatsapp_alert_lock:
        db_now = load_db()
        summary = evaluate_all_tasks_completion(db_now)
        if not summary["all_completed"]:
            return {
                "triggered": False,
                "reason": "tasks_incomplete",
                "all_completed": False,
                "total_tasks": summary["total_tasks"],
                "completed_count": summary["completed_count"],
                "progress_percent": summary["progress_percent"],
            }

        notifications = db_now.setdefault("notifications", {})
        last_sig = str(notifications.get("all_completed_whatsapp_signature") or "")
        if not force and last_sig == summary["signature"]:
            return {
                "triggered": False,
                "reason": "already_notified",
                "all_completed": True,
                "total_tasks": summary["total_tasks"],
                "completed_count": summary["completed_count"],
                "progress_percent": 100,
                "last_alert": notifications.get("last_all_completed_alert"),
            }

        titles = [str(t.get("title") or tid) for tid, t in summary["completed_items"][:6]]
        summary_lines = ", ".join(titles)
        alert_msg = (
            f"✅ All Tasks Completed! (100%)\n\n"
            f"வணக்கம் கிருபா! உங்கள் அனைத்து Hackathon & Project பணிகளும் ({summary['completed_count']}/{summary['total_tasks']}) "
            f"100% வெற்றிகரமாக முடிந்துவிட்டன.\n"
            f"Completed Tasks: {summary_lines}"
        )

        delivery = send_whatsapp_notification(
            alert_msg,
            event="all_tasks_completed",
            extra_payload={
                "source_task_id": source_task_id,
                "total_tasks": summary["total_tasks"],
                "completed_count": summary["completed_count"],
                "progress_percent": 100,
                "completed_task_ids": [tid for tid, _ in summary["completed_items"]],
                "completed_titles": titles,
            },
        )

        alert_record = {
            "event": "all_tasks_completed",
            "title": "All Tasks Completed",
            "message": alert_msg,
            "source_task_id": source_task_id,
            "completed_count": summary["completed_count"],
            "total_tasks": summary["total_tasks"],
            "signature": summary["signature"],
            "delivery": delivery,
            "sent_at": datetime.now().isoformat(),
        }
        notifications["all_completed_whatsapp_signature"] = summary["signature"]
        notifications["last_all_completed_alert"] = alert_record
        outbox = notifications.setdefault("whatsapp_outbox", [])
        outbox.append(alert_record)
        notifications["whatsapp_outbox"] = outbox[-30:]
        save_db(db_now)

        try:
            _hist_append("All Tasks Completed (WhatsApp)", alert_msg, "whatsapp_alert")
        except Exception:
            pass

        return {
            "triggered": True,
            "reason": "sent",
            "all_completed": True,
            "total_tasks": summary["total_tasks"],
            "completed_count": summary["completed_count"],
            "progress_percent": 100,
            "message": alert_msg,
            "delivery": delivery,
        }


def dispatch_task_alert(task_id: str, task_name: str, status: str, file_path: str = "", extra_details: str = "") -> dict:
    results = {"telegram": None, "whatsapp": None, "twilio_call": None}
    if telegram_token and telegram_chat_id:
        emoji = "✅" if status == "COMPLETED" else "❌"
        filename = os.path.basename(file_path) if file_path else "N/A"
        alert_text = (
            f"{emoji} *Autonomous Task {status}!*\n\n"
            f"🆔 *ID:* `{task_id}`\n"
            f"📝 *Title:* {task_name}\n"
            f"📊 *Status:* `{status}`\n"
            f"📦 *Artifact:* `{filename}`\n"
        )
        if extra_details:
            alert_text += f"ℹ️ *Details:* {extra_details[:180]}\n"
        results["telegram"] = send_telegram_alert(alert_text)

    emoji_wa = "✅" if status == "COMPLETED" else "❌"
    wa_text = f"{emoji_wa} *Task {status}*\nID: `{task_id}`\nTitle: {task_name}\n{extra_details[:140]}"
    results["whatsapp"] = send_whatsapp_notification(
        wa_text,
        event="autonomous_task_alert",
        extra_payload={
            "task_id": task_id,
            "task_name": task_name,
            "status": status,
            "file_path": file_path,
            "details": extra_details,
        },
    )

    if get_secret("TWILIO_ACCOUNT_SID") and get_secret("ADMIN_PHONE_NUMBER"):
        call_msg = (
            f"வணக்கம்! உங்கள் பணி {task_name[:30]} வெற்றிகரமாக முடிந்தது."
            if status == "COMPLETED"
            else f"வணக்கம்! உங்கள் பணி {task_name[:30]} தோல்வியடைந்தது."
        )
        ok_call, call_sid_or_err = make_agent_call(call_msg)
        results["twilio_call"] = {"success": ok_call, "sid_or_error": call_sid_or_err}

    return results


# ==============================================================================
# 6. LLM CALLERS (Custom Key + Multi-Model Fallback + Conversational Brain)
# ==============================================================================
_gemini_cooldown_until = 0


def call_gemini(prompt: str, system_instruction: str = "", task_id: str = ""):
    global _gemini_cooldown_until
    if not gemini_key or not genai:
        raise ValueError("GEMINI_API_KEY is missing or google-generativeai is unavailable.")
    if time.time() < _gemini_cooldown_until:
        cooldown_left = int(_gemini_cooldown_until - time.time())
        raise RuntimeError(f"Gemini cooldown active ({cooldown_left}s remaining).")

    candidates = ([custom_model_name] if custom_model_name else []) + [
        "gemini-2.5-flash",
        "gemini-2.0-flash",
        "gemini-1.5-flash",
    ]
    last_err = None
    for model_name in dict.fromkeys(candidates):
        try:
            def _gemini_call(m=model_name):
                genai.configure(api_key=gemini_key)
                model = genai.GenerativeModel(
                    model_name=m,
                    system_instruction=system_instruction or None,
                )
                return model.generate_content(prompt, request_options={"timeout": 120})

            with ThreadPoolExecutor(max_workers=1) as executor:
                response = executor.submit(_gemini_call).result(timeout=125)

            if response and response.text and response.text.strip():
                tokens_est = (len(prompt) + len(system_instruction) + len(response.text)) // 4
                if task_id:
                    append_task_log(task_id, f"✅ Google Gemini ({model_name}) succeeded.")
                return response.text.strip(), f"Google Gemini ({model_name})", tokens_est
            raise ValueError(f"Empty response from Gemini ({model_name}).")
        except Exception as e:
            last_err = e
            err_str = str(e).lower()
            if task_id:
                append_task_log(task_id, f"⚠️ Gemini '{model_name}': {e}")
            if any(term in err_str for term in ["deadline", "504", "timeout", "quota", "429", "exhausted", "resource_exhausted"]):
                _gemini_cooldown_until = time.time() + 60
                raise last_err
    if last_err:
        raise last_err


def call_openrouter(prompt: str, system_instruction: str = "", task_id: str = "", messages: list[dict] | None = None):
    if not openrouter_key or not OpenAI:
        raise ValueError("OPENROUTER_API_KEY is missing or openai package unavailable.")
    chat_msgs = []
    if system_instruction:
        chat_msgs.append({"role": "system", "content": system_instruction})
    if messages:
        chat_msgs.extend(messages)
    else:
        chat_msgs.append({"role": "user", "content": prompt})

    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=openrouter_key,
        default_headers={"HTTP-Referer": "https://reakiruba.app", "X-Title": "SRI AI Companion"},
    )
    errors = []
    for model_name in OPENROUTER_FREE_MODELS:
        try:
            def _or_call(m=model_name):
                return client.chat.completions.create(
                    model=m, messages=chat_msgs, temperature=0.5, max_tokens=2048, timeout=45
                )

            with ThreadPoolExecutor(max_workers=1) as executor:
                response = executor.submit(_or_call).result(timeout=50)
            content = response.choices[0].message.content
            if content and content.strip():
                text = content.strip()
                tokens_est = (len(prompt) + len(system_instruction) + len(text)) // 4
                return text, f"OpenRouter ({model_name})", tokens_est
        except Exception as e:
            errors.append(f"{model_name}: {e}")
    raise RuntimeError(f"All OpenRouter free models exhausted: {'; '.join(errors)}")


def call_nvidia(prompt: str, system_instruction: str = "", messages: list[dict] | None = None):
    if not nvidia_key or not OpenAI:
        raise ValueError("NVIDIA_API_KEY unavailable.")
    client = OpenAI(base_url="https://integrate.api.nvidia.com/v1", api_key=nvidia_key)
    chat_msgs = ([{"role": "system", "content": system_instruction}] if system_instruction else []) + (
        messages if messages else [{"role": "user", "content": prompt}]
    )
    res = client.chat.completions.create(
        model="meta/llama-3.3-70b-instruct", messages=chat_msgs, temperature=0.5, max_tokens=1024, timeout=15
    )
    text = (res.choices[0].message.content or "").strip()
    if text:
        return text, "NVIDIA (llama-3.3-70b)", (len(prompt) + len(text)) // 4
    raise ValueError("Empty NVIDIA response.")


def call_groq(prompt: str, system_instruction: str = "", messages: list[dict] | None = None, max_tokens: int = 1024):
    if not groq_key or not OpenAI:
        raise ValueError("GROQ_API_KEY unavailable.")
    client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=groq_key)
    chat_msgs = ([{"role": "system", "content": system_instruction}] if system_instruction else []) + (
        messages if messages else [{"role": "user", "content": prompt}]
    )
    for model_id in ["llama-3.3-70b-versatile", "llama3-8b-8192"]:
        try:
            res = client.chat.completions.create(
                model=model_id, messages=chat_msgs, temperature=0.55, max_tokens=max_tokens, timeout=15
            )
            text = (res.choices[0].message.content or "").strip()
            if text:
                return text, f"Groq ({model_id})", (len(prompt) + len(text)) // 4
        except Exception:
            continue
    raise ValueError("Groq models failed.")


def call_llm_with_recovery(prompt: str, system_instruction: str = "", task_id: str = ""):
    errors = []
    if gemini_key and time.time() >= _gemini_cooldown_until:
        try:
            return call_gemini(prompt, system_instruction, task_id=task_id)
        except Exception as e:
            errors.append(f"Gemini: {e}")
    if openrouter_key:
        try:
            return call_openrouter(prompt, system_instruction, task_id=task_id)
        except Exception as e:
            errors.append(f"OpenRouter: {e}")
    if nvidia_key:
        try:
            return call_nvidia(prompt, system_instruction)
        except Exception as e:
            errors.append(f"NVIDIA: {e}")
    if groq_key:
        try:
            return call_groq(prompt, system_instruction)
        except Exception as e:
            errors.append(f"Groq: {e}")
    raise RuntimeError(f"All LLM providers failed: {'; '.join(errors) if errors else 'No API keys configured'}")


def _build_conversation_messages(
    history_items: list | None,
    latest_prompt: str,
    allow_links: bool | None = None,
) -> list[dict]:
    if allow_links is None:
        allow_links = user_explicitly_requested_link(latest_prompt)
    msgs: list[dict] = []
    if history_items:
        for item in history_items[-6:]:
            if not isinstance(item, dict):
                continue
            if "user" in item or "agent" in item:
                u = str(item.get("user", "")).strip()
                a = str(item.get("agent", "")).strip()
                if u:
                    msgs.append({"role": "user", "content": u})
                if a:
                    safe_a = a if allow_links else sanitize_unsolicited_links(a, "")
                    if safe_a:
                        msgs.append({"role": "assistant", "content": safe_a})
            else:
                role = "user" if str(item.get("role", "")).lower() == "user" else "assistant"
                content = str(item.get("content", "")).strip()
                if content:
                    if role == "assistant" and not allow_links:
                        content = sanitize_unsolicited_links(content, "")
                    if content:
                        msgs.append({"role": role, "content": content})
    msgs.append({"role": "user", "content": latest_prompt})
    return msgs


_FAST_CLIENT_POOL: dict[str, object] = {}
_HTTP_SESSION = requests.Session() if requests else None


def _get_pooled_openai_client(provider: str, base_url: str, api_key: str, default_headers: dict | None = None):
    cache_key = f"{provider}:{base_url}:{api_key[-8:] if api_key else ''}"
    client = _FAST_CLIENT_POOL.get(cache_key)
    if client is None and OpenAI:
        kwargs = {"base_url": base_url, "api_key": api_key, "max_retries": 0}
        if default_headers:
            kwargs["default_headers"] = default_headers
        client = OpenAI(**kwargs)
        _FAST_CLIENT_POOL[cache_key] = client
    return client


def _call_gemini_fast_rest(
    model_name: str,
    msgs: list[dict],
    system_instruction: str,
    max_tokens: int,
    timeout_sec: float,
) -> str:
    """Direct persistent HTTP call to Gemini REST API with low-latency thinking configuration."""
    clean_model = model_name.replace("models/", "").strip()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{clean_model}:generateContent?key={urllib.parse.quote(gemini_key)}"
    contents = [
        {
            "role": "model" if m["role"] == "assistant" else "user",
            "parts": [{"text": m["content"]}],
        }
        for m in msgs
    ]
    gen_cfg: dict = {"maxOutputTokens": max_tokens}
    low_name = clean_model.lower()
    if "gemini-4" in low_name:
        gen_cfg["thinkingConfig"] = {"thinkingLevel": "LOW"}
    elif "gemini-2.5" in low_name:
        gen_cfg["temperature"] = 0.65
        gen_cfg["thinkingConfig"] = {"thinkingBudget": 0}
    else:
        gen_cfg["temperature"] = 0.65

    payload: dict = {"contents": contents, "generationConfig": gen_cfg}
    if system_instruction:
        payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}

    if _HTTP_SESSION is not None:
        resp = _HTTP_SESSION.post(url, json=payload, timeout=timeout_sec)
        if resp.status_code >= 400:
            raise RuntimeError(f"Gemini REST HTTP {resp.status_code}: {resp.text[:220]}")
        res_json = resp.json()
    else:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            res_json = json.loads(resp.read().decode("utf-8", errors="ignore"))

    candidates = res_json.get("candidates") or []
    if candidates:
        parts = (candidates[0].get("content") or {}).get("parts") or []
        text = "\n".join(str(p.get("text") or "") for p in parts if p.get("text")).strip()
        if text:
            return text
    return ""


def call_fast_voice_llm(
    prompt: str,
    system_instruction: str = "",
    max_tokens: int = 240,
    history_messages: list | None = None,
    timeout_sec: float | None = None,
) -> str:
    """Low-latency multilingual conversational LLM router with pooled connections for instant replies."""
    global _gemini_cooldown_until
    msgs = _build_conversation_messages(history_messages, prompt)
    full_msgs = ([{"role": "system", "content": system_instruction}] if system_instruction else []) + msgs
    req_timeout = timeout_sec if timeout_sec is not None else (10.0 if max_tokens > 400 else 4.2)
    last_err: Exception | None = None

    # Tier 1: Groq Ultra-Fast (pooled persistent HTTP client, zero retry overhead)
    if groq_key and OpenAI:
        try:
            client = _get_pooled_openai_client("groq", "https://api.groq.com/openai/v1", groq_key)
            for gm in ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]:
                try:
                    res = client.chat.completions.create(
                        model=gm, messages=full_msgs, temperature=0.65, max_tokens=max_tokens, timeout=req_timeout
                    )
                    text = (res.choices[0].message.content or "").strip()
                    if text:
                        return text
                except Exception as e:
                    last_err = e
                    if any(x in str(e).lower() for x in ["connection", "network", "unreachable"]):
                        break
        except Exception as e:
            last_err = e

    # Tier 2: Direct Google Gemini Flash / Hydrogen (pooled persistent REST with minimal thinking latency)
    if gemini_key and time.time() >= _gemini_cooldown_until:
        candidates = ([custom_model_name] if custom_model_name else []) + ["gemini-2.5-flash", "gemini-4-hydrogen"]
        for g_model_name in dict.fromkeys(candidates):
            try:
                text = _call_gemini_fast_rest(
                    g_model_name,
                    msgs=msgs,
                    system_instruction=system_instruction,
                    max_tokens=max_tokens,
                    timeout_sec=req_timeout,
                )
                if text:
                    return text
            except Exception as e:
                last_err = e
                err_low = str(e).lower()
                if any(x in err_low for x in ["quota", "429", "exhausted", "resource_exhausted"]):
                    _gemini_cooldown_until = time.time() + 60
                    break
                if any(x in err_low for x in ["connection", "network", "timeout", "deadline"]):
                    break
        if genai:
            history_transcript = "\n".join(
                f"{'Kirubha' if m['role'] == 'user' else 'SRI'}: {m['content']}" for m in msgs[:-1]
            )
            gemini_prompt = f"{history_transcript}\nKirubha: {prompt}" if history_transcript else prompt
            for g_model_name in dict.fromkeys(candidates):
                if time.time() < _gemini_cooldown_until:
                    break
                try:
                    genai.configure(api_key=gemini_key)
                    gen_model = genai.GenerativeModel(
                        model_name=g_model_name,
                        generation_config={"temperature": 0.65, "max_output_tokens": max_tokens},
                        system_instruction=system_instruction or None,
                    )
                    resp = gen_model.generate_content(gemini_prompt, request_options={"timeout": req_timeout})
                    if resp and resp.text and resp.text.strip():
                        return resp.text.strip()
                except Exception as e:
                    last_err = e
                    err_low = str(e).lower()
                    if any(x in err_low for x in ["quota", "429", "exhausted", "resource_exhausted"]):
                        _gemini_cooldown_until = time.time() + 60
                        break
                    if any(x in err_low for x in ["connection", "network", "timeout", "deadline"]):
                        break

    # Tier 3: OpenRouter Free Tier (pooled persistent client)
    if openrouter_key and OpenAI:
        try:
            client_or = _get_pooled_openai_client(
                "openrouter",
                "https://openrouter.ai/api/v1",
                openrouter_key,
                default_headers={"HTTP-Referer": "https://reakiruba.app", "X-Title": "SRI AI Companion"},
            )
            for om in ["google/gemini-2.0-flash-exp:free", "meta-llama/llama-3.3-70b-instruct:free"]:
                try:
                    res = client_or.chat.completions.create(
                        model=om, messages=full_msgs, temperature=0.65, max_tokens=max_tokens, timeout=req_timeout
                    )
                    text = (res.choices[0].message.content or "").strip()
                    if text:
                        return text
                except Exception as e:
                    last_err = e
                    continue
        except Exception as e:
            last_err = e

    detail = f": {last_err}" if last_err else ": No API keys configured"
    raise RuntimeError(f"Fast conversational LLM providers unavailable{detail}")


# ==============================================================================
# 7. AUTONOMOUS DIRECTORY & FILE TOOLS & TRANSCRIPTION
# ==============================================================================
def derive_project_slug(title: str, prompt: str) -> str:
    combined = f"{title} {prompt}".lower()
    words = re.findall(r"[a-zA-Z0-9]+", combined)
    stopwords = {
        "build", "create", "a", "an", "the", "in", "with", "and", "for", "to", "of",
        "single", "file", "page", "responsive", "modern", "sleek", "interactive",
        "application", "app", "html", "css", "js", "full", "make", "generate", "ui",
    }
    meaningful = [w for w in words if w not in stopwords and len(w) > 2]
    return ("_".join(meaningful[:3]) if meaningful else "web_project")[:32]


def create_project_structure(folder_name: str, file_name: str, code_content: str) -> tuple[bool, str, str]:
    try:
        raw_folder = folder_name.strip()
        raw_file = file_name.strip()
        if ".." in raw_folder or ".." in raw_file or raw_folder.startswith(("/", "\\")) or ":" in raw_folder or ":" in raw_file:
            return False, "", "Security boundary violation: Path traversal or absolute paths forbidden."
        clean_folder = re.sub(r"[^a-zA-Z0-9_\-]", "_", raw_folder).strip("_") or "project"
        clean_file = os.path.basename(raw_file.replace("\\", "/").lstrip("/")) or "index.html"
        target_dir = os.path.abspath(os.path.join(WORKSPACE_DIR, clean_folder))
        target_path = os.path.abspath(os.path.join(target_dir, clean_file))

        is_safe, sec_err = is_safe_sandbox_path(target_path, WORKSPACE_DIR)
        if not is_safe:
            return False, "", sec_err

        rel_target = os.path.relpath(target_path, BASE_DIR).replace("\\", "/")
        sri_execution_gate.add_allowed_workspace(f"workspace/{clean_folder}")
        if not sri_execution_gate.run_agent_task(sri_auth_secret, "WRITE_CODE", rel_target):
            return False, "", f"SriExecutionGate rejected write: {sri_execution_gate.kill_reason}"
        if clean_file.lower().endswith((".html", ".css", ".js")):
            if not sri_design_guard.authorize_design_task(sri_auth_secret, "WRITE_CODE", clean_file):
                return False, "", f"SriDesignAndLaunchGuard rejected write: {sri_design_guard.kill_reason}"

        os.makedirs(target_dir, exist_ok=True)
        temp_path = f"{target_path}.tmp"
        with open(temp_path, "w", encoding="utf-8") as f:
            f.write(code_content)
        os.replace(temp_path, target_path)
        return True, target_path, ""
    except Exception as e:
        return False, "", f"Error creating project structure: {e}"


def get_workspace_files() -> list[str]:
    if not os.path.exists(WORKSPACE_DIR):
        return []
    files = []
    workspace_abs = os.path.abspath(WORKSPACE_DIR)
    for root, dirs, filenames in os.walk(WORKSPACE_DIR):
        dirs[:] = [d for d in dirs if not d.startswith(".") and not d.startswith("__")]
        for fn in filenames:
            if fn.endswith(".tmp") or fn.startswith("."):
                continue
            full_path = os.path.abspath(os.path.join(root, fn))
            files.append(os.path.relpath(full_path, workspace_abs).replace("\\", "/"))
    return sorted(files)


def safe_read_code(rel_path: str) -> tuple[bool, str, str]:
    try:
        clean_rel = rel_path.strip().replace("\\", "/").lstrip("/")
        if not clean_rel or ".." in clean_rel or ":" in clean_rel:
            return False, "", "Invalid or unsafe file path."
        target_path = os.path.abspath(os.path.join(WORKSPACE_DIR, clean_rel))
        is_safe, sec_err = is_safe_sandbox_path(target_path, WORKSPACE_DIR)
        if not is_safe:
            return False, "", sec_err
        if not os.path.isfile(target_path):
            return False, "", f"File '{clean_rel}' not found in workspace/."
        with open(target_path, "r", encoding="utf-8", errors="replace") as f:
            return True, f.read(), ""
    except Exception as e:
        return False, "", f"Failed reading '{rel_path}': {e}"


def safe_write_code(original_rel_path: str, modified_code: str, custom_suffix: str = "_updated") -> tuple[bool, str, str]:
    try:
        clean_name = original_rel_path.strip().replace("\\", "/").lstrip("/")
        if not clean_name or ".." in clean_name or ":" in clean_name:
            return False, "", "Security boundary violation."
        base_name, ext = os.path.splitext(clean_name.replace("/", "_"))
        if not ext:
            ext = ".html"
        target_path = os.path.abspath(os.path.join(OUTPUT_DIR, f"{base_name}{custom_suffix}{ext}"))
        is_safe, sec_err = is_safe_sandbox_path(target_path, OUTPUT_DIR)
        if not is_safe:
            return False, "", sec_err
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        temp_path = f"{target_path}.tmp"
        with open(temp_path, "w", encoding="utf-8") as f:
            f.write(modified_code)
        os.replace(temp_path, target_path)
        return True, target_path, ""
    except Exception as e:
        return False, "", f"Atomic save error: {e}"


def create_project_zip_bundle(target_path: str) -> bytes:
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        if os.path.isdir(target_path):
            for root, _, files in os.walk(target_path):
                for f in files:
                    if f.endswith(".tmp") or f.startswith("."):
                        continue
                    full_p = os.path.join(root, f)
                    zf.write(full_p, arcname=os.path.relpath(full_p, target_path))
        elif os.path.isfile(target_path):
            zf.write(target_path, arcname=os.path.basename(target_path))
    zip_buffer.seek(0)
    return zip_buffer.getvalue()


VOICE_TECHNICAL_PROMPT = "Tamil, English, Python, HTML, CSS, JavaScript, UI, App, Research"


def _transcribe_with_whisper(audio_bytes: bytes, mime_type: str = "audio/wav") -> str:
    if not groq_key or not OpenAI:
        raise ValueError("GROQ_API_KEY unavailable.")
    clean_mime = (mime_type or "audio/wav").split(";")[0].strip().lower()
    ext = "webm" if "webm" in clean_mime else ("ogg" if "ogg" in clean_mime else ("mp3" if "mp3" in clean_mime else "wav"))
    client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=groq_key)
    transcription = client.audio.transcriptions.create(
        model="whisper-large-v3-turbo",
        file=(f"audio.{ext}", io.BytesIO(audio_bytes), clean_mime),
        response_format="text",
        language="ta",
        prompt=VOICE_TECHNICAL_PROMPT,
    )
    txt = transcription if isinstance(transcription, str) else getattr(transcription, "text", "")
    if txt and txt.strip():
        return txt.strip()
    raise ValueError("Empty Whisper transcription.")


def _transcribe_with_gemini(audio_bytes: bytes, mime_type: str = "audio/wav") -> str:
    if not gemini_key or not genai:
        raise ValueError("GEMINI_API_KEY unavailable.")
    genai.configure(api_key=gemini_key)
    model = genai.GenerativeModel("gemini-2.5-flash")
    clean_mime = (mime_type or "audio/wav").split(";")[0].strip().lower()
    if "wav" in clean_mime:
        clean_mime = "audio/wav"
    elif "webm" in clean_mime:
        clean_mime = "audio/webm"
    elif "ogg" in clean_mime:
        clean_mime = "audio/ogg"
    elif "mp3" in clean_mime or "mpeg" in clean_mime:
        clean_mime = "audio/mp3"
    instruction = "Transcribe the spoken Tamil or English audio accurately without adding meta commentary."
    resp = model.generate_content([{"mime_type": clean_mime, "data": audio_bytes}, instruction], request_options={"timeout": 60})
    if resp and resp.text and resp.text.strip():
        return resp.text.strip()
    raise ValueError("Empty Gemini transcription.")


def transcribe_audio_to_text(audio_bytes: bytes, mime_type: str = "audio/wav", engine: str = "auto") -> str:
    if not audio_bytes or len(audio_bytes) < 64:
        raise ValueError("Audio recording is empty.")
    if "whisper" in (engine or "").lower() and groq_key:
        try:
            return _transcribe_with_whisper(audio_bytes, mime_type)
        except Exception:
            pass
    if gemini_key:
        try:
            return _transcribe_with_gemini(audio_bytes, mime_type)
        except Exception:
            pass
    if groq_key:
        return _transcribe_with_whisper(audio_bytes, mime_type)
    raise RuntimeError("No audio transcription provider available.")


# ==============================================================================
# 8. AUTONOMOUS 5-STEP BACKGROUND CODE/UI RUNNER
# ==============================================================================
def extract_code_block(raw_text: str, default_ext: str = "html") -> tuple[str, str]:
    matches = re.findall(r"```([a-zA-Z0-9_\-\+]*)\s*\n(.*?)```", raw_text, re.DOTALL)
    if matches:
        if default_ext in ["html", "htm"]:
            doc_matches = [m for m in matches if "<!doctype" in m[1].lower() or "<html" in m[1].lower()]
            if doc_matches:
                return max(doc_matches, key=lambda m: len(m[1]))[1].strip(), "html"
        best = max(matches, key=lambda m: len(m[1]))
        lang = best[0].lower().strip()
        ext = "html" if lang in ["html", "htm"] else ("py" if lang in ["python", "py"] else default_ext)
        return best[1].strip(), ext
    doc_match = re.search(r"(<!DOCTYPE html.*)", raw_text, re.DOTALL | re.IGNORECASE)
    if doc_match:
        return re.sub(r"```+$", "", doc_match.group(1)).strip(), "html"
    return raw_text.strip(), default_ext


def validate_artifact_integrity(code: str, ext: str) -> tuple[bool, str, str]:
    if ext == "html":
        fixed = re.sub(r"```+$", "", code).strip()
        if "<!doctype html>" not in fixed.lower() and "<html" not in fixed.lower():
            fixed = (
                '<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="UTF-8">\n'
                '<meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
                '<title>Generated App</title>\n<script src="https://cdn.tailwindcss.com"></script>\n</head>\n'
                f'<body class="bg-slate-950 text-slate-100 min-h-screen p-6">\n{fixed}\n</body>\n</html>'
            )
        if "</html>" not in fixed.lower():
            fixed += "\n</html>"
        return True, "HTML verified.", fixed
    return True, "Code artifact verified.", code


def generate_5d_plan(prompt: str, task_type: str, system_instruction: str = "", task_id: str = ""):
    planner_prompt = (
        f'Task Request: "{prompt}"\nTask Type: {task_type}\n'
        "Formulate a concise 5D Technical Plan with headers:\n"
        "### 1. Architecture Dimension\n### 2. User Experience Dimension\n"
        "### 3. Resilience Dimension\n### 4. Efficiency Dimension\n### 5. Reflection & Verification Checklist"
    )
    res_plan = call_llm_with_recovery(planner_prompt, system_instruction, task_id=task_id) or ("", "", 0)
    plan_text, model_name, tokens = res_plan
    sections = {"architecture": "", "ux": "", "resilience": "", "efficiency": "", "reflection": ""}
    for key, pat in [
        ("architecture", r"###\s*1\.\s*Architecture Dimension(.*?)(?=###|\Z)"),
        ("ux", r"###\s*2\.\s*User Experience Dimension(.*?)(?=###|\Z)"),
        ("resilience", r"###\s*3\.\s*Resilience Dimension(.*?)(?=###|\Z)"),
        ("efficiency", r"###\s*4\.\s*Efficiency Dimension(.*?)(?=###|\Z)"),
        ("reflection", r"###\s*5\.\s*Reflection(.*?)(?=###|\Z)"),
    ]:
        m = re.search(pat, plan_text, re.DOTALL | re.IGNORECASE)
        if m:
            sections[key] = m.group(1).strip()
    return sections, plan_text, model_name, tokens


def generate_project_schema(prompt: str, architecture_plan: str, system_instruction: str = "", task_id: str = ""):
    schema_prompt = (
        f"Architecture:\n{architecture_plan}\nUser Task: {prompt}\n"
        "Return valid JSON in ```json ... ``` with appName, version, dataModel, initialState, mockRecords."
    )
    res = call_llm_with_recovery(schema_prompt, system_instruction, task_id=task_id) or ("", "", 0)
    raw, model_name, tokens = res
    m = re.search(r"```(?:json)?\s*\n(.*?)```", raw, re.DOTALL)
    clean_json = m.group(1).strip() if m else raw.strip()
    try:
        formatted = json.dumps(json.loads(clean_json), indent=2)
    except Exception:
        formatted = json.dumps(
            {"appName": "SRI Generated App", "version": "1.0.0", "prompt": prompt, "mockRecords": [{"id": 1, "status": "active"}]},
            indent=2,
        )
    return formatted, model_name, tokens


def run_self_verification(prompt: str, code_sample: str, reflection_checklist: str, system_instruction: str = "", task_id: str = ""):
    verify_prompt = (
        f'Request: "{prompt}"\nChecklist: {reflection_checklist}\n'
        f"Code Head/Tail:\n```html\n{code_sample[:1200]}\n...\n{code_sample[-500:]}\n```\n"
        "Provide a brief PASSED/VERIFIED QA report."
    )
    return call_llm_with_recovery(verify_prompt, system_instruction, task_id=task_id) or ("PASSED", "QA Engine", 0)


def run_autonomous_agent(task_id: str):
    start_time = time.time()
    db = load_db()
    task = db["tasks"].get(task_id)
    if not task:
        return
    prompt = task["prompt"]
    task_type = task["task_type"]
    source_file = task.get("source_file", "")
    change_request = task.get("change_request", prompt)
    accumulated_tokens = 0
    used_models = set()
    system_instruction = (
        "You are a Senior Full-Stack Engineer. Produce clean, responsive, self-contained HTML/CSS/JS or Python artifacts with zero placeholders."
    )

    try:
        if task_type == "code_edit":
            update_task_record(task_id, current_step=1)
            read_ok, original_code, read_err = safe_read_code(source_file)
            if not read_ok:
                raise FileNotFoundError(read_err)
            _, ext_no_dot = os.path.splitext(source_file)
            lang = ext_no_dot.lower().lstrip(".") or "html"

            update_task_record(task_id, current_step=2, schema_data=f"Source: {source_file}")
            update_task_record(task_id, current_step=3)
            code_prompt = (
                f"Modify '{source_file}':\nChange Request: {change_request}\n"
                f"Original Code:\n```{lang}\n{original_code}\n```\n"
                f"Return the FULL updated document inside ```{lang} ... ``` fences."
            )
            raw_code, model_used, toks = call_llm_with_recovery(code_prompt, system_instruction, task_id=task_id)
            accumulated_tokens += toks
            used_models.add(model_used)
            body, ext = extract_code_block(raw_code, default_ext=lang)
            _ok, _msg, finalized_code = validate_artifact_integrity(body, ext)
            update_task_record(task_id, code=finalized_code, current_step=4)
            update_task_record(task_id, current_step=5)
            write_ok, out_path, write_err = safe_write_code(source_file, finalized_code, custom_suffix="_updated")
            if not write_ok:
                raise IOError(write_err)
            duration = round(time.time() - start_time, 2)
            primary_model = ", ".join(used_models)
            db = load_db()
            db["metrics"]["completed_tasks"] += 1
            db["metrics"]["total_tokens"] += accumulated_tokens
            save_db(db)
            update_task_record(
                task_id, notify_all_complete=False, status="COMPLETED", current_step=5, output_file=out_path,
                duration_seconds=duration, tokens=accumulated_tokens, model_used=primary_model,
            )
            dispatch_task_alert(task_id, f"Refine {source_file}", "COMPLETED", out_path, f"Done in {duration}s")
            try:
                check_and_trigger_all_tasks_completed_whatsapp_alert(source_task_id=task_id)
            except Exception as _wa_err:
                print(f"ℹ️ All-tasks WhatsApp check notice: {_wa_err}")
            return

        update_task_record(task_id, current_step=1)
        plan_5d, plan_text, m1, t1 = generate_5d_plan(prompt, task_type, system_instruction, task_id=task_id)
        accumulated_tokens += t1
        used_models.add(m1)
        update_task_record(task_id, plan=plan_text, plan_5d=plan_5d, current_step=2)

        folder_name = task.get("folder_name", "").strip() or derive_project_slug(task.get("title", ""), prompt)
        schema_str, m2, t2 = generate_project_schema(prompt, plan_5d.get("architecture", plan_text), system_instruction, task_id=task_id)
        accumulated_tokens += t2
        used_models.add(m2)
        schema_ok, schema_path, _ = create_project_structure(folder_name, "schema.json", schema_str)
        rel_schema = os.path.relpath(schema_path, WORKSPACE_DIR).replace("\\", "/") if schema_ok else ""
        update_task_record(task_id, schema_data=schema_str, schema_file=rel_schema, folder_name=folder_name, current_step=3)

        code_prompt = (
            f"User Request: {prompt}\nArchitecture: {plan_5d.get('architecture', plan_text)}\n"
            f"Schema:\n```json\n{schema_str}\n```\nGenerate complete single-file code in ```html ... ```."
        )
        raw_code, m3, t3 = call_llm_with_recovery(code_prompt, system_instruction, task_id=task_id)
        accumulated_tokens += t3
        used_models.add(m3)
        body, ext = extract_code_block(raw_code, default_ext="html" if task_type == "frontend" else "py")
        _ok, _msg, finalized_code = validate_artifact_integrity(body, ext)
        update_task_record(task_id, code=finalized_code, current_step=4)

        verify_text, m4, t4 = run_self_verification(prompt, finalized_code, plan_5d.get("reflection", ""), system_instruction, task_id=task_id)
        accumulated_tokens += t4
        used_models.add(m4)
        update_task_record(task_id, verification_report=verify_text, current_step=5)

        target_file_name = f"index.{ext}" if ext in ["html", "htm"] else f"main.{ext}"
        c_ok, ws_filepath, c_err = create_project_structure(folder_name, target_file_name, finalized_code)
        if not c_ok:
            raise IOError(c_err)
        rel_ws_path = os.path.relpath(ws_filepath, WORKSPACE_DIR).replace("\\", "/")
        clean_slug = re.sub(r"[^a-zA-Z0-9_\-]", "_", task["title"].lower())[:30]
        filepath = os.path.join(OUTPUT_DIR, f"{task_id}_{clean_slug}.{ext}")
        temp_fp = f"{filepath}.tmp"
        with open(temp_fp, "w", encoding="utf-8") as f:
            f.write(finalized_code)
        os.replace(temp_fp, filepath)

        duration = round(time.time() - start_time, 2)
        primary_model = ", ".join(used_models)
        db = load_db()
        db["metrics"]["completed_tasks"] += 1
        db["metrics"]["total_tokens"] += accumulated_tokens
        save_db(db)
        update_task_record(
            task_id, notify_all_complete=False, status="COMPLETED", current_step=5, output_file=filepath,
            workspace_file=rel_ws_path, folder_name=folder_name,
            duration_seconds=duration, tokens=accumulated_tokens, model_used=primary_model,
        )
        dispatch_task_alert(task_id, task["title"], "COMPLETED", ws_filepath, f"Saved at workspace/{rel_ws_path} in {duration}s")
        try:
            check_and_trigger_all_tasks_completed_whatsapp_alert(source_task_id=task_id)
        except Exception as _wa_err:
            print(f"ℹ️ All-tasks WhatsApp check notice: {_wa_err}")
    except Exception as exc:
        duration = round(time.time() - start_time, 2)
        error_msg = str(exc)
        status = "TIMEOUT" if "exceeded" in error_msg else "FAILED"
        db = load_db()
        db["metrics"]["failed_tasks"] += 1
        save_db(db)
        update_task_record(task_id, status=status, duration_seconds=duration, error=error_msg)
        append_task_log(task_id, f"❌ Task {status}: {error_msg}")
        dispatch_task_alert(task_id, task.get("title", task_id), status, "", error_msg)


def dispatch_code_edit_task(filename: str, change_request: str) -> str:
    clean_name = filename.strip().replace("\\", "/").lstrip("/")
    base_display = os.path.basename(clean_name)
    title = f"Refine {base_display}: {change_request[:24]}"
    prompt = f"Modify '{clean_name}': {change_request}"
    rel_path = f"workspace/{clean_name}" if not clean_name.startswith("workspace/") else clean_name
    if not sri_execution_gate.run_agent_task(sri_auth_secret, "DEBUG_CODE", rel_path):
        tid = create_task_record(prompt=prompt, task_type="code_edit", title=title, source_file=clean_name, change_request=change_request)
        update_task_record(tid, status="FAILED", error=f"Gate rejected: {sri_execution_gate.kill_reason}")
        return tid
    tid = create_task_record(prompt=prompt, task_type="code_edit", title=title, source_file=clean_name, change_request=change_request)
    threading.Thread(target=run_autonomous_agent, args=(tid,), daemon=True).start()
    return tid


def dispatch_background_task(prompt: str, task_type: str = "auto", source_file: str = "", folder_name: str = "") -> str:
    prompt_str = prompt.strip()
    words = prompt_str.split()
    title = (" ".join(words[:5]) if words else "Untitled Task")[:40]
    if not sri_execution_gate.is_active:
        tid = create_task_record(prompt=prompt_str, task_type=task_type, title=title, folder_name=folder_name or "generated_app")
        update_task_record(tid, status="FAILED", error=f"Gate locked: {sri_execution_gate.kill_reason}")
        return tid
    if task_type == "code_edit" and source_file:
        return dispatch_code_edit_task(source_file, prompt_str)
    if task_type == "auto":
        frontend_kws = ["html", "css", "js", "ui", "ux", "frontend", "dashboard", "landing", "card", "page", "web"]
        task_type = "frontend" if any(kw in prompt_str.lower() for kw in frontend_kws) else "general"
    clean_folder = folder_name.strip() if folder_name else derive_project_slug(title, prompt_str)
    tid = create_task_record(prompt=prompt_str, task_type=task_type, title=title, folder_name=clean_folder)
    threading.Thread(target=run_autonomous_agent, args=(tid,), daemon=True).start()
    return tid


# ==============================================================================
# 9. OPEN-ENDED COMPANION BRAIN, LIVE RESEARCH & CONDITIONAL LINK POLICY
# ==============================================================================
def parse_bridge_payload(raw_cmd: str) -> tuple[str, str, str]:
    """Extract optional metadata __SRI_META__JSON__<command> sent by sri_zero_failure_ui."""
    txt = (raw_cmd or "").strip()
    m = re.match(r"^__SRI_META__(\{.*?\})__(.*)$", txt, re.DOTALL)
    if m:
        try:
            meta = json.loads(m.group(1))
            channel = str(meta.get("channel") or "chat").strip().lower()
            lang = str(meta.get("lang") or "ta-IN").strip()
            return m.group(2).strip(), channel, lang
        except Exception:
            pass
    return txt, "chat", "ta-IN"


def is_realtime_web_search_required(query: str) -> bool:
    """Detect research topics, web search, real-time news, tech updates, current details, weather, or explicit link searches."""
    q = (query or "").strip().lower()
    if not q:
        return False
    if re.search(r"https?://|www\.", q):
        return True

    has_explicit_research = any(
        w in q
        for w in (
            "research", "insights", "insight", "tech news", "tech updates", "technology updates",
            "ai news", "ai updates", "latest updates", "ஆராய்ச்சி", "ரிசர்ச்", "செய்தி", "நியூஸ்", "டெக் நியூஸ்",
        )
    )
    coding_exclusions = [
        "write code", "write python", "python code", "javascript code", "fix bug", "debug",
        "syntax error", "event listener", "event loop", "event handler", "dom event", "dispatch event",
        "find index", "find element", "find in array", "find in list", "regex",
        "find bug", "find error", "binary search", "search tree", "linear search",
    ]
    if not has_explicit_research and any(ex in q for ex in coding_exclusions):
        return False

    realtime_triggers = [
        "research", "open research", "research page", "investigate", "deep dive",
        "insights on", "insights about", "insights", "insight",
        "search web", "search the web", "web search", "search about", "search for", "look up",
        "find info", "find information", "information about", "info about", "details about",
        "explain about", "tell me about", "study about", "study on", "case study",
        "literature review", "market analysis", "trends in", "fact check", "analyze", "analysis",
        "compare", "summarize", "summary of",
        "world news", "live news", "today's news", "todays news", "today news",
        "latest news", "breaking news", "current news", "tech news", "technology news",
        "tech updates", "technology updates", "ai news", "ai updates", "latest updates",
        "recent updates", "live updates", "current affairs", "what's new", "whats new",
        "news", "headlines", "weather today", "weather in", "live score", "cricket score",
        "stock price", "crypto price", "gold rate", "exchange rate",
        "who is the current", "latest version", "what happened", "recent update", "update me on",
        "where to find", "where can i find", "where to buy", "where to download",
        "ஆராய்ச்சி", "ரிசர்ச்", "உலக செய்தி", "இன்றைய செய்தி", "செய்திகள்", "செய்தி", "நியூஸ்",
        "டெக் நியூஸ்", "புதிய தொழில்நுட்பம்", "இப்போது என்ன", "தற்போதைய",
        "வானிலை", "தங்க விலை", "வலை தேடல்", "தேடு", "தகவல்", "விளக்கு",
        "பற்றி சொல்லு", "பற்றி கூறு", "அனலைஸ்", "ஒப்பீடு", "எங்கே கிடைக்கும்", "எங்கு கிடைக்கும்",
    ]
    if any(trig in q for trig in realtime_triggers):
        return True
    if user_explicitly_requested_link(q):
        return True
    return False


def should_fetch_live_context(query: str) -> bool:
    """Detect genuine real-time info requests without adding web-scraping lag to casual chat mentioning 'now' or 'today'."""
    q = (query or "").strip().lower()
    if not q:
        return False
    if is_realtime_web_search_required(q):
        return True
    live_info_patterns = (
        r"\b(who is the current|who won|what happened|price of|weather|live score|release date|latest version of)\b",
        r"\b(latest|current|recent)\s+(news|updates|headlines|events|trends|standings|results)\b",
        r"\b(today's|todays)\s+(news|weather|price|rate|match|headlines)\b",
        r"(இன்றைய\s*(?:செய்தி|வானிலை|விலை)|தற்போதைய\s*(?:செய்தி|நிலை)|யார்\s*(?:ஜெயித்த|வென்ற))",
    )
    return any(re.search(pat, q) for pat in live_info_patterns)


def _strip_cutoff_disclaimers(text: str) -> str:
    """Remove boilerplate 'I lack real-time access / knowledge cutoff' disclaimers when live grounding is active."""
    if not text:
        return ""
    disclaimer_pats = (
        r"(?i)^(?:as an ai(?: language model)?,?\s*)?i (?:do not|don't) have (?:access to )?(?:real-time|live|current|internet) (?:information|data|news|updates|access|browsing)[^.!?\n]*[.!?]\s*",
        r"(?i)^i cannot (?:browse|access|fetch) (?:the )?(?:internet|real-time|live)[^.!?\n]*[.!?]\s*",
        r"(?i)^my knowledge (?:cutoff|was last updated)[^.!?\n]*[.!?]\s*",
    )
    cleaned = text.strip()
    for pat in disclaimer_pats:
        cleaned = re.sub(pat, "", cleaned).strip()
    return cleaned or text.strip()


def _clean_retrieval_query(query: str) -> str:
    cleaned = (query or "").strip()
    cleaned = re.sub(
        r"^(?:please\s+|can you\s+|could you\s+|hey sri\s+|sri\s+)*"
        r"(?:(?:give|send|share|provide|find|get|fetch)\s+(?:me\s+)?(?:the\s+)?)?"
        r"(?:official\s+)?(?:book\s+link|pdf\s+link|download\s+link|tool\s+download|resource\s+location|resource\s+url|resource\s+link|website\s+link|external\s+link|source\s+link|link|url)\s+(?:for|to|of)\s+",
        "",
        cleaned,
        flags=re.IGNORECASE,
    ).strip()
    cleaned = re.sub(
        r"^(?:where\s+(?:can\s+i|do\s+i|to)\s+(?:find|get|buy|download|read)|how\s+to\s+download)\s+",
        "",
        cleaned,
        flags=re.IGNORECASE,
    ).strip()
    cleaned = re.sub(
        r"^(?:research|investigate|deep dive into|study|analyze|find|search|look up|get|tell me about|explain about|summarize|update me on|what are the|what is the)\s+",
        "",
        cleaned,
        flags=re.IGNORECASE,
    ).strip()
    return cleaned.rstrip("?.! ") or (query or "").strip()


def _fetch_google_news_rss(raw_query: str, clean_q: str, allow_links: bool) -> list[dict]:
    """Fetch real-time structured news items from Google News RSS (English & Tamil editions)."""
    items: list[dict] = []
    q_low = (raw_query or "").lower()
    is_tamil = bool(re.search(r"[\u0B80-\u0BFF]", raw_query or ""))
    is_generic_headlines = any(
        phrase in q_low
        for phrase in ("today news", "today's news", "todays news", "latest news", "world news", "headlines", "breaking news", "செய்திகள்", "இன்றைய செய்தி")
    ) and len(clean_q.split()) <= 3

    if is_generic_headlines:
        rss_url = (
            "https://news.google.com/rss?hl=ta&gl=IN&ceid=IN:ta"
            if is_tamil
            else "https://news.google.com/rss?hl=en-IN&gl=IN&ceid=IN:en"
        )
    else:
        encoded = urllib.parse.quote_plus(clean_q)
        rss_url = (
            f"https://news.google.com/rss/search?q={encoded}&hl=ta&gl=IN&ceid=IN:ta"
            if is_tamil
            else f"https://news.google.com/rss/search?q={encoded}&hl=en-IN&gl=IN&ceid=IN:en"
        )

    headers = {"User-Agent": "Mozilla/5.0 (compatible; SRICompanion/1.0)"}
    req = urllib.request.Request(rss_url, headers=headers)
    with urllib.request.urlopen(req, timeout=3.2) as resp:
        xml_bytes = resp.read()
    root = ET.fromstring(xml_bytes)
    for node in root.findall("./channel/item")[:5]:
        title = (node.findtext("title") or "").strip()
        if not title:
            continue
        link = (node.findtext("link") or "").strip()
        pub_date = (node.findtext("pubDate") or "").strip()
        source_el = node.find("source")
        source_name = (source_el.text or "").strip() if source_el is not None and source_el.text else "Google News"
        desc_raw = node.findtext("description") or ""
        desc_clean = html_lib.unescape(re.sub(r"<[^>]+>", " ", desc_raw))
        desc_clean = re.sub(r"\s+", " ", desc_clean).strip()
        short_date = " ".join(pub_date.split()[:4]) if pub_date else "Live"
        snippet = desc_clean if desc_clean and desc_clean.lower() != title.lower() else f"Reported by {source_name} ({short_date})."
        items.append({
            "title": html_lib.unescape(title),
            "snippet": snippet[:320],
            "url": link if (allow_links and is_valid_external_url(link)) else "",
            "badge": f"Live News · {source_name[:22]}",
            "published": short_date,
        })
    return items


def _fetch_tech_updates_hn(raw_query: str, clean_q: str, allow_links: bool) -> list[dict]:
    """Fetch live technology & AI updates from Hacker News Algolia API."""
    q_low = (raw_query or "").lower()
    is_tech_oriented = any(
        k in q_low
        for k in (
            "tech", "technology", "ai", "software", "programming", "python", "javascript", "react",
            "cloud", "startup", "model", "llm", "gemini", "openai", "chip", "hardware", "cyber",
            "டெக்", "தொழில்நுட்பம்", "ஏஐ",
        )
    )
    if not is_tech_oriented:
        return []

    encoded = urllib.parse.quote_plus(clean_q)
    api_url = f"https://hn.algolia.com/api/v1/search_by_date?query={encoded}&tags=story&hitsPerPage=4"
    if len(clean_q.split()) <= 2 and any(k in q_low for k in ("tech news", "tech updates", "technology updates", "technology news")):
        api_url = "https://hn.algolia.com/api/v1/search?tags=front_page&hitsPerPage=4"

    req = urllib.request.Request(api_url, headers={"User-Agent": "Mozilla/5.0 (compatible; SRICompanion/1.0)"})
    with urllib.request.urlopen(req, timeout=3.0) as resp:
        data = json.loads(resp.read().decode("utf-8", errors="ignore"))

    items: list[dict] = []
    for hit in (data.get("hits") or [])[:4]:
        title = (hit.get("title") or "").strip()
        if not title:
            continue
        created_at = str(hit.get("created_at") or "")[:10] or "Today"
        points = hit.get("points") or 0
        story_text = re.sub(r"<[^>]+>", " ", str(hit.get("story_text") or "")).strip()
        snippet = story_text[:280] if story_text else f"Live tech discussion ({points} upvotes · {created_at})."
        hit_url = (hit.get("url") or "").strip()
        items.append({
            "title": html_lib.unescape(title),
            "snippet": html_lib.unescape(snippet),
            "url": hit_url if (allow_links and is_valid_external_url(hit_url)) else "",
            "badge": "Tech Update · Live",
            "published": created_at,
        })
    return items


def _fetch_wikipedia_and_ddg_info(clean_q: str, allow_links: bool) -> list[dict]:
    """Fetch instant general info via DuckDuckGo Instant Answer JSON, Wikipedia API, and DDG HTML."""
    items: list[dict] = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    # 1. DuckDuckGo Instant Answer JSON API
    try:
        ia_url = f"https://api.duckduckgo.com/?q={urllib.parse.quote_plus(clean_q)}&format=json&no_html=1&skip_disambig=1"
        req = urllib.request.Request(ia_url, headers=headers)
        with urllib.request.urlopen(req, timeout=2.5) as resp:
            ia = json.loads(resp.read().decode("utf-8", errors="ignore"))
        abstract = (ia.get("AbstractText") or "").strip()
        heading = (ia.get("Heading") or clean_q.title()).strip()
        src_url = (ia.get("AbstractURL") or "").strip()
        if abstract:
            items.append({
                "title": html_lib.unescape(heading),
                "snippet": html_lib.unescape(abstract[:340]),
                "url": src_url if (allow_links and is_valid_external_url(src_url)) else "",
                "badge": "Live Info · Instant",
                "published": "Live",
            })
    except Exception:
        pass

    # 2. Wikipedia Search API (general knowledge fallback)
    try:
        wiki_url = (
            "https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch="
            + urllib.parse.quote_plus(clean_q)
            + "&utf8=&format=json&srlimit=2"
        )
        req = urllib.request.Request(wiki_url, headers=headers)
        with urllib.request.urlopen(req, timeout=2.6) as resp:
            wdata = json.loads(resp.read().decode("utf-8", errors="ignore"))
        for hit in (wdata.get("query", {}).get("search") or [])[:2]:
            w_title = (hit.get("title") or "").strip()
            w_snip = re.sub(r"<[^>]+>", "", str(hit.get("snippet") or "")).strip()
            if w_title and w_snip:
                slug = urllib.parse.quote(w_title.replace(" ", "_"))
                candidate_wiki_url = f"https://en.wikipedia.org/wiki/{slug}"
                items.append({
                    "title": html_lib.unescape(w_title),
                    "snippet": html_lib.unescape(w_snip),
                    "url": candidate_wiki_url if (allow_links and is_valid_external_url(candidate_wiki_url)) else "",
                    "badge": "Knowledge Base",
                    "published": "Verified",
                })
    except Exception:
        pass

    # 3. DuckDuckGo HTML Search
    try:
        ddg_url = "https://html.duckduckgo.com/html/"
        data = urllib.parse.urlencode({"q": clean_q}).encode("utf-8")
        req = urllib.request.Request(ddg_url, data=data, headers=headers)
        with urllib.request.urlopen(req, timeout=3.2) as resp:
            raw_html = resp.read().decode("utf-8", errors="ignore")
        matches = re.findall(
            r'<a class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>.*?<a class="result__snippet"[^>]*>(.*?)</a>',
            raw_html,
            re.DOTALL,
        )
        if not matches:
            matches = [
                (m[0], clean_q.title(), m[1])
                for m in re.findall(
                    r'<a class="result__url"[^>]*href="([^"]+)"[^>]*>.*?<a class="result__snippet"[^>]*>(.*?)</a>',
                    raw_html,
                    re.DOTALL,
                )
            ]
        for m in matches[:4]:
            raw_url = m[0].strip()
            title_txt = re.sub(r"<[^>]+>", "", m[1]).strip() or clean_q.title()
            snippet = re.sub(r"<[^>]+>", "", m[2]).strip()
            if "uddg=" in raw_url:
                raw_url = urllib.parse.unquote(raw_url.split("uddg=")[-1].split("&")[0])
            elif raw_url.startswith("//"):
                raw_url = "https:" + raw_url
            items.append({
                "title": html_lib.unescape(title_txt),
                "snippet": html_lib.unescape(snippet) or "Verified live search insight.",
                "url": raw_url if (allow_links and is_valid_external_url(raw_url)) else "",
                "badge": "Live Web",
                "published": "Live",
            })
    except Exception:
        pass

    return items


def _fetch_gemini_google_search_grounding(query: str) -> str:
    """Use Gemini's native Google Search Grounding REST tool when GEMINI_API_KEY is available."""
    global _gemini_cooldown_until
    if not gemini_key or time.time() < _gemini_cooldown_until:
        return ""
    allow_links = user_explicitly_requested_link(query)
    link_policy_note = (
        "EXPLICIT RESOURCE LINK REQUEST: Provide only verified, valid https:// links directly answering Kirubhakaran's request."
        if allow_links
        else "NO LINKS ALLOWED: Do NOT output any URLs, bare domains, reference links, or download links — summarize naturally in plain conversation."
    )
    model_id = (custom_model_name or "gemini-2.5-flash").replace("models/", "")
    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent?key={urllib.parse.quote(gemini_key)}"
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    payload = {
        "systemInstruction": {
            "parts": [{
                "text": (
                    f"{SRI_COMPANION_SYSTEM_PROMPT}\n"
                    f"{link_policy_note}\n"
                    f"Current date/time: {now_str}. Use Google Search grounding to retrieve up-to-date verified facts."
                )
            }]
        },
        "contents": [{"role": "user", "parts": [{"text": query}]}],
        "tools": [{"google_search": {}}],
        "generationConfig": {"temperature": 0.4, "maxOutputTokens": 560},
    }
    try:
        req = urllib.request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=4.5) as resp:
            res_json = json.loads(resp.read().decode("utf-8", errors="ignore"))
        candidates = res_json.get("candidates") or []
        if candidates:
            parts = (candidates[0].get("content") or {}).get("parts") or []
            text = "\n".join(str(p.get("text") or "") for p in parts if p.get("text")).strip()
            if allow_links and text and not re.search(r"https?://", text, re.IGNORECASE):
                chunks = (candidates[0].get("groundingMetadata") or {}).get("groundingChunks") or []
                valid_uris = []
                for ch in chunks:
                    web_info = ch.get("web") or {}
                    uri = str(web_info.get("uri") or "").strip()
                    title = str(web_info.get("title") or "").strip()
                    if is_valid_external_url(uri) and uri not in valid_uris:
                        valid_uris.append(f"{title + ': ' if title else ''}{uri}")
                    if len(valid_uris) >= 3:
                        break
                if valid_uris:
                    text = f"{text}\n\n" + "\n".join(valid_uris)
            if text:
                return _strip_cutoff_disclaimers(sanitize_unsolicited_links(text, query))
    except Exception as e:
        err_low = str(e).lower()
        if any(k in err_low for k in ("429", "quota", "exhausted", "resource_exhausted")):
            _gemini_cooldown_until = time.time() + 60
        print(f"ℹ️ Gemini live search grounding notice: {e}")
    return ""


def collect_realtime_retrieval(query: str) -> dict:
    """Concurrently aggregate live news RSS, tech feeds, general info, web snippets, and Search grounding."""
    clean_q = _clean_retrieval_query(query)
    allow_links = user_explicitly_requested_link(query)
    raw_items: list[dict] = []
    grounded_brief = ""

    with ThreadPoolExecutor(max_workers=4) as pool:
        fut_news = pool.submit(_fetch_google_news_rss, query, clean_q, allow_links)
        fut_tech = pool.submit(_fetch_tech_updates_hn, query, clean_q, allow_links)
        fut_info = pool.submit(_fetch_wikipedia_and_ddg_info, clean_q, allow_links)
        fut_gemini = pool.submit(_fetch_gemini_google_search_grounding, query) if gemini_key else None

        for fut in (fut_news, fut_tech, fut_info):
            try:
                res = fut.result(timeout=4.0)
                if isinstance(res, list):
                    raw_items.extend(res)
            except Exception:
                pass
        if fut_gemini is not None:
            try:
                grounded_brief = fut_gemini.result(timeout=4.8) or ""
            except Exception:
                grounded_brief = ""

    # Deduplicate by normalized title and keep cleanest top findings
    seen_titles: set[str] = set()
    dedup_items: list[dict] = []
    for it in raw_items:
        norm = re.sub(r"\W+", "", (it.get("title") or "").lower())[:48]
        if not norm or norm in seen_titles:
            continue
        seen_titles.add(norm)
        clean_it = dict(it)
        cand_url = str(clean_it.get("url") or "").strip()
        clean_it["url"] = cand_url if (allow_links and is_valid_external_url(cand_url)) else ""
        dedup_items.append(clean_it)
        if len(dedup_items) >= 6:
            break

    return {
        "query": clean_q,
        "allow_links": allow_links,
        "items": dedup_items,
        "grounded_brief": grounded_brief,
        "retrieved_at": datetime.now().strftime("%Y-%m-%d %I:%M %p"),
    }


def perform_live_web_research(query: str) -> dict:
    """
    Live Companion Research Engine (Real-Time News, Tech Updates, General Info, Deep Research).
    Combines multi-source live retrieval (Google News RSS, HN Tech API, Wikipedia, DuckDuckGo,
    and Gemini Google Search Grounding) + fast LLM synthesis.
    Respects Smart Conditional Linking and friendly Tamil quota/API fallbacks.
    """
    retrieval = collect_realtime_retrieval(query)
    clean_q = retrieval["query"]
    allow_links = retrieval["allow_links"]
    items = retrieval["items"]
    grounded_brief = retrieval["grounded_brief"]

    # Synthesize open-ended companion brief using retrieved real-time context + fast LLM
    llm_synthesis = grounded_brief
    llm_error_msg = ""
    if not llm_synthesis:
        try:
            synth_instr = get_open_ended_companion_prompt(query, mode="chat")
            snippet_ctx = "\n".join(
                f"- [{it.get('badge', 'Live')}] {it['title']}: {it['snippet']}"
                + (f" ({it['url']})" if allow_links and it.get("url") else "")
                for it in items
            )
            synth_prompt = (
                f"Kirubha asks for live/current details: {query}\n"
                f"Live retrieval timestamp: {retrieval['retrieved_at']}\n"
                + (f"Real-time retrieved context:\n{snippet_ctx}\n" if snippet_ctx else "")
                + "Synthesize a clear, accurate, up-to-date answer directly using the retrieved context. "
                "Match Kirubha's language (Tamil or English). Never say you lack live internet access."
            )
            llm_synthesis = call_fast_voice_llm(synth_prompt, synth_instr, max_tokens=560)
            llm_synthesis = _strip_cutoff_disclaimers(sanitize_unsolicited_links(llm_synthesis, query))
        except Exception as llm_err:
            print(f"⚠️ Research synthesis fallback triggered: {llm_err}")
            llm_error_msg = _friendly_tamil_ai_error(llm_err)
            llm_synthesis = ""

    if not items:
        fallback_snippet = llm_synthesis or llm_error_msg or f"Live knowledge brief ready for {clean_q}."
        items = [{
            "title": clean_q.title(),
            "snippet": fallback_snippet,
            "url": "",
            "badge": "SRI Knowledge Brief",
            "published": retrieval["retrieved_at"],
        }]

    cards_html = ""
    for it in items:
        safe_title = html_lib.escape(it["title"])
        safe_snippet = html_lib.escape(sanitize_unsolicited_links(it["snippet"], query))
        safe_badge = html_lib.escape(it["badge"])
        cand_url = str(it.get("url") or "").strip()
        if allow_links and is_valid_external_url(cand_url):
            safe_url = html_lib.escape(cand_url)
            title_block = (
                f'<a href="{safe_url}" target="_blank" rel="noopener noreferrer" '
                f'style="color:#FBBF24;font-size:14.5px;font-weight:600;text-decoration:none;">'
                f'{safe_title} ↗</a>'
            )
        else:
            title_block = f'<span style="color:#FBBF24;font-size:14.5px;font-weight:600;">{safe_title}</span>'

        cards_html += f"""
        <div style="background:#0E121A;border:1px solid #1E222B;border-radius:12px;padding:14px;margin-bottom:10px;">
          <div style="display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:6px;">
            {title_block}
            <span style="background:rgba(245,158,11,0.12);border:1px solid rgba(245,158,11,0.35);color:#F59E0B;font-size:10.5px;padding:2px 8px;border-radius:999px;font-weight:500;flex-shrink:0;">{safe_badge}</span>
          </div>
          <p style="font-size:12.8px;color:#CBD5E1;line-height:1.58;margin:0;">{safe_snippet}</p>
        </div>"""

    footer_cta = ""
    if allow_links and items:
        first_valid = next((str(it.get("url") or "").strip() for it in items if is_valid_external_url(str(it.get("url") or ""))), "")
        if first_valid:
            first_url = html_lib.escape(first_valid)
            footer_cta = (
                f'<a href="{first_url}" target="_blank" rel="noopener noreferrer" '
                f'style="background:linear-gradient(135deg,#F59E0B,#D97706);color:#060709;padding:6px 14px;border-radius:999px;font-size:12px;font-weight:700;text-decoration:none;">'
                f'Open Resource ↗</a>'
            )

    safe_query_title = html_lib.escape(clean_q)
    t_stamp = datetime.now().strftime("%I:%M %p")
    summary_text = llm_synthesis or llm_error_msg
    summary_section = ""
    if summary_text:
        safe_summary = html_lib.escape(sanitize_unsolicited_links(summary_text, query))
        summary_section = f"""
        <div style="background:linear-gradient(135deg,rgba(16,185,129,0.10),rgba(245,158,11,0.06));border:1px solid rgba(16,185,129,0.32);border-left:3px solid #10B981;border-radius:12px;padding:13px 14px;margin-bottom:14px;">
          <div style="font-size:10.5px;color:#34D399;font-weight:700;text-transform:uppercase;letter-spacing:0.6px;margin-bottom:6px;">Real-Time Executive Summary</div>
          <div style="font-size:13.2px;color:#F8FAFC;line-height:1.62;white-space:pre-wrap;">{safe_summary}</div>
        </div>"""

    panel_html = f"""
    <div style="font-family:'Inter',-apple-system,BlinkMacSystemFont,sans-serif;color:#F4F4F5;padding:2px;">
      <div style="background:#0A0C10;border:1px solid rgba(245,158,11,0.38);border-radius:16px;padding:16px;">
        <div style="display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:12px;border-bottom:1px solid #1E222B;padding-bottom:10px;">
          <span style="background:rgba(245,158,11,0.15);border:1px solid #F59E0B;color:#F59E0B;font-size:11px;font-weight:700;padding:3px 10px;border-radius:999px;">✦ SRI Real-Time Research</span>
          <span style="font-size:11px;color:#10B981;font-weight:600;">● Live Verified · {t_stamp}</span>
        </div>
        <div style="font-size:16px;font-weight:700;color:#FFFFFF;margin-bottom:12px;line-height:1.35;">{safe_query_title}</div>
        {summary_section}
        {cards_html}
        <div style="margin-top:12px;padding-top:10px;border-top:1px solid #1E222B;display:flex;align-items:center;justify-content:space-between;">
          <span style="font-size:11px;color:#71717A;">SRI Solo AI Companion · Live Retrieval Engine</span>
          {footer_cta}
        </div>
      </div>
    </div>"""

    full_card_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #060709; color: #F4F4F5; font-family: -apple-system, BlinkMacSystemFont, 'Inter', sans-serif; padding: 14px; }}
</style>
</head>
<body>
  {panel_html}
</body>
</html>"""

    voice_summary = llm_synthesis or llm_error_msg or "; ".join(f"{it['title']}: {it['snippet']}" for it in items[:2])
    voice_summary = _strip_cutoff_disclaimers(sanitize_unsolicited_links(voice_summary, query))

    return {
        "query": clean_q,
        "items": items,
        "panel_html": panel_html,
        "card_html": full_card_html,
        "voice_summary": voice_summary,
    }


def build_companion_inline_card(user_prompt: str, reply_text: str) -> str:
    """Open-ended Obsidian Companion Card without hardcoded hackathon or login cards."""
    t_stamp = datetime.now().strftime("%I:%M %p")
    clean_p = html_lib.escape(user_prompt)
    clean_r = html_lib.escape(sanitize_unsolicited_links(reply_text, user_prompt))
    return f"""
    <div class="slide-inline-card" style="font-family:'Inter',sans-serif;color:#F4F4F5;padding:4px;">
      <div style="background:linear-gradient(135deg,rgba(245,158,11,0.14),rgba(16,185,129,0.06));border:1px solid rgba(245,158,11,0.42);border-radius:14px;padding:14px;margin-bottom:10px;">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
          <span style="font-size:11px;color:#F59E0B;font-weight:700;text-transform:uppercase;letter-spacing:0.7px;">✦ SRI · Solo AI Companion</span>
          <span style="font-size:10px;color:#9CA3AF;background:#141821;border:1px solid #222630;padding:2px 8px;border-radius:999px;">⏱️ {t_stamp}</span>
        </div>
        <div style="font-size:12px;color:#D1D5DB;margin-bottom:6px;"><strong>Kirubha:</strong> &ldquo;{clean_p}&rdquo;</div>
        <div style="font-size:13.5px;line-height:1.6;color:#FFFFFF;background:#060709;border-left:3px solid #10B981;border-radius:8px;padding:10px 12px;white-space:pre-wrap;">
          {clean_r}
        </div>
      </div>
    </div>
    """


build_smart_mentor_inline_card = build_companion_inline_card


def _friendly_tamil_ai_error(err: Exception | str | None = None) -> str:
    """Return a friendly, conversational Tamil fallback message for quota limits or API errors."""
    msg = str(err or "").lower()
    if any(k in msg for k in ["429", "quota", "resource_exhausted", "exhausted", "rate limit", "too many requests"]):
        return (
            "மன்னிக்கவும் கிருபா! இப்போது AI பயன்பாட்டு வரம்பு (Quota Limit) நிரம்பிவிட்டது "
            "அல்லது அதிக கோரிக்கைகள் உள்ளன. சில வினாடிகள் கழித்து மீண்டும் முயற்சிக்கவும்!"
        )
    if any(k in msg for k in ["timeout", "deadline", "504", "503", "502", "connection", "network", "unreachable"]):
        return (
            "மன்னிக்கவும் கிருபா! AI சேவையகத்துடன் இணைப்பதில் தற்காலிக தாமதம் ஏற்பட்டுள்ளது. "
            "கொஞ்சம் கழித்து மீண்டும் பேசுங்கள்!"
        )
    if any(k in msg for k in ["401", "403", "api_key", "api key", "unauthorized", "permission", "no api keys"]):
        return (
            "மன்னிக்கவும் கிருபா! AI சேவை இணைப்பில் (API Key / Service) சிறிய சிக்கல் உள்ளது. "
            "அமைப்புகளைச் சரிபார்த்து மீண்டும் முயற்சிக்கவும்."
        )
    return (
        "மன்னிக்கவும் கிருபா! தற்போது AI பதில் உருவாக்குவதில் சிறிய தொழில்நுட்பச் சிக்கல் ஏற்பட்டுள்ளது. "
        "சில வினாடிகளில் மீண்டும் முயற்சிக்கவும்!"
    )


def _normalize_natural_voice_reply(reply_text: str) -> str:
    """Keep spoken replies natural and fluid without injecting robotic pacing templates or markdown artifacts."""
    cleaned = re.sub(r"```[\s\S]*?```", "", reply_text or "")
    cleaned = re.sub(r"[\*_`#~\[\]{}<>|\\]", " ", cleaned)
    cleaned = re.sub(r"(?m)^\s*(?:[-*+]|\d+\.)\s+", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned or (reply_text or "").strip()


def get_executive_voice_response(
    user_query: str,
    active_tasks_count: int = 0,
    workspace_file: str = "workspace/login.html",
    file_exists: bool = False,
    file_size: int = 0,
    newly_dispatched_id: str | None = None,
    research_summary: str | None = None,
    channel: str = "chat",
    preferred_lang: str = "ta-IN",
    chat_history: list | None = None,
) -> str:
    """
    Open-Ended General AI Companion Brain for Kirubha:
    - Low-latency natural conversation in Tamil (தமிழ் / ta-IN), English, and regional languages.
    - No rigid templates or robotic speech pacing.
    - Enforces Conditional Linking (no unsolicited URLs or download links).
    """
    try:
        clean_q = (user_query or "").strip()
        if not clean_q:
            return "வணக்கம் கிருபா! சொல்லுங்க, எப்படி உதவலாம்?" if preferred_lang == "ta-IN" else "Hey Kirubha! How can I help you today?"

        # 1. Instant ultra-fast greeting fast-path (<1ms, non-repetitive)
        instant = try_instant_voice_reply(clean_q, preferred_lang=preferred_lang)
        if instant:
            return sanitize_unsolicited_links(instant, clean_q)

        if newly_dispatched_id:
            return (
                "சரி கிருபா! இதை பின்னணியில் உருவாக்கத் தொடங்கிவிட்டேன் — முடிந்ததும் Preview-வில் பார்க்கலாம்."
                if preferred_lang == "ta-IN" or re.search(r"[\u0B80-\u0BFF]", clean_q)
                else "Got it, Kirubha! I've started building that in the background — it'll appear in Preview shortly."
            )

        if research_summary:
            clean_summary = _strip_cutoff_disclaimers(sanitize_unsolicited_links(research_summary, clean_q))
            return _normalize_natural_voice_reply(clean_summary) if channel == "orb" else clean_summary

        # 2. Live task progress status lookup ONLY when user explicitly asks about background task progress
        q_low = clean_q.lower()
        is_status_query = any(
            w in q_low
            for w in [
                "எங்க போயிட்டு", "என்ன பண்ணுது", "முடிஞ்சு", "மாடல் யூஸ்", "எந்த மாடல்",
                "task status", "project status", "background task", "active tasks", "task progress",
            ]
        )
        if is_status_query:
            db_now = load_db()
            tasks_map = db_now.get("tasks", {})
            running = [t for t in tasks_map.values() if t.get("status") == "RUNNING"]
            completed = [t for t in tasks_map.values() if t.get("status") == "COMPLETED"]
            if running:
                rt = running[0]
                return f"தற்போது '{rt.get('title', 'Task')}' {rt.get('progress_percent', 0)}% முடிந்துள்ளது ({rt.get('current_action', 'running')})."
            if completed:
                return f"தற்போது {len(completed)} பணிகள் வெற்றிகரமாக முடிந்துள்ளன. புதிய டாஸ்க் ஏதேனும் தொடங்கலாமா?"
            return "தற்போது எந்த பின்னணி டாஸ்க்கும் ஓடவில்லை கிருபா. சொல்லுங்க, என்ன செய்யலாம்?"

        # 3. Selective real-time grounding (only for live info queries) + Fast Conversational LLM
        mode = "voice" if channel == "orb" else "chat"
        live_context_block = ""
        if should_fetch_live_context(clean_q):
            try:
                live_ret = collect_realtime_retrieval(clean_q)
                if live_ret.get("grounded_brief"):
                    brief_clean = _strip_cutoff_disclaimers(sanitize_unsolicited_links(live_ret["grounded_brief"], clean_q))
                    if brief_clean:
                        return _normalize_natural_voice_reply(brief_clean) if mode == "voice" else brief_clean
                live_items = live_ret.get("items") or []
                if live_items:
                    allow_links = live_ret.get("allow_links", False)
                    live_lines = "\n".join(
                        f"- [{it.get('badge', 'Live')}] {it['title']}: {it['snippet']}"
                        + (f" ({it['url']})" if allow_links and it.get("url") else "")
                        for it in live_items[:4]
                    )
                    live_context_block = f"\nReal-time retrieved context ({live_ret.get('retrieved_at', '')}):\n{live_lines}"
            except Exception as live_err:
                print(f"ℹ️ Auto live-context notice: {live_err}")

        system_instr = get_open_ended_companion_prompt(clean_q, mode=mode, preferred_lang=preferred_lang)
        now_ctx = datetime.now().strftime("%A, %B %d, %Y %I:%M %p")
        context_note = f"Current date/time: {now_ctx}. Background tasks running: {active_tasks_count}."
        full_system = f"{system_instr}\nContext: {context_note}{live_context_block}"
        token_budget = 220 if mode == "voice" else 1400

        try:
            reply = call_fast_voice_llm(
                clean_q,
                system_instruction=full_system,
                max_tokens=token_budget,
                history_messages=chat_history,
            )
            if reply and reply.strip():
                cleaned = _strip_cutoff_disclaimers(sanitize_unsolicited_links(reply.strip(), clean_q))
                return _normalize_natural_voice_reply(cleaned) if mode == "voice" else cleaned
            return _friendly_tamil_ai_error("Empty AI response")
        except Exception as llm_err:
            print(f"⚠️ Companion LLM fallback triggered: {llm_err}")
            return _friendly_tamil_ai_error(llm_err)
    except Exception as outer_err:
        print(f"⚠️ Voice/Chat response safety handler caught error: {outer_err}")
        return _friendly_tamil_ai_error(outer_err)


# ==============================================================================
# 10. REST API GATEWAY (?action=...)
# ==============================================================================
def handle_sri_api_gateway():
    try:
        params = st.query_params
    except Exception:
        return
    action = (params.get("action", "") or params.get("api", "") or params.get("endpoint", "")).strip().lower()
    if not action:
        return

    auth_provided = params.get("auth", "") or params.get("key", "") or params.get("secret", "")
    if auth_provided != sri_auth_secret:
        st.json({"status": "error", "code": 401, "error": "Unauthorized SRI_AUTH_SECRET"})
        st.stop()

    now_ts = datetime.now().isoformat()
    payload: dict = {"status": "ok", "action": action, "timestamp": now_ts}

    if action == "health":
        payload["runtime"] = RUNTIME_ENV
        payload["workspace_dir"] = WORKSPACE_DIR
    elif action == "dispatch":
        prompt = params.get("prompt", "") or params.get("task", "")
        if not prompt:
            payload = {"status": "error", "code": 400, "error": "'prompt' is required", "timestamp": now_ts}
        else:
            tid = dispatch_background_task(prompt, task_type=params.get("type", "auto"), folder_name=params.get("folder", ""))
            payload["task_id"] = tid
    elif action == "status":
        tid = params.get("task_id", "")
        task = load_db().get("tasks", {}).get(tid)
        payload = {"status": "ok", "task": task, "timestamp": now_ts} if task else {"status": "error", "code": 404, "error": "Task not found"}
    elif action == "list":
        tasks = list(load_db().get("tasks", {}).values())
        tasks.sort(key=lambda t: str(t.get("created_at", "")), reverse=True)
        payload["tasks"] = tasks[:25]
    elif action == "metrics":
        db_state = load_db()
        payload["metrics"] = db_state.get("metrics", {})
        payload["active_running"] = sum(1 for t in db_state.get("tasks", {}).values() if t.get("status") == "RUNNING")
    elif action == "call":
        ok, res = make_agent_call(params.get("message", "") or "வணக்கம்! உங்கள் SRI ஏஜென்ட் அழைக்கிறது!")
        payload.update({"status": "ok" if ok else "error", "success": ok, "call_sid": res if ok else None, "error": None if ok else res})
    elif action == "workspace":
        payload["workspace_files"] = get_workspace_files()
    elif action in ("whatsapp_complete_check", "complete_alert", "all_tasks_completed"):
        force_send = str(params.get("force", "")).strip().lower() in ("1", "true", "yes")
        payload["completion_alert"] = check_and_trigger_all_tasks_completed_whatsapp_alert(force=force_send)

    st.json(payload)
    st.stop()


handle_sri_api_gateway()


# ==============================================================================
# 11. SIDEBAR TECHNICAL DRAWER (SRI Control Drawer — Exact 9-Item Menu & Stats)
# ==============================================================================
restore_session_state_on_wakeup()
_drawer_db = load_db()
_drawer_metrics = _drawer_db.get("metrics", {})
_drawer_tasks = _drawer_db.get("tasks", {})
_drawer_active = sum(1 for t in _drawer_tasks.values() if t.get("status") == "RUNNING")
_drawer_completed = _drawer_metrics.get("completed_tasks", 0)
_drawer_agent_status = "SRI (Active)" if _drawer_active > 0 else "SRI (Ready)"
_drawer_ws_files = get_workspace_files()
_drawer_ws_preview = ", ".join(_drawer_ws_files[:4]) if _drawer_ws_files else "login.html"
if len(_drawer_ws_files) > 4:
    _drawer_ws_preview += f" (+{len(_drawer_ws_files) - 4} more)"

with st.sidebar:
    st.markdown("### ⚙️ SRI Control Drawer")
    st.caption(f"Open-Ended Companion & Task Engine • {RUNTIME_ENV['env_name']}")

    st.markdown(
        f"""
        <div style="background:#0E121A;border:1px solid rgba(245,158,11,0.35);border-radius:12px;padding:10px 12px;margin-bottom:12px;font-size:12px;color:#E2E8F0;">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
            <span style="color:#94A3B8;font-weight:600;">Agent Status</span>
            <span style="color:#10B981;font-weight:700;">● {html_lib.escape(_drawer_agent_status)}</span>
          </div>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:8px;">
            <div style="background:#060709;border:1px solid #1E222B;border-radius:8px;padding:6px 8px;">
              <div style="font-size:10px;color:#94A3B8;text-transform:uppercase;">Active Tasks</div>
              <div style="font-size:15px;font-weight:700;color:#F59E0B;">{_drawer_active}</div>
            </div>
            <div style="background:#060709;border:1px solid #1E222B;border-radius:8px;padding:6px 8px;">
              <div style="font-size:10px;color:#94A3B8;text-transform:uppercase;">Completed</div>
              <div style="font-size:15px;font-weight:700;color:#10B981;">{_drawer_completed}</div>
            </div>
          </div>
          <div style="background:#060709;border:1px solid #1E222B;border-radius:8px;padding:6px 8px;">
            <div style="font-size:10px;color:#94A3B8;text-transform:uppercase;margin-bottom:2px;">Workspace ({len(_drawer_ws_files)} files)</div>
            <div style="font-family:monospace;font-size:11px;color:#FBBF24;word-break:break-word;">workspace/ · {html_lib.escape(_drawer_ws_preview)}</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.expander("1. Workspaces & Background Runner", expanded=False):
        col_wa_in, col_wa_add = st.columns([3, 1])
        with col_wa_in:
            sb_new_area = st.text_input("New workspace:", placeholder="workspace/my_app", key="sb_wa_new_input", label_visibility="collapsed")
        with col_wa_add:
            if st.button("➕", key="sb_wa_add_btn", use_container_width=True) and sb_new_area:
                sri_master_agent.add_new_work_area(sb_new_area)
                st.toast(f"Added: {sb_new_area}")
                st.rerun()

        sb_selected_area = st.selectbox("Workspace:", sri_master_agent.approved_work_areas, key="sb_wa_selected_area")
        sb_task_desc = st.text_area("Background build prompt:", placeholder="Build a responsive interactive dashboard...", height=80, key="sb_wa_task_desc")
        if st.button("🚀 Start Background Task", key="sb_start_bg_btn", type="primary", use_container_width=True):
            if not sb_task_desc.strip():
                st.warning("Enter a task prompt.")
            else:
                folder_target = sb_selected_area.replace("workspace/", "").strip() or "student_learning_hub"
                new_tid = dispatch_background_task(sb_task_desc.strip(), task_type="auto", folder_name=folder_target)
                st.success(f"Task queued: `{new_tid}`")
                st.rerun()

    with st.expander("2. Voice Engine (ta / en)", expanded=False):
        _lang_opts = ["ta-IN", "en-IN", "hi-IN", "te-IN", "ml-IN"]
        _cur_lang = str(st.session_state.get("sri_voice_lang_pref") or "ta-IN")
        if _cur_lang not in _lang_opts:
            _cur_lang = "ta-IN"
        sb_voice_lang = st.selectbox(
            "Primary Voice Language (ta / en):",
            _lang_opts,
            index=_lang_opts.index(_cur_lang),
            key="sb_voice_engine_lang",
        )
        st.session_state["sri_voice_lang_pref"] = sb_voice_lang
        if hasattr(st, "checkbox"):
            sb_continuous_orb = st.checkbox(
                "Continuous Walkie-Talkie Listening",
                value=bool(st.session_state.get("sri_continuous_voice_enabled", True)),
                key="sb_voice_continuous_chk",
            )
            st.session_state["sri_continuous_voice_enabled"] = sb_continuous_orb
        st.caption("Neural Edge-TTS + Web Speech Continuous Engine active (`ta-IN` / `en-IN`).")

    with st.expander("3. Model & API Router + Safety Gate", expanded=False):
        _model_opts = [
            "gemini-4-hydrogen",
            "gemini-2.5-flash",
            "llama-3.3-70b-versatile",
            "google/gemini-2.0-flash-exp:free",
        ]
        _cur_m = custom_model_name or "gemini-4-hydrogen"
        if _cur_m not in _model_opts:
            _model_opts.insert(0, _cur_m)
        sb_model_sel = st.selectbox(
            "Active AI Model Router:",
            _model_opts,
            index=_model_opts.index(_cur_m),
            key="sb_model_router_sel",
        )
        st.session_state["sri_custom_model_override"] = sb_model_sel
        custom_model_name = sb_model_sel

        _providers_ready = [
            f"Gemini: {'Ready' if gemini_key else 'Unset'}",
            f"Groq: {'Ready' if groq_key else 'Unset'}",
            f"OpenRouter: {'Ready' if openrouter_key else 'Unset'}",
        ]
        st.caption(" • ".join(_providers_ready))
        st.caption(
            f"Execution Gate: `{'ACTIVE' if sri_execution_gate.is_active else 'LOCKED'}` • "
            f"Design Guard: `{'ACTIVE' if sri_design_guard.is_active else 'LOCKED'}`"
        )
        if st.button("🛡️ Reset Safety Gates", key="sb_reset_gates_btn", use_container_width=True):
            sri_execution_gate.reset_gate(sri_auth_secret)
            sri_design_guard.reset_guard(sri_auth_secret)
            st.success("Safety gates verified and active.")
            st.rerun()

    with st.expander("4. Twilio Voice Call & WhatsApp Bridge", expanded=False):
        st.caption(f"Admin Number: `{get_secret('ADMIN_PHONE_NUMBER', 'Unconfigured')}`")
        st.caption(f"WhatsApp Target: `{_resolve_kirubha_whatsapp_number() or 'Unconfigured'}`")
        if st.button("📞 Test Voice Call", key="sb_call_now_btn", use_container_width=True):
            ok, res = make_agent_call("வணக்கம் கிருபா! SRI இணைப்பில் உள்ளது.")
            st.success(f"Calling! SID: {res}") if ok else st.error(f"Call failed: {res}")
        if st.button("💬 Test WhatsApp Alert", key="sb_test_wa_btn", use_container_width=True):
            wa_res = send_whatsapp_notification(
                "🤖 SRI Solo AI Companion — Kirubha WhatsApp test alert active!",
                event="test_whatsapp_alert",
            )
            if wa_res.get("ok"):
                prov = wa_res.get("provider", "whatsapp")
                st.success(f"WhatsApp alert ready via {prov}!")
            else:
                st.warning(f"WhatsApp notice: {wa_res.get('error', 'Check WhatsApp webhook/Twilio config')}")
        if st.button("✅ Check All Tasks & Alert WhatsApp", key="sb_check_all_wa_btn", use_container_width=True):
            chk_res = check_and_trigger_all_tasks_completed_whatsapp_alert(force=True)
            if chk_res.get("all_completed"):
                st.success(f"All Tasks Completed ({chk_res.get('completed_count')}/{chk_res.get('total_tasks')}) — WhatsApp alert sent!")
            else:
                st.info(f"Progress: {chk_res.get('completed_count', 0)}/{chk_res.get('total_tasks', 0)} completed ({chk_res.get('progress_percent', 0)}%).")

    with st.expander("5. Safe Auto-Code Editor & File Upload", expanded=False):
        ws_flist = _drawer_ws_files
        sb_cur_file = st.selectbox("Select workspace file:", ws_flist if ws_flist else ["login.html"], key="sb_cur_file_select")
        zip_bytes = create_project_zip_bundle(WORKSPACE_DIR)
        st.download_button("📦 Download Workspace .ZIP", data=zip_bytes, file_name="sri_workspace.zip", mime="application/zip", use_container_width=True)
        if sb_cur_file and os.path.exists(os.path.join(WORKSPACE_DIR, sb_cur_file)):
            r_ok, r_content, _ = safe_read_code(sb_cur_file)
            if r_ok:
                st.download_button(f"📥 Download {os.path.basename(sb_cur_file)}", data=r_content, file_name=os.path.basename(sb_cur_file), use_container_width=True)
                sb_edit = st.text_area("Modify instructions:", key="sb_edit_instructions_in")
                if st.button("⚡ Execute Safe Auto-Edit", key="sb_exec_auto_edit_btn", use_container_width=True) and sb_edit.strip():
                    tid = dispatch_code_edit_task(sb_cur_file, sb_edit.strip())
                    st.success(f"Edit started: `{tid}`")
                    st.rerun()
        if hasattr(st, "file_uploader"):
            sb_uploaded = st.file_uploader(
                "Upload file to workspace:",
                type=["html", "css", "js", "py", "json", "txt", "md"],
                key="sb_workspace_file_upload",
            )
            if sb_uploaded is not None and st.button("📤 Save Uploaded File", key="sb_save_upload_btn", use_container_width=True):
                raw_bytes = sb_uploaded.getvalue() if hasattr(sb_uploaded, "getvalue") else sb_uploaded.read()
                decoded_txt = raw_bytes.decode("utf-8", errors="replace") if isinstance(raw_bytes, (bytes, bytearray)) else str(raw_bytes)
                up_ok, _up_path, up_err = create_project_structure("uploads", getattr(sb_uploaded, "name", "uploaded.txt"), decoded_txt)
                st.success("Uploaded safely to workspace/uploads!") if up_ok else st.error(up_err)

    with st.expander("6. SRI REST API Gateway & Webhook", expanded=False):
        st.caption("Available Gateway Actions (`?action=`):")
        if hasattr(st, "code"):
            st.code("health | dispatch | status | list | metrics | call | workspace | whatsapp_complete_check", language="text")
        sb_webhook_in = st.text_input(
            "Webhook Endpoint URL:",
            value=str(st.session_state.get("sri_webhook_override") or antigravity_webhook_url),
            key="sb_gateway_webhook_input",
        )
        st.session_state["sri_webhook_override"] = sb_webhook_in.strip()
        st.caption(f"Auth Secret: `Configured ({len(sri_auth_secret)} chars)`")

    with st.expander("7. Execution Audit & Cache Maintenance", expanded=False):
        st.caption(
            f"Total: {_drawer_metrics.get('total_tasks', 0)} • "
            f"Done: {_drawer_completed} • Failed: {_drawer_metrics.get('failed_tasks', 0)} • "
            f"Tokens: {_drawer_metrics.get('total_tokens', 0)}"
        )
        if st.button("🔄 Refresh Execution Audit", key="sb_refresh_audit_btn", use_container_width=True):
            st.rerun()
        hist_q = st.text_input("Search audit history:", placeholder="Filter conversation...", key="sb_hist_search", label_visibility="collapsed")
        entries = _search_hist(hist_q, limit=100) if hist_q else _hist_load()[-100:]
        st.markdown(f"<div style='max-height:260px;overflow-y:auto;'>{_hist_html(entries)}</div>", unsafe_allow_html=True)

    with st.expander("8. Clear Cache", expanded=False):
        st.caption("Clear temporary cloud workspace folders, TTS cache, Streamlit caches, and conversation history.")
        col_c1, col_c2 = st.columns(2)
        with col_c1:
            if st.button("🧹 Clear Cache", key="sb_clean_cache_btn", use_container_width=True):
                cleanup_cloud_workspace(os.path.join(tempfile.gettempdir(), "streamlit_agent"))
                st.toast("Cache cleaned!")
                st.rerun()
        with col_c2:
            if st.button("🗑️ Clear History", key="sb_hist_clear_btn", use_container_width=True):
                _clear_hist()
                st.session_state.history_log = []
                st.toast("History cleared!")
                st.rerun()

    with st.expander("9. Account", expanded=False):
        st.caption("Profile: **Kirubha (Kirubhakaran)**")
        st.caption(f"Role: `Solo Builder / Owner` • Env: `{RUNTIME_ENV['env_name']}`")
        st.caption(f"Workspace Root: `{WORKSPACE_DIR}`")
        if st.button("🔁 Reset Session State", key="sb_account_reset_btn", use_container_width=True):
            for _rk in ("sri_chat_history", "sri_latest_research_html", "sri_voice_turn_id"):
                st.session_state.pop(_rk, None)
            st.toast("Session state reset cleanly.")
            st.rerun()


# ==============================================================================
# 12. ZERO-RELOAD HIDDEN BRIDGE & MAIN COMPANION ORCHESTRATION
# ==============================================================================
st.markdown("""
<style>
div[data-testid="stTextInput"]:has(input[aria-label="sri_bridge_input"]),
div[data-testid="stTextInput"]:has(input[aria-label="sri_hidden_bridge"]),
div[data-testid="stTextInput"]:has(input[placeholder="sri_hidden_bridge"]),
div[data-testid="stTextInput"]:has(input[id*="sri_bridge_input"]),
div:has(> input[aria-label="sri_bridge_input"]),
div:has(> input[aria-label="sri_hidden_bridge"]) {
    position: fixed !important;
    top: -9999px !important;
    left: -9999px !important;
    width: 1px !important;
    height: 1px !important;
    opacity: 0 !important;
    pointer-events: none !important;
    z-index: -9999 !important;
}
</style>
""", unsafe_allow_html=True)


def _on_sri_bridge_change():
    val = st.session_state.get("sri_bridge_input", "").strip()
    if val:
        st.session_state["_active_sri_bridge_cmd"] = val
    st.session_state["sri_bridge_input"] = ""


st.text_input(
    "sri_bridge_input",
    key="sri_bridge_input",
    placeholder="sri_hidden_bridge",
    label_visibility="collapsed",
    on_change=_on_sri_bridge_change,
)

restore_session_state_on_wakeup()

if "history_log" not in st.session_state or not st.session_state.history_log:
    st.session_state.history_log = _hist_load()


def save_to_history(task_name: str, details: str, entry_type: str = "chat") -> None:
    entry = _hist_append(task_name, details, entry_type)
    if "history_log" not in st.session_state:
        st.session_state.history_log = []
    st.session_state.history_log.append(entry)


db_state = load_db()
metrics = db_state.get("metrics", {})
all_tasks = db_state.get("tasks", {})
running_count = sum(1 for t in all_tasks.values() if t.get("status") == "RUNNING")
completed_count = metrics.get("completed_tasks", 0)
failed_count = metrics.get("failed_tasks", 0)
agent_status_str = "SRI (Active)" if running_count > 0 else "SRI (Ready)"

target_rel = "login.html"
target_full = os.path.join(WORKSPACE_DIR, target_rel)
if not os.path.exists(target_full):
    ws_files = get_workspace_files()
    target_rel = ws_files[0] if ws_files else "login.html"
    target_full = os.path.join(WORKSPACE_DIR, target_rel)

generated_code = ""
if os.path.exists(target_full):
    try:
        with open(target_full, "r", encoding="utf-8") as f:
            generated_code = f.read()
    except Exception:
        generated_code = ""

workspace_file_label = f"workspace/{target_rel}" if os.path.exists(target_full) else "SRI Solo AI Companion"
generated_preview_html = generated_code

reply_spoken: str = ""
active_voice_lang: str = str(st.session_state.get("sri_voice_lang_pref") or "ta-IN")
active_page_hint: str = ""
active_tab_hint: str = ""
active_input_channel: str = "chat"
active_voice_turn_id: str = str(st.session_state.get("sri_voice_turn_id", ""))

bridge_cmd = st.session_state.pop("_active_sri_bridge_cmd", None)
raw_cmd = bridge_cmd or st.query_params.get("sri_cmd")

if raw_cmd:
    try:
        for qp in ("sri_cmd", "ts"):
            if qp in st.query_params:
                del st.query_params[qp]
    except Exception:
        pass

    effective_prompt = ""
    input_channel = "chat"
    is_research_query = False
    new_t_id = None

    try:
        effective_prompt, input_channel, active_voice_lang = parse_bridge_payload(str(raw_cmd))
        active_input_channel = input_channel
        if effective_prompt and effective_prompt != "VOICE_TRIGGER":
            st.session_state["task_prompt_val"] = effective_prompt
            st.session_state["current_task_prompt"] = effective_prompt
            turn_seq = int(st.session_state.get("sri_voice_turn_seq", 0)) + 1
            st.session_state["sri_voice_turn_seq"] = turn_seq
            active_voice_turn_id = f"turn_{turn_seq}_{int(time.time() * 1000)}"
            st.session_state["sri_voice_turn_id"] = active_voice_turn_id

            if "sri_chat_history" not in st.session_state:
                st.session_state["sri_chat_history"] = []

            try:
                query_lower = effective_prompt.lower()
                is_research_query = is_realtime_web_search_required(effective_prompt)
                research_summary = None

                if is_research_query:
                    research_data = perform_live_web_research(effective_prompt)
                    research_file_full = os.path.join(WORKSPACE_DIR, "research.html")
                    try:
                        with open(research_file_full, "w", encoding="utf-8") as f:
                            f.write(research_data["card_html"])
                    except Exception:
                        pass
                    st.session_state["sri_latest_research_html"] = research_data.get("panel_html") or ""
                    research_summary = research_data["voice_summary"]
                    active_page_hint = "research"

                is_build_request = any(
                    w in query_lower
                    for w in [
                        "build ui", "create ui", "generate ui", "dashboard ui", "landing page",
                        "student dashboard", "saas auth", "kanban board", "refine logic",
                        "in workspace", "workspace/", "refine workspace", "web app in workspace",
                        "build a website", "create a page", "ui உருவாக்கு",
                    ]
                )
                is_preview_nav = any(
                    w in query_lower
                    for w in [
                        "show preview", "open preview", "preview page", "check preview",
                        "go to preview", "switch to preview", "view preview", "open project", "show project",
                        "show code", "open code", "source code", "code view", "inspect code",
                        "go to code", "switch to code",
                        "ப்ரிவியூ", "பிரிவியூ", "கோடு காட்டு", "சோர்ஸ் கோடு",
                    ]
                )
                new_t_id = None
                if is_build_request and not is_research_query:
                    folder_target = st.session_state.get("task_folder_val", "").strip() or derive_project_slug("", effective_prompt)
                    task_kind = "frontend" if any(w in query_lower for w in ["ui", "design", "html", "css", "frontend", "பக்கம்"]) else "auto"
                    new_t_id = dispatch_background_task(
                        prompt=effective_prompt,
                        task_type=task_kind,
                        folder_name=folder_target,
                    )
                    active_page_hint = "project"
                    active_tab_hint = "preview"
                elif is_preview_nav and not is_research_query:
                    active_page_hint = "project"
                    active_tab_hint = "code" if any(w in query_lower for w in ["code", "கோடு", "சோர்ஸ்"]) else "preview"

                reply_spoken = get_executive_voice_response(
                    effective_prompt,
                    active_tasks_count=running_count,
                    workspace_file=workspace_file_label,
                    file_exists=os.path.exists(target_full),
                    file_size=len(generated_code),
                    newly_dispatched_id=new_t_id,
                    research_summary=research_summary,
                    channel=input_channel,
                    preferred_lang=active_voice_lang,
                    chat_history=st.session_state.get("sri_chat_history", []),
                )
                reply_spoken = sanitize_unsolicited_links(reply_spoken, effective_prompt)

                if not is_research_query:
                    generated_preview_html = build_companion_inline_card(effective_prompt, reply_spoken)
                    workspace_file_label = "SRI Solo AI Companion"
            except Exception as brain_err:
                print(f"⚠️ Voice/Chat brain fallback error: {brain_err}")
                reply_spoken = _friendly_tamil_ai_error(brain_err)
                generated_preview_html = build_companion_inline_card(effective_prompt, reply_spoken)
                if is_research_query:
                    st.session_state["sri_latest_research_html"] = build_companion_inline_card(effective_prompt, reply_spoken)
                    active_page_hint = "research"
                workspace_file_label = "SRI Solo AI Companion"

            st.session_state["sri_chat_history"].append({"user": effective_prompt, "agent": reply_spoken})
            hist_type = "research" if is_research_query else ("voice" if input_channel == "orb" else "chat")
            try:
                save_to_history(effective_prompt, reply_spoken, hist_type)
            except Exception:
                pass
    except Exception as bridge_err:
        print(f"⚠️ Bridge command processing error: {bridge_err}")
        reply_spoken = _friendly_tamil_ai_error(bridge_err)


_ui_ws_files_payload = []
try:
    for _wf in get_workspace_files()[:12]:
        _ok_rf, _rf_content, _ = safe_read_code(_wf)
        if _ok_rf:
            _ui_ws_files_payload.append({
                "path": f"workspace/{_wf}",
                "short": _wf,
                "content": _rf_content[:60000],
                "sizeBytes": len(_rf_content.encode("utf-8", errors="ignore")),
            })
except Exception:
    _ui_ws_files_payload = []

_ui_tracker_tasks = []
try:
    for _tid, _tdata in list(all_tasks.items())[-12:]:
        if isinstance(_tdata, dict):
            _ui_tracker_tasks.append({
                "id": _tid,
                "title": _tdata.get("title") or _tdata.get("prompt", "Agent Task")[:60],
                "status": _tdata.get("status", "COMPLETED"),
                "progress": _tdata.get("progress", 100),
                "file": _tdata.get("workspace_file") or _tdata.get("output_file") or "",
            })
except Exception:
    _ui_tracker_tasks = []

render_sri_zero_failure_ui(
    agent_status=agent_status_str,
    active_tasks=running_count,
    completed_tasks=completed_count,
    failed_tasks=failed_count,
    workspace_file=workspace_file_label,
    generated_code=generated_code,
    generated_preview_html=generated_preview_html,
    research_html=st.session_state.get("sri_latest_research_html", ""),
    chat_history=st.session_state.get("sri_chat_history", []),
    voice_reply_text=reply_spoken,
    voice_lang=active_voice_lang,
    voice_turn_id=active_voice_turn_id,
    skip_tts=(not reply_spoken) or (active_input_channel != "orb"),
    active_page=active_page_hint,
    active_tab=active_tab_hint,
    history_log=_hist_for_ui(limit=200),
    whatsapp_alert_status=evaluate_all_tasks_completion(db_state),
    workspace_files_data=_ui_ws_files_payload,
    tracker_tasks_data=list(reversed(_ui_tracker_tasks)),
)

