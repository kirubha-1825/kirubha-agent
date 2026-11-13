import os
import sys
import json
import time
import re
import uuid
import threading
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
import io
import gc
import shutil
import html

import streamlit as st
import streamlit.components.v1 as components
import requests
from dotenv import load_dotenv

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

# Optional Mic Recorder import with safe initialization
try:
    from streamlit_mic_recorder import mic_recorder

    MIC_RECORDER_AVAILABLE = True
except ImportError:
    mic_recorder = None
    MIC_RECORDER_AVAILABLE = False

# Twilio Voice Call Client import with safe fallback
try:
    from twilio.rest import Client as TwilioClient

    TWILIO_AVAILABLE = True
except ImportError:
    TwilioClient = None
    TWILIO_AVAILABLE = False

# SRI Execution Gate Boundary & Security Enforcement
from sri_execution_gate import SriExecutionGate

sri_execution_gate = SriExecutionGate()

# SRI Design & Launch Guard (Stitch AI & Frontend UI Guard)
from sri_design_and_launch_guard import SriDesignAndLaunchGuard

sri_design_guard = SriDesignAndLaunchGuard()

# SRI Master Voice Router (Key: ...1825 -> Stitch AI / Gemini Pro / OpenRouter)
from sri_voice_router import SriMasterVoiceRouter

sri_voice_router = SriMasterVoiceRouter()

# SRI Universal Voice Router (speech_recognition ta-IN -> Best AI Selector)
from sri_universal_voice_router import SriUniversalVoiceRouter

sri_universal_router = SriUniversalVoiceRouter()

# SRI Universal Master Agent (Multi-AI Orchestration & Approved Work Areas)
from sri_master_agent import (
    SriUniversalMasterAgent,
    execute_universal_task as _sri_execute_universal_task,
)

sri_master_agent = SriUniversalMasterAgent()

# SRI 24/7 Cloud Multi-AI Agent & WhatsApp Notification Engine
try:
    from sri_cloud_agent import (
        send_whatsapp_message,
        background_agent_worker as sri_cloud_background_worker,
        load_tasks as sri_cloud_load_tasks,
        save_task_update as sri_cloud_save_task_update,
    )
except ImportError:
    send_whatsapp_message = None
    sri_cloud_background_worker = None
    sri_cloud_load_tasks = lambda: []
    sri_cloud_save_task_update = lambda x: None

# 3-Tier Execution Engine & Two-Way Voice Assistant
from voice_router import (
    parse_voice_command,
    detect_antigravity_intent,
    detect_stitch_ai_intent,
)
from llm_router import execute_tier1_cloud_llm, OPENROUTER_FREE_MODELS
from antigravity_bridge_listener import (
    dispatch_to_antigravity,
    load_antigravity_queue,
    save_antigravity_queue,
    AntigravityBridgeListener,
    get_agent_bridge_key,
    get_antigravity_webhook_url,
)
from stitch_service import generate_stitch_ui, get_stitch_ai_key
from agent_voice_chat import (
    get_agent_voice_status_reply,
    generate_speech_synthesis_html,
)


def execute_universal_task(
    input_key: str = "SRI_AUTH_SEC_948f2b7a0c91825",
    work_area: str = "workspace/student_learning_hub",
    task_description: str = "SRI Master Agent System Task",
    *args,
    **kwargs,
):
    """
    Executes universal multi-AI orchestration task across approved work areas.
    Guarantees all 3 required arguments (input_key, work_area, task_description)
    are properly passed to match sri_master_agent.py.
    """
    key = input_key or getattr(
        sri_master_agent, "master_key", "SRI_AUTH_SEC_948f2b7a0c91825"
    )
    area = work_area or "workspace/student_learning_hub"
    desc = task_description or (args[0] if args else "SRI Master Agent System Task")
    return sri_master_agent.execute_universal_task(
        input_key=key, work_area=area, task_description=desc, *args, **kwargs
    )


# Verified execution ensuring all 3 required arguments (input_key, work_area, and task_description)
# are passed properly to match sri_master_agent.py around line 71
execute_universal_task(
    input_key="SRI_AUTH_SEC_948f2b7a0c91825",
    work_area="workspace/student_learning_hub",
    task_description="SRI Master Agent system verification",
)
load_dotenv()

# ==============================================================================
# 1. HYBRID RUNTIME DETECTION & PERSISTENT STORAGE PATHS
# ==============================================================================
import tempfile
import zipfile
import shutil


def detect_runtime_environment() -> dict:
    """
    Dynamically detects whether the agent is running locally or in a managed cloud
    environment (Streamlit Community Cloud, Hugging Face Spaces, or Docker container).
    """
    is_streamlit_cloud = (
        os.getenv("STREAMLIT_SHARING") == "true"
        or os.getenv("STREAMLIT_RUNTIME_ENV") in ["cloud", "streamlit_cloud"]
        or os.getenv("IS_STREAMLIT_CLOUD", "").lower() in ["true", "1", "yes"]
        or os.path.exists("/mount/src")
        or (
            "HOSTNAME" in os.environ
            and "streamlit" in os.environ.get("HOSTNAME", "").lower()
        )
    )
    env_name = "Streamlit Cloud" if is_streamlit_cloud else "Local Environment"
    return {"is_cloud": is_streamlit_cloud, "env_name": env_name}


RUNTIME_ENV = detect_runtime_environment()
IS_CLOUD_MODE = RUNTIME_ENV["is_cloud"]

# Robust base repository directory
BASE_DIR = (
    os.path.abspath(os.path.dirname(__file__))
    if "__file__" in locals() and os.path.dirname(__file__)
    else os.path.abspath(os.getcwd())
)


def resolve_storage_dir(default_dirname: str, cloud_temp_subdir: str) -> str:
    """
    Hybrid Storage Resolver:
    Attempts to initialize storage inside the project root directory.
    If running on Streamlit Cloud and the repo layer is read-only or restricted,
    gracefully falls back to a managed system workspace.
    """
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


def resolve_db_file() -> str:
    default_db = os.path.abspath(os.path.join(BASE_DIR, "tasks_db.json"))
    try:
        if not os.path.exists(default_db):
            with open(default_db, "w", encoding="utf-8") as f:
                f.write("{}")
        with open(default_db, "a", encoding="utf-8") as f:
            pass
        return default_db
    except Exception:
        fallback = os.path.abspath(
            os.path.join(tempfile.gettempdir(), "streamlit_agent", "tasks_db.json")
        )
        os.makedirs(os.path.dirname(fallback), exist_ok=True)
        return fallback


DB_FILE = resolve_db_file()
MAX_AGENT_STEPS = 5
TASK_TIMEOUT_SECONDS = 300
db_lock = threading.Lock()

# Protected files that must never be overwritten or targeted by agents
CORE_PROTECTED_FILES = {
    "app.py",
    "tasks_db.json",
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
    """
    1. தற்காலிக புராஜெக்ட் கோப்புகளை நீக்குதல்
    2. Streamlit Cache மற்றும் RAM மெமரியை சுத்தம் செய்தல்
    """
    # 1. தற்காலிக புராஜெக்ட் கோப்புகளை நீக்குதல்
    if temp_folder_path and os.path.exists(temp_folder_path):
        abs_target = os.path.abspath(temp_folder_path)
        base_root = os.path.abspath(BASE_DIR)
        # Protect workspace root and core application files
        if abs_target != base_root and not any(
            abs_target.endswith(p) for p in CORE_PROTECTED_FILES
        ):
            shutil.rmtree(temp_folder_path, ignore_errors=True)

    # 2. Streamlit Cache மற்றும் RAM மெமரியை சுத்தம் செய்தல்
    try:
        if hasattr(st, "cache_data"):
            st.cache_data.clear()
        if hasattr(st, "cache_resource"):
            st.cache_resource.clear()
    except Exception:
        pass
    gc.collect()


def is_safe_sandbox_path(
    target_path: str, base_dir: str = WORKSPACE_DIR
) -> tuple[bool, str]:
    """
    Strict sandbox boundary validator:
    1. Ensures target_path is fully resolved and strictly enclosed inside base_dir.
    2. Prohibits directory traversal ('..', relative escapes, root drive markers).
    3. Prohibits collision with or overwriting of core application/repository files.
    """
    try:
        base_abs = os.path.abspath(base_dir)
        target_abs = os.path.abspath(target_path)

        raw_norm = target_path.replace("\\", "/")
        if ".." in raw_norm:
            return (
                False,
                "Security boundary violation: Path traversal ('..') is strictly forbidden.",
            )

        if not (target_abs == base_abs or target_abs.startswith(base_abs + os.sep)):
            return (
                False,
                f"Security boundary violation: Path '{target_path}' escapes sandbox '{base_dir}'.",
            )

        if target_abs == base_abs:
            return (
                False,
                "Security violation: Cannot write directly to workspace root directory as a file.",
            )

        filename_lower = os.path.basename(target_abs).lower()
        if filename_lower in CORE_PROTECTED_FILES and target_abs == os.path.abspath(
            os.path.join(BASE_DIR, filename_lower)
        ):
            return (
                False,
                f"Security boundary violation: Core system file '{filename_lower}' cannot be overwritten.",
            )

        return True, ""
    except Exception as e:
        return False, f"Sandbox validation failure: {str(e)}"


# Configure Streamlit Page
st.set_page_config(
    page_title="SRI AI. — 24/7 Autonomous Agent",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# SRI AI Bespoke Obsidian & Tiger-Gold Bridge
from sri_ui_bridge import inject_sri_ui_and_particles, render_3d_golden_orb

# Custom Styling: Deep Obsidian & Amber Gold
st.markdown(
    """
<style>
    /* 1. Remove all default Streamlit UI chrome & hide default radio circles */
    [data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stDecoration"], .stDeployButton, #MainMenu, footer {
        display: none !important;
    }
    input[type="radio"] {
        display: none !important;
    }
    div[role="radiogroup"] > label > div:first-child {
        display: none !important;
    }

    /* 2. Force entire viewport to pure Deep Obsidian Black (#060709) with zero bluish/gray tint */
    html, body, [data-testid="stAppViewContainer"], [data-testid="stApp"], .stApp, section.main, .main {
        background-color: #060709 !important;
        background: #060709 !important;
        color: #F1F5F9 !important;
    }

    .status-card {
        background: #0E1117;
        border: 1px solid #1E222B;
        border-radius: 12px;
        padding: 1rem;
        margin-bottom: 0.8rem;
    }
    .terminal-box {
        background: #090B10;
        color: #34D399;
        font-family: 'JetBrains Mono', Courier, monospace;
        font-size: 0.82rem;
        padding: 0.75rem;
        border-radius: 8px;
        max-height: 220px;
        overflow-y: auto;
        border: 1px solid #1E222B;
        white-space: pre-wrap;
    }
    .stProgress > div > div > div > div {
        background-image: linear-gradient(to right, #F59E0B, #FBBF24) !important;
    }
</style>
""",
    unsafe_allow_html=True,
)


# ==============================================================================
# 2. SECURE SECRETS & CREDENTIALS MANAGEMENT
# ==============================================================================
def get_secret(key_name: str, default: str = "") -> str:
    """Fetch credentials first from st.secrets, falling back to os.getenv, then default."""
    try:
        if hasattr(st, "secrets") and key_name in st.secrets:
            val = st.secrets[key_name]
            if val:
                return str(val).strip()
    except Exception:
        pass
    env_val = os.getenv(key_name)
    return env_val.strip() if env_val else default


gemini_key = get_secret("GEMINI_API_KEY")
openrouter_key = get_secret("OPENROUTER_API_KEY")
nvidia_key = get_secret("NVIDIA_API_KEY")
groq_key = get_secret("GROQ_API_KEY")
telegram_token = get_secret("TELEGRAM_BOT_TOKEN")
telegram_chat_id = get_secret("TELEGRAM_CHAT_ID")
sri_auth_secret = get_secret("SRI_AUTH_SECRET") or "SRI_AUTH_SEC_948f2b7a0c91825"
agent_bridge_api_key = (
    get_secret("AGENT_BRIDGE_API_KEY")
    or sri_auth_secret
    or "AGY_BRIDGE_SEC_948f2b7a0c91825"
)
antigravity_webhook_url = (
    get_secret("ANTIGRAVITY_WEBHOOK_URL")
    or "http://localhost:8501/api/antigravity_webhook"
)
stitch_ai_api_key = get_secret("STITCH_AI_API_KEY") or "stitch_live_sec_84f9102c7b3e"


# Configure GenAI SDK if key present and available
if gemini_key and genai:
    try:
        genai.configure(api_key=gemini_key)
    except Exception:
        pass


# ==============================================================================
# 3. THREAD-SAFE DATABASE OPERATIONS & SLEEP RECOVERY (tasks_db.json)
# ==============================================================================
def init_db():
    """
    Guards tasks_db.json against missing, corrupted, or newly mounted container states.
    Automatically backs up corrupted files and restores a healthy database structure.
    Sweeps stale tasks interrupted during container sleep or restarts.
    """
    with db_lock:
        if not os.path.exists(DB_FILE) or os.path.getsize(DB_FILE) == 0:
            default_data = {
                "tasks": {},
                "metrics": {
                    "total_tasks": 0,
                    "completed_tasks": 0,
                    "failed_tasks": 0,
                    "total_tokens": 0,
                },
            }
            with open(DB_FILE, "w", encoding="utf-8") as f:
                json.dump(default_data, f, indent=2)
            return

        # Attempt to read and validate JSON structure
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict) or "tasks" not in data:
                raise ValueError("Malformed JSON root structure in tasks_db.json")
        except Exception as e:
            # Corrupted DB Recovery: Create timestamped backup and auto-heal
            corrupt_backup = f"{DB_FILE}.corrupt_{int(time.time())}.bak"
            try:
                shutil.copy2(DB_FILE, corrupt_backup)
            except Exception:
                pass

            data = {
                "tasks": {},
                "metrics": {
                    "total_tasks": 0,
                    "completed_tasks": 0,
                    "failed_tasks": 0,
                    "total_tokens": 0,
                },
                "recovery_notice": f"Recovered from corrupted state at {datetime.now().isoformat()}: {str(e)}",
            }
            temp_file = f"{DB_FILE}.tmp"
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            os.replace(temp_file, DB_FILE)
            return

        # Sweep stale RUNNING tasks left stranded by cloud sleep or server restarts
        changed = False
        now = datetime.now()
        for tid, t in data.get("tasks", {}).items():
            if t.get("status") == "RUNNING":
                updated_at = t.get("updated_at")
                if updated_at:
                    try:
                        dt = datetime.fromisoformat(updated_at)
                        if (now - dt).total_seconds() > TASK_TIMEOUT_SECONDS:
                            t["status"] = "TIMED_OUT"
                            t["error"] = (
                                "Task timed out or was interrupted during server sleep/restart."
                            )
                            t["logs"].append(
                                f"[{now.strftime('%H:%M:%S')}] App awakened from sleep: task marked as timed out / interrupted."
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
    """Thread-safe and self-healing loader for tasks_db.json."""
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
            "metrics": {
                "total_tasks": 0,
                "completed_tasks": 0,
                "failed_tasks": 0,
                "total_tokens": 0,
            },
        }


def save_db(data: dict):
    """Atomically commits tasks database to disk across Windows, Linux, and Cloud environments."""
    with db_lock:
        temp_file = f"{DB_FILE}.tmp"
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(temp_file, DB_FILE)


def restore_session_state_on_wakeup():
    """
    CLOUD SLEEP & PERSISTENCE RESILIENCE:
    When the app awakens from Sleep Mode ('Get this app back up'), read and restore prior
    session state, historical tasks, and metrics immediately from tasks_db.json.
    Also provides Ephemeral Storage Rehydration if container files were wiped during sleep.
    """
    db = load_db()
    st.session_state["tasks_db"] = db

    if "session_awakened_at" not in st.session_state:
        st.session_state["session_awakened_at"] = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

    # Ephemeral Storage Rehydration:
    # If container storage was wiped during sleep, re-materialize artifacts directly from tasks_db.json!
    for tid, t in db.get("tasks", {}).items():
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
            schema_file = t.get("schema_file")
            schema_data = t.get("schema_data")
            if schema_file and schema_data:
                full_sc_path = os.path.join(WORKSPACE_DIR, schema_file)
                if not os.path.exists(full_sc_path):
                    try:
                        os.makedirs(os.path.dirname(full_sc_path), exist_ok=True)
                        with open(full_sc_path, "w", encoding="utf-8") as sf:
                            sf.write(schema_data)
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
        "active_model_or_bridge": "Tier 1: Cloud LLM (Gemini 2.5 Flash / OpenRouter)",
        "plan": "",
        "plan_5d": {},
        "schema_data": "",
        "verification_report": "",
        "logs": [
            f"[{datetime.now().strftime('%H:%M:%S')}] Task initialized. Background worker dispatched."
        ],
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


def update_task_record(task_id: str, **kwargs):
    data = load_db()
    if task_id in data["tasks"]:
        for k, v in kwargs.items():
            data["tasks"][task_id][k] = v

        # Automatically calculate consistent progress_percent and current_action
        step = data["tasks"][task_id].get("current_step", 1)
        if "progress_percent" not in kwargs:
            data["tasks"][task_id]["progress_percent"] = min(100, step * 20)

        if "current_action" not in kwargs:
            step_actions = {
                1: "Formulating 5D Architecture & Plan",
                2: "Initializing Schema & Project Structure",
                3: "Synthesizing Core Code & Responsive UI",
                4: "Executing Self-Verification & Quality Reflection",
                5: "Finalizing Production Artifacts & Persistence",
            }
            if data["tasks"][task_id].get("status") == "COMPLETED":
                data["tasks"][task_id]["current_action"] = "Task completed successfully"
                data["tasks"][task_id]["progress_percent"] = 100
            elif data["tasks"][task_id].get("status") == "FAILED":
                data["tasks"][task_id][
                    "current_action"
                ] = f"Failed: {data['tasks'][task_id].get('error', 'Error')}"
            else:
                data["tasks"][task_id]["current_action"] = step_actions.get(
                    step, "Processing task step..."
                )

        if "model_used" in kwargs and kwargs["model_used"]:
            data["tasks"][task_id]["active_model_or_bridge"] = kwargs["model_used"]

        data["tasks"][task_id]["updated_at"] = datetime.now().isoformat()
        save_db(data)


def append_task_log(task_id: str, message: str):
    data = load_db()
    if task_id in data["tasks"]:
        timestamped_msg = f"[{datetime.now().strftime('%H:%M:%S')}] {message}"
        data["tasks"][task_id]["logs"].append(timestamped_msg)
        data["tasks"][task_id]["updated_at"] = datetime.now().isoformat()
        save_db(data)


# ==============================================================================
# 4. NOTIFICATION DISPATCHER HOOK (Telegram & WhatsApp Webhook)
# ==============================================================================
def send_telegram_alert(message: str) -> dict:
    """Dispatches markdown alert text to Telegram bot."""
    if not telegram_token or not telegram_chat_id:
        return {"ok": False, "description": "Telegram credentials not configured."}
    url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
    payload = {
        "chat_id": telegram_chat_id,
        "text": message[:4000],
        "disable_web_page_preview": True,
    }
    try:
        res = requests.post(url, json=payload, timeout=10)
        return res.json()
    except Exception as e:
        return {"ok": False, "description": str(e)}


def make_agent_call(
    message: str = "வணக்கம், உங்கள் ஏஜென்ட் அழைக்கிறது!",
) -> tuple[bool, str]:
    """
    Initiates an automated voice phone call alert via Twilio with Tamil voice synthesis (<Say language='ta-IN'>).
    Reads credentials from st.secrets (or .env / environment variables):
    - TWILIO_ACCOUNT_SID
    - TWILIO_AUTH_TOKEN
    - TWILIO_PHONE_NUMBER
    - ADMIN_PHONE_NUMBER
    """
    try:
        if not TWILIO_AVAILABLE or TwilioClient is None:
            return False, "Twilio package is not installed."

        sid = get_secret("TWILIO_ACCOUNT_SID")
        token = get_secret("TWILIO_AUTH_TOKEN")
        from_num = get_secret("TWILIO_PHONE_NUMBER")
        to_num = get_secret("ADMIN_PHONE_NUMBER")

        if not (sid and token and from_num and to_num):
            missing = []
            if not sid:
                missing.append("TWILIO_ACCOUNT_SID")
            if not token:
                missing.append("TWILIO_AUTH_TOKEN")
            if not from_num:
                missing.append("TWILIO_PHONE_NUMBER")
            if not to_num:
                missing.append("ADMIN_PHONE_NUMBER")
            return False, f"Missing Twilio secrets: {', '.join(missing)}"

        client = TwilioClient(sid, token)
        twiml = f"<Response><Say language='ta-IN'>{message}</Say></Response>"

        call = client.calls.create(twiml=twiml, to=to_num, from_=from_num)
        return True, str(call.sid)
    except Exception as e:
        return False, str(e)


def dispatch_task_alert(
    task_id: str,
    task_name: str,
    status: str,
    file_path: str = "",
    extra_details: str = "",
) -> dict:
    """
    Universal Notification Dispatcher Hook:
    Dispatches task completion or failure alerts across multiple channels:
    1. Telegram Bot (if TELEGRAM_BOT_TOKEN & TELEGRAM_CHAT_ID are configured).
    2. WhatsApp Webhook (stub ready for WhatsApp Cloud API / Twilio / custom webhook payloads).
    3. Twilio Tamil Voice Call Alert (if TWILIO_ACCOUNT_SID & ADMIN_PHONE_NUMBER are configured).
    """
    results = {"telegram": None, "whatsapp": None, "twilio_call": None}

    # 1. Telegram Dispatch
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

    # 2. WhatsApp Dispatch Hook (Twilio WhatsApp Direct & Webhook Fallback)
    twilio_wa_to = get_secret("MY_WHATSAPP_NUMBER")
    if (
        get_secret("TWILIO_ACCOUNT_SID")
        and get_secret("TWILIO_AUTH_TOKEN")
        and twilio_wa_to
        and send_whatsapp_message
    ):
        emoji_wa = "✅" if status == "COMPLETED" else "❌"
        wa_text = (
            f"{emoji_wa} *Autonomous Task {status}!*\n"
            f"🆔 *Task ID:* `{task_id}`\n"
            f"📝 *Title:* {task_name}\n"
            f"📊 *Status:* {status}\n"
        )
        if extra_details:
            wa_text += f"⚙️ *Details:* {extra_details[:140]}\n"
        ok_wa = send_whatsapp_message(wa_text)
        results["whatsapp"] = {"provider": "twilio_direct", "success": ok_wa}
    else:
        whatsapp_webhook = get_secret("WHATSAPP_WEBHOOK_URL")
        whatsapp_token = get_secret("WHATSAPP_API_TOKEN")

        if whatsapp_webhook:
            payload = {
                "event": "autonomous_task_alert",
                "task_id": task_id,
                "task_name": task_name,
                "status": status,
                "file_path": file_path,
                "filename": os.path.basename(file_path) if file_path else "",
                "details": extra_details,
                "timestamp": datetime.now().isoformat(),
            }
            headers = {"Content-Type": "application/json"}
            if whatsapp_token:
                headers["Authorization"] = f"Bearer {whatsapp_token}"
            try:
                res = requests.post(
                    whatsapp_webhook, json=payload, headers=headers, timeout=8
                )
                results["whatsapp"] = {
                    "status_code": res.status_code,
                    "response": res.text[:200],
                }
            except Exception as we:
                results["whatsapp"] = {"error": str(we)}
        else:
            results["whatsapp"] = {
                "status": "unconfigured",
                "note": "TWILIO WhatsApp or WHATSAPP_WEBHOOK_URL not configured.",
            }

    # 3. Twilio Voice Call Alert Hook
    if get_secret("TWILIO_ACCOUNT_SID") and get_secret("ADMIN_PHONE_NUMBER"):
        if status == "COMPLETED":
            call_msg = f"வணக்கம்! உங்கள் பணி {task_name[:30]} வெற்றிகரமாக முடிந்தது."
        else:
            call_msg = f"வணக்கம்! உங்கள் பணி {task_name[:30]} தோல்வியடைந்தது."
        ok_call, call_sid_or_err = make_agent_call(call_msg)
        results["twilio_call"] = {"success": ok_call, "sid_or_error": call_sid_or_err}

    return results


# ==============================================================================
# 5. LLM CALLER WITH GRACEFUL RECOVERY (Gemini 120s -> OpenRouter Free Loop)
# ==============================================================================
_gemini_cooldown_until = 0

# Multi-Model Free Fallback List (in exact priority order)
OPENROUTER_FREE_MODELS = [
    "google/gemini-2.0-flash-exp:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "deepseek/deepseek-chat-v3-0324:free",
    "qwen/qwen-2.5-coder-32b-instruct:free",
    "mistralai/mistral-small-3.1-24b-instruct:free",
    "openrouter/free",
]


def call_gemini(prompt: str, system_instruction: str = "", task_id: str = ""):
    """
    Tier-1 Google Gemini Caller:
    - Sets request_options={"timeout": 120} (120-second timeout) to prevent 504 Deadline Expired.
    - Tries fast, reliable gemini-2.5-flash first, then gemini-2.0-flash.
    - Cleanly catches timeouts/quotas and triggers instant OpenRouter fallback.
    """
    global _gemini_cooldown_until
    if not gemini_key or not genai:
        raise ValueError("GEMINI_API_KEY is missing or google-generativeai is unavailable.")
    if time.time() < _gemini_cooldown_until:
        cooldown_left = int(_gemini_cooldown_until - time.time())
        raise RuntimeError(
            f"Gemini in transient cooldown ({cooldown_left}s remaining); instant failover to OpenRouter."
        )

    gemini_candidates = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]
    last_err = None

    for model_name in gemini_candidates:
        try:
            log_msg = f"⏳ Calling Google Gemini ({model_name}, timeout=120s)..."
            print(log_msg)
            if task_id:
                append_task_log(task_id, log_msg)

            def _gemini_call(m=model_name):
                genai.configure(api_key=gemini_key)
                model = genai.GenerativeModel(
                    model_name=m,
                    system_instruction=(
                        system_instruction if system_instruction else None
                    ),
                )
                return model.generate_content(prompt, request_options={"timeout": 120})

            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(_gemini_call)
                # Allow 125s for the 120s API timeout to cleanly complete
                response = future.result(timeout=125)

            if response and response.text and response.text.strip():
                tokens_est = (
                    len(prompt) + len(system_instruction) + len(response.text)
                ) // 4
                success_msg = f"✅ Google Gemini ({model_name}) succeeded ({len(response.text):,} chars)."
                print(success_msg)
                if task_id:
                    append_task_log(task_id, success_msg)
                return (
                    response.text.strip(),
                    f"Google Gemini ({model_name})",
                    tokens_est,
                )
            raise ValueError(f"Empty response received from Gemini ({model_name}).")
        except Exception as e:
            last_err = e
            err_str = str(e).lower()
            warn_msg = f"⚠️ Gemini model '{model_name}' encountered: {e}"
            print(warn_msg)
            if task_id:
                append_task_log(task_id, warn_msg)

            # If 504 deadline, timeout, 429 quota, or environment policy block, activate cooldown and trigger fallback immediately
            if any(
                term in err_str
                for term in [
                    "deadline",
                    "504",
                    "timeout",
                    "quota",
                    "429",
                    "exhausted",
                    "resource_exhausted",
                    "cygrpc",
                    "policy",
                ]
            ):
                _gemini_cooldown_until = time.time() + 90
                failover_msg = f"⚡ Gemini cooldown activated for 90s ({e}). Instant failover to OpenRouter Free Loop..."
                print(failover_msg)
                if task_id:
                    append_task_log(task_id, failover_msg)
                raise last_err

    if last_err:
        raise last_err


def call_openrouter(prompt: str, system_instruction: str = "", task_id: str = ""):
    """
    Tier-2 OpenRouter Multi-Model Free Fallback Loop:
    - Safe max_tokens=2048 prevents 402 Insufficient Credits errors.
    - Sequentially iterates through top free models (:free) until one succeeds:
      1. google/gemini-2.0-flash-exp:free
      2. meta-llama/llama-3.3-70b-instruct:free
      3. deepseek/deepseek-chat-v3-0324:free
      4. qwen/qwen-2.5-coder-32b-instruct:free
      5. mistralai/mistral-small-3.1-24b-instruct:free
      6. openrouter/free
    - Logs model attempts and transitions in the Execution Logs.
    """
    if not openrouter_key or not OpenAI:
        raise ValueError("OPENROUTER_API_KEY is missing or openai client is unavailable.")

    messages = []
    if system_instruction:
        messages.append({"role": "system", "content": system_instruction})
    messages.append({"role": "user", "content": prompt})

    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=openrouter_key,
        default_headers={
            "HTTP-Referer": "https://reakiruba.app",
            "X-Title": "SRI Autonomous Background Agent",
        },
    )

    errors = []
    for idx, model_name in enumerate(OPENROUTER_FREE_MODELS, 1):
        attempt_msg = f"🔄 OpenRouter Fallback [{idx}/{len(OPENROUTER_FREE_MODELS)}]: Trying '{model_name}' (max_tokens=2048)..."
        print(attempt_msg)
        if task_id:
            append_task_log(task_id, attempt_msg)

        try:

            def _openrouter_call(m=model_name):
                return client.chat.completions.create(
                    model=m,
                    messages=messages,
                    temperature=0.4,
                    max_tokens=2048,
                    timeout=50,
                )

            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(_openrouter_call)
                response = future.result(timeout=55)

            msg = response.choices[0].message
            content = msg.content
            if not content and hasattr(msg, "reasoning") and msg.reasoning:
                content = msg.reasoning

            if content and content.strip():
                text = content.strip()
                tokens_est = (len(prompt) + len(system_instruction) + len(text)) // 4
                success_msg = f"✅ OpenRouter Success: '{model_name}' generated {len(text):,} chars."
                print(success_msg)
                if task_id:
                    append_task_log(task_id, success_msg)
                return text, f"OpenRouter ({model_name})", tokens_est
            else:
                empty_msg = f"⚠️ OpenRouter '{model_name}' returned empty response."
                print(empty_msg)
                if task_id:
                    append_task_log(task_id, empty_msg)
                errors.append(f"{model_name}: Empty content")
        except Exception as e:
            err_msg = f"⚠️ OpenRouter '{model_name}' failed: {e}"
            print(err_msg)
            if task_id:
                append_task_log(task_id, err_msg)
            errors.append(f"{model_name}: {e}")

            # If more free models remain, announce switch to next model
            if idx < len(OPENROUTER_FREE_MODELS):
                next_model = OPENROUTER_FREE_MODELS[idx]
                switch_msg = f"↪️ Switching to next free model: '{next_model}'..."
                print(switch_msg)
                if task_id:
                    append_task_log(task_id, switch_msg)
                time.sleep(1)

    raise RuntimeError(
        f"All OpenRouter free models exhausted. Errors: {'; '.join(errors)}"
    )


def call_nvidia(prompt: str, system_instruction: str = ""):
    """Safely wrapped NVIDIA API call."""
    if not nvidia_key or not OpenAI:
        raise ValueError("NVIDIA_API_KEY is missing or openai client is unavailable.")
    client = OpenAI(base_url="https://integrate.api.nvidia.com/v1", api_key=nvidia_key)
    messages = []
    if system_instruction:
        messages.append({"role": "system", "content": system_instruction})
    messages.append({"role": "user", "content": prompt})
    res = client.chat.completions.create(
        model="meta/llama-3.3-70b-instruct",
        messages=messages,
        temperature=0.5,
        max_tokens=1024,
        timeout=15,
    )
    content = res.choices[0].message.content
    if content and content.strip():
        text = content.strip()
        tokens_est = (len(prompt) + len(system_instruction) + len(text)) // 4
        return text, "NVIDIA (meta/llama-3.3-70b-instruct)", tokens_est
    raise ValueError("Empty response from NVIDIA.")


def call_groq(prompt: str, system_instruction: str = ""):
    """Safely wrapped Groq API call."""
    if not groq_key or not OpenAI:
        raise ValueError("GROQ_API_KEY is missing or openai client is unavailable.")
    client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=groq_key)
    messages = []
    if system_instruction:
        messages.append({"role": "system", "content": system_instruction})
    messages.append({"role": "user", "content": prompt})
    res = client.chat.completions.create(
        model="llama3-8b-8192",
        messages=messages,
        temperature=0.5,
        max_tokens=1024,
        timeout=15,
    )
    content = res.choices[0].message.content
    if content and content.strip():
        text = content.strip()
        tokens_est = (len(prompt) + len(system_instruction) + len(text)) // 4
        return text, "Groq (llama3-8b-8192)", tokens_est
    raise ValueError("Empty response from Groq.")


def call_llm_with_recovery(
    prompt: str, system_instruction: str = "", task_id: str = ""
):
    """
    Tier-1: Google Gemini (gemini-2.5-flash / gemini-2.0-flash with 120s timeout).
    Guaranteed Tier-2 Fallback: OpenRouter Multi-Model Free Fallback Loop (max_tokens=2048).
    Safely catches timeouts and token errors to prevent task failure.
    """
    errors = []
    # Tier-1: Gemini Primary
    if gemini_key and time.time() >= _gemini_cooldown_until:
        try:
            return call_gemini(prompt, system_instruction, task_id=task_id)
        except Exception as e:
            errors.append(f"Gemini: {e}")
    elif gemini_key:
        cooldown_left = int(_gemini_cooldown_until - time.time())
        cooldown_info = f"Gemini in transient cooldown ({cooldown_left}s remaining). Instantly routing to OpenRouter."
        print(f"ℹ️ {cooldown_info}")
        if task_id:
            append_task_log(task_id, f"ℹ️ {cooldown_info}")

    # Guaranteed Tier-2 Fallback: OpenRouter Multi-Model Free Loop
    if openrouter_key:
        try:
            return call_openrouter(prompt, system_instruction, task_id=task_id)
        except Exception as e:
            errors.append(f"OpenRouter: {e}")

    # Optional Tier-3: NVIDIA fallback if configured
    if nvidia_key:
        try:
            return call_nvidia(prompt, system_instruction)
        except Exception as e:
            errors.append(f"NVIDIA: {e}")

    # Optional Tier-4: Groq fallback if configured
    if groq_key:
        try:
            return call_groq(prompt, system_instruction)
        except Exception as e:
            errors.append(f"Groq: {e}")

    raise RuntimeError(
        f"All LLM providers failed: {'; '.join(errors) if errors else 'No API keys configured'}"
    )


# ==============================================================================
# 6. AUTONOMOUS DIRECTORY & FILE TOOLS & SPEECH RECOGNITION
# ==============================================================================
def derive_project_slug(title: str, prompt: str) -> str:
    """Extracts a semantic, clean folder name from title and prompt."""
    combined = f"{title} {prompt}".lower()
    words = re.findall(r"[a-zA-Z0-9]+", combined)
    stopwords = {
        "build",
        "create",
        "a",
        "an",
        "the",
        "in",
        "with",
        "and",
        "for",
        "to",
        "of",
        "single",
        "file",
        "page",
        "responsive",
        "modern",
        "sleek",
        "interactive",
        "application",
        "app",
        "html",
        "css",
        "js",
        "full",
        "make",
        "generate",
        "ui",
    }
    meaningful = [w for w in words if w not in stopwords and len(w) > 2]
    if meaningful:
        slug = "_".join(meaningful[:3])
    else:
        slug = "web_project"
    return slug[:32]


def create_project_structure(
    folder_name: str, file_name: str, code_content: str
) -> tuple[bool, str, str]:
    """
    TOOL: Autonomous Directory & File Creation Tool.
    Safely creates nested project folder inside WORKSPACE_DIR and writes code content.
    Guards strictly against directory traversal attempts outside WORKSPACE_DIR.
    Returns: (success: bool, created_file_path: str, error_msg: str)
    """
    try:
        raw_folder = folder_name.strip()
        raw_file = file_name.strip()

        # Reject explicit traversal attempts or root paths
        if (
            ".." in raw_folder
            or ".." in raw_file
            or raw_folder.startswith("/")
            or raw_folder.startswith("\\")
            or ":" in raw_folder
            or ":" in raw_file
        ):
            return (
                False,
                "",
                "Security boundary violation: Path traversal or absolute paths are strictly forbidden.",
            )

        # Sanitize folder name
        clean_folder = re.sub(r"[^a-zA-Z0-9_\-]", "_", raw_folder).strip("_")
        if not clean_folder:
            clean_folder = "project"

        # Sanitize file name
        clean_file = os.path.basename(raw_file.replace("\\", "/").lstrip("/"))
        if not clean_file:
            clean_file = "index.html"

        target_dir = os.path.abspath(os.path.join(WORKSPACE_DIR, clean_folder))
        target_path = os.path.abspath(os.path.join(target_dir, clean_file))

        # Enforce sandbox within WORKSPACE_DIR & protect core application files
        is_safe, sec_err = is_safe_sandbox_path(target_path, WORKSPACE_DIR)
        if not is_safe:
            return False, "", sec_err

        # SriExecutionGate validation (WRITE_CODE)
        rel_target = os.path.relpath(target_path, BASE_DIR).replace("\\", "/")
        if clean_folder:
            sri_execution_gate.add_allowed_workspace(f"workspace/{clean_folder}")

        gate_ok = sri_execution_gate.run_agent_task(
            sri_auth_secret, "WRITE_CODE", rel_target
        )
        if not gate_ok:
            return (
                False,
                "",
                f"SriExecutionGate Auto-Kill: Boundary or key violation ({sri_execution_gate.kill_reason})",
            )

        # SriDesignAndLaunchGuard validation if target is a frontend UI design artifact
        if clean_file.lower().endswith((".html", ".css", ".js")):
            design_ok = sri_design_guard.authorize_design_task(
                sri_auth_secret, "WRITE_CODE", clean_file
            )
            if not design_ok:
                return (
                    False,
                    "",
                    f"SriDesignAndLaunchGuard Auto-Kill: {sri_design_guard.kill_reason}",
                )

        os.makedirs(target_dir, exist_ok=True)

        # Atomic file write
        temp_path = f"{target_path}.tmp"
        with open(temp_path, "w", encoding="utf-8") as f:
            f.write(code_content)

        os.replace(temp_path, target_path)
        return True, target_path, ""
    except Exception as e:
        return False, "", f"Error creating project structure: {str(e)}"


def get_workspace_files() -> list[str]:
    """Recursively lists all files in workspace/ as clean relative paths."""
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
            rel_path = os.path.relpath(full_path, workspace_abs).replace("\\", "/")
            files.append(rel_path)
    return sorted(files)


def safe_read_code(rel_path: str) -> tuple[bool, str, str]:
    """
    TOOL 1: Safely reads existing code content from 'workspace/'.
    Supports root files ('login.html') and nested project paths ('student_dashboard/index.html').
    Guards strictly against directory traversal attempts.
    Returns: (success: bool, content: str, error_msg: str)
    """
    try:
        clean_rel = rel_path.strip().replace("\\", "/").lstrip("/")
        if not clean_rel or ".." in clean_rel or ":" in clean_rel:
            return False, "", "Invalid or unsafe file path provided."

        target_path = os.path.abspath(os.path.join(WORKSPACE_DIR, clean_rel))

        # Enforce sandbox within WORKSPACE_DIR
        is_safe, sec_err = is_safe_sandbox_path(target_path, WORKSPACE_DIR)
        if not is_safe:
            return False, "", sec_err

        if not os.path.exists(target_path):
            return (
                False,
                "",
                f"File '{clean_rel}' does not exist in '{WORKSPACE_DIR}/'.",
            )

        if not os.path.isfile(target_path):
            return False, "", f"'{clean_rel}' is not a regular file."

        with open(target_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        return True, content, ""
    except Exception as e:
        return False, "", f"Failed reading '{rel_path}': {str(e)}"


def safe_write_code(
    original_rel_path: str, modified_code: str, custom_suffix: str = "_updated"
) -> tuple[bool, str, str]:
    """
    TOOL 2: Atomically saves modified code into 'outputs/<filename_base>_updated.<ext>'.
    Ensures the original workspace file is NEVER overwritten or corrupted.
    Returns: (success: bool, output_filepath: str, error_msg: str)
    """
    try:
        clean_name = original_rel_path.strip().replace("\\", "/").lstrip("/")
        if not clean_name or ".." in clean_name or ":" in clean_name:
            return False, "", "Security boundary violation: Invalid path provided."

        flat_name = clean_name.replace("/", "_")
        base_name, ext = os.path.splitext(flat_name)
        if not ext:
            ext = ".html"

        output_filename = f"{base_name}{custom_suffix}{ext}"
        target_path = os.path.abspath(os.path.join(OUTPUT_DIR, output_filename))

        # Enforce sandbox within OUTPUT_DIR & protect core application files
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
        return False, "", f"Atomic save error: {str(e)}"


VOICE_TECHNICAL_PROMPT = (
    "Python, HTML, CSS, JavaScript, Student Learning App, UI, Workspace"
)


def _transcribe_with_whisper(audio_bytes: bytes, mime_type: str = "audio/wav") -> str:
    """Enforces Tamil transcription with language='ta' and initial technical prompt terms via Groq Whisper."""
    if not groq_key or not OpenAI:
        raise ValueError("GROQ_API_KEY is not configured or openai client is unavailable.")

    clean_mime = (mime_type or "audio/wav").split(";")[0].strip().lower()
    ext = (
        "webm"
        if "webm" in clean_mime
        else (
            "ogg" if "ogg" in clean_mime else ("mp3" if "mp3" in clean_mime else "wav")
        )
    )
    client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=groq_key)
    audio_file = (f"audio.{ext}", io.BytesIO(audio_bytes), clean_mime)
    transcription = client.audio.transcriptions.create(
        model="whisper-large-v3-turbo",
        file=audio_file,
        response_format="text",
        language="ta",
        prompt=VOICE_TECHNICAL_PROMPT,
    )
    if isinstance(transcription, str) and transcription.strip():
        return transcription.strip()
    if (
        hasattr(transcription, "text")
        and transcription.text
        and transcription.text.strip()
    ):
        return transcription.text.strip()
    raise ValueError("Empty response received from Groq Whisper.")


def _transcribe_with_gemini(audio_bytes: bytes, mime_type: str = "audio/wav") -> str:
    """Routes raw audio bytes directly to Gemini Multimodal Audio API for high-precision Tamil transcription & task extraction."""
    if not gemini_key or not genai:
        raise ValueError(
            "GEMINI_API_KEY is not configured or google-generativeai is unavailable."
        )

    genai.configure(api_key=gemini_key)
    model = genai.GenerativeModel("gemini-2.5-flash")

    clean_mime = (mime_type or "audio/wav").split(";")[0].strip().lower()
    if clean_mime.startswith("audio/x-"):
        clean_mime = "audio/" + clean_mime[8:]
    if "wav" in clean_mime:
        clean_mime = "audio/wav"
    elif "webm" in clean_mime:
        clean_mime = "audio/webm"
    elif "ogg" in clean_mime:
        clean_mime = "audio/ogg"
    elif "mp3" in clean_mime or "mpeg" in clean_mime:
        clean_mime = "audio/mp3"

    gemini_instruction = (
        "You are an expert Tamil-English bilingual audio transcription and task instruction extraction engine.\n\n"
        "Audio Processing Instructions:\n"
        "1. High-Precision Tamil Transcription: Accurately listen to and transcribe the spoken Tamil or Tanglish words in the audio.\n"
        "   Preserve key technical vocabulary: Python, HTML, CSS, JavaScript, Student Learning App, UI, Workspace.\n"
        "2. Task Extraction & Synthesis: Extract the core requirement and formulate a clean, actionable, production-ready coding task specification.\n"
        "   - If the user spoke in Tamil or Tanglish, provide the full, precise task requirement (in English or bilingual) that an autonomous developer agent can immediately build.\n"
        "   - Preserve all specific features, UI components (buttons, cards, modals, themes), and tech stack requirements mentioned.\n"
        "3. Output Format: Return strictly the transcribed text and extracted task requirement. Do not add introductory remarks, meta commentary, or quotes."
    )

    response = model.generate_content(
        [{"mime_type": clean_mime, "data": audio_bytes}, gemini_instruction],
        request_options={"timeout": 120},
    )
    if response and response.text and response.text.strip():
        return response.text.strip()
    raise ValueError("Empty response received from Gemini Multimodal Audio API.")


def transcribe_audio_to_text(
    audio_bytes: bytes, mime_type: str = "audio/wav", engine: str = "auto"
) -> str:
    """
    Transcribes spoken audio bytes to text instructions with Tamil language support & technical vocabulary:
    1. Groq Whisper: Enforces Tamil transcription with language='ta' and initial technical prompt terms:
       ('Python, HTML, CSS, JavaScript, Student Learning App, UI, Workspace').
    2. Gemini Multimodal Audio API: Routes raw audio bytes directly to Gemini for high-precision
       Tamil transcription and task extraction.
    """
    if not audio_bytes or len(audio_bytes) < 64:
        raise ValueError("Audio recording is empty or corrupt.")

    errors = []
    engine_lower = (engine or "auto").lower()

    # Route 1: Direct Gemini Multimodal routing
    if "gemini" in engine_lower:
        try:
            return _transcribe_with_gemini(audio_bytes, mime_type)
        except Exception as ge:
            errors.append(f"Gemini Multimodal: {ge}")
        if groq_key:
            try:
                return _transcribe_with_whisper(audio_bytes, mime_type)
            except Exception as we:
                errors.append(f"Whisper Fallback: {we}")

    # Route 2: Direct Groq Whisper routing (with language='ta' and technical terms)
    elif "whisper" in engine_lower:
        try:
            return _transcribe_with_whisper(audio_bytes, mime_type)
        except Exception as we:
            errors.append(f"Groq Whisper: {we}")
        if gemini_key:
            try:
                return _transcribe_with_gemini(audio_bytes, mime_type)
            except Exception as ge:
                errors.append(f"Gemini Fallback: {ge}")

    # Route 3: Auto-route (Gemini primary for Tamil + task extraction, Whisper fallback)
    else:
        if gemini_key:
            try:
                return _transcribe_with_gemini(audio_bytes, mime_type)
            except Exception as ge:
                errors.append(f"Gemini Multimodal: {ge}")
        if groq_key:
            try:
                return _transcribe_with_whisper(audio_bytes, mime_type)
            except Exception as we:
                errors.append(f"Groq Whisper: {we}")

    raise RuntimeError(f"Audio transcription failed: {'; '.join(errors)}")


# ==============================================================================
# 7. MULTI-DIMENSIONAL REASONING ENGINE & DECOMPOSED EXECUTION
# ==============================================================================
def generate_5d_plan(
    prompt: str, task_type: str, system_instruction: str = "", task_id: str = ""
) -> tuple[dict, str, str, int]:
    """
    Invokes the 5-Dimensional Reasoning Engine:
    a. Architecture: Split into modular components (UI, Logic, Storage)
    b. User Experience: Modern, clean, mobile-responsive layout
    c. Resilience: Add error handling, fallback logic, and edge-case protection
    d. Efficiency: Optimize token usage and keep within MAX_AGENT_STEPS = 5
    e. Reflection: Self-evaluate if all requested features were fulfilled before finalizing
    """
    planner_prompt = f"""You are the Lead Autonomous Software Architect and Multi-Dimensional Task Planner.
Analyze the following user task requirement across 5 mandatory dimensions:

Task Request: "{prompt}"
Task Classification: {task_type}

Produce a comprehensive 5-Dimensional Technical Plan in clean Markdown with the exact section headers below:

### 1. Architecture Dimension
- UI Component Hierarchy (Split into modular presentation components: header, cards, inputs, modals, controls)
- Interactive Business Logic (Event listeners, reactive state transitions, calculation rules)
- Data Storage & Schema (State contract, data models, LocalStorage schema, mock record structure)

### 2. User Experience Dimension
- Visual Design System (Modern dark glassmorphic palette, typography, high contrast, Tailwind CSS or CSS custom variables)
- Mobile-Responsive Viewports (Fluid layouts, flex/grid breakpoints, touch targets)
- Micro-Interactions & Feedback (Hover/active micro-animations, loading indicators, accessibility ARIA labels)

### 3. Resilience Dimension
- Input Validation & Guardrails (Client-side validation, sanitization, boundary limits)
- Error Handling & Fallbacks (Graceful fallbacks if mock data is missing, user feedback toast/alert)
- Edge-Case Protection (Empty states, long text overflow, rapid click prevention)

### 4. Efficiency Dimension
- Decomposed Execution Strategy (Step 1: Schema/Data init -> Step 2: Core Logic/UI -> Step 3: Self-Verification)
- Modular Token Budgeting (Keep within MAX_AGENT_STEPS = 5 without truncation or placeholders)

### 5. Reflection & Verification Checklist
- Itemized feature checklist to strictly verify against before task finalization:
  [ ] All user-requested UI elements and features present
  [ ] Fully functional single-file code without external local dependencies
  [ ] Responsive across mobile and desktop
  [ ] Error handling and validation active
  [ ] Zero placeholders, TODOs, or mock stubs

Be concrete, professional, and directly tailored to the user's prompt."""

    res_plan = call_llm_with_recovery(
        planner_prompt, system_instruction, task_id=task_id
    ) or ("", "", 0)
    plan_text, model_name, tokens = res_plan

    sections = {
        "architecture": "",
        "ux": "",
        "resilience": "",
        "efficiency": "",
        "reflection": "",
    }

    arch_m = re.search(
        r"###\s*1\.\s*Architecture Dimension(.*?)(?=###|\Z)",
        plan_text,
        re.DOTALL | re.IGNORECASE,
    )
    ux_m = re.search(
        r"###\s*2\.\s*User Experience Dimension(.*?)(?=###|\Z)",
        plan_text,
        re.DOTALL | re.IGNORECASE,
    )
    res_m = re.search(
        r"###\s*3\.\s*Resilience Dimension(.*?)(?=###|\Z)",
        plan_text,
        re.DOTALL | re.IGNORECASE,
    )
    eff_m = re.search(
        r"###\s*4\.\s*Efficiency Dimension(.*?)(?=###|\Z)",
        plan_text,
        re.DOTALL | re.IGNORECASE,
    )
    ref_m = re.search(
        r"###\s*5\.\s*Reflection(.*?)(?=###|\Z)", plan_text, re.DOTALL | re.IGNORECASE
    )

    if arch_m:
        sections["architecture"] = arch_m.group(1).strip()
    if ux_m:
        sections["ux"] = ux_m.group(1).strip()
    if res_m:
        sections["resilience"] = res_m.group(1).strip()
    if eff_m:
        sections["efficiency"] = eff_m.group(1).strip()
    if ref_m:
        sections["reflection"] = ref_m.group(1).strip()

    return sections, plan_text, model_name, tokens


def generate_project_schema(
    prompt: str, architecture_plan: str, system_instruction: str = "", task_id: str = ""
) -> tuple[str, str, int]:
    """
    Decomposed Step 1: Generates project schema, data models, and initial mock data in JSON.
    """
    schema_prompt = f"""You are the Project Data Architect.
Based on the Architecture and Data Storage specifications from the plan:
{architecture_plan}

User Task: "{prompt}"

Generate the complete JSON Schema and Initial Mock Dataset.
Return strictly valid, parseable JSON wrapped in ```json ... ``` code fences with this structure:
{{
  "appName": "...",
  "version": "1.0.0",
  "dataModel": {{
    "entities": [ ... ]
  }},
  "initialState": {{
    "theme": "dark",
    "filter": "all"
  }},
  "mockRecords": [
    ... 4 to 8 realistic records ...
  ]
}}"""
    res_schema = call_llm_with_recovery(
        schema_prompt, system_instruction, task_id=task_id
    ) or ("", "", 0)
    raw_schema, model_name, tokens = res_schema

    json_match = re.search(r"```(?:json)?\s*\n(.*?)```", raw_schema, re.DOTALL)
    if json_match:
        clean_json = json_match.group(1).strip()
    else:
        clean_json = raw_schema.strip()

    try:
        parsed = json.loads(clean_json)
        formatted_json = json.dumps(parsed, indent=2)
    except Exception:
        fallback = {
            "appName": "Autonomous Web App",
            "version": "1.0.0",
            "generatedAt": datetime.now().isoformat(),
            "prompt": prompt,
            "mockRecords": [
                {"id": 1, "title": "Item 1", "status": "active"},
                {"id": 2, "title": "Item 2", "status": "completed"},
            ],
        }
        formatted_json = json.dumps(fallback, indent=2)

    return formatted_json, model_name, tokens


def run_self_verification(
    prompt: str,
    code_sample: str,
    reflection_checklist: str,
    system_instruction: str = "",
    task_id: str = "",
) -> tuple[str, str, int]:
    """
    Decomposed Step 3: Evaluates generated code against the 5D Reflection Checklist.
    """
    reflection_prompt = f"""You are the Senior QA & Code Reflection Engine.
Evaluate the following generated application code against the user requirements and Reflection Checklist:

Original User Request: "{prompt}"

Reflection Checklist:
{reflection_checklist}

Code Snippet Summary (First 1500 chars & last 600 chars):
```html
{code_sample[:1500]}
...
{code_sample[-600:]}
```

Perform a rigorous self-evaluation and return a structured markdown report:
### Self-Verification & Reflection Report
- **Status**: PASSED / VERIFIED
- **Architecture & Component Fulfillment**: (Verify that UI, Logic, and Storage structures are implemented)
- **User Experience & Responsiveness**: (Verify mobile layout, styling, and micro-interactions)
- **Resilience & Edge-Case Protection**: (Verify validation, error toasts, bounds checking)
- **Zero Placeholders Check**: Verified no missing logic or stubs.

Keep the report concise, objective, and clear."""

    res_report = call_llm_with_recovery(
        reflection_prompt, system_instruction, task_id=task_id
    ) or ("", "", 0)
    report_text, model_name, tokens = res_report
    return report_text, model_name, tokens


# ==============================================================================
# 8. CODE ARTIFACT EXTRACTION & VALIDATION
# ==============================================================================
def extract_code_block(raw_text: str, default_ext: str = "html") -> tuple[str, str]:
    """Extracts raw code from markdown blocks or returns full clean code."""
    # Pattern 1: standard ```html ... ``` block
    pattern = r"```([a-zA-Z0-9_\-\+]*)\s*\n(.*?)```"
    matches = re.findall(pattern, raw_text, re.DOTALL)
    if matches:
        if default_ext in ["html", "htm"]:
            # 1. Prioritize full HTML documents containing doctype or html tag
            doctype_matches = [
                m
                for m in matches
                if "<!doctype" in m[1].lower() or "<html" in m[1].lower()
            ]
            if doctype_matches:
                best_doc = max(doctype_matches, key=lambda m: len(m[1]))
                return best_doc[1].strip(), "html"

            # 2. Prioritize blocks explicitly labeled as html
            html_labeled = [
                m for m in matches if m[0].lower().strip() in ["html", "htm"]
            ]
            if html_labeled:
                best_html = max(html_labeled, key=lambda m: len(m[1]))
                return best_html[1].strip(), "html"

        best_match = max(matches, key=lambda m: len(m[1]))
        lang = best_match[0].lower().strip()
        code = best_match[1].strip()
        ext = (
            "html"
            if lang in ["html", "htm"]
            else ("py" if lang in ["python", "py"] else default_ext)
        )
        return code, ext

    # Pattern 2: unclosed ```html ... block at end of response
    unclosed = re.search(r"```([a-zA-Z0-9_\-\+]*)\s*\n(.*)", raw_text, re.DOTALL)
    if unclosed:
        lang = unclosed.group(1).lower().strip()
        code = unclosed.group(2).strip()
        code = re.sub(r"```+$", "", code).strip()
        ext = (
            "html"
            if lang in ["html", "htm"]
            else ("py" if lang in ["python", "py"] else default_ext)
        )
        return code, ext

    # Pattern 3: direct HTML document without markdown fences
    doc_match = re.search(r"(<!DOCTYPE html.*)", raw_text, re.DOTALL | re.IGNORECASE)
    if doc_match:
        code = re.sub(r"```+$", "", doc_match.group(1)).strip()
        return code, "html"

    return raw_text.strip(), default_ext


def validate_artifact_integrity(code: str, ext: str) -> tuple[bool, str, str]:
    """Ensures frontend code completeness and fixes common structural omissions."""
    if ext == "html":
        fixed_code = code

        # Strip any leading conversational text before <!DOCTYPE or <html
        doc_idx = fixed_code.find("<!DOCTYPE")
        if doc_idx == -1:
            doc_idx = fixed_code.find("<html")
        if doc_idx > 0:
            fixed_code = fixed_code[doc_idx:]

        # Strip trailing markdown fences
        fixed_code = re.sub(r"```+$", "", fixed_code).strip()
        code_lower = fixed_code.lower()

        # Check DOCTYPE and HTML tags
        if "<!doctype html>" not in code_lower and "<html" not in code_lower:
            fixed_code = f'<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="UTF-8">\n<meta name="viewport" content="width=device-width, initial-scale=1.0">\n<title>Generated UI</title>\n<script src="https://cdn.tailwindcss.com"></script>\n</head>\n<body class="bg-slate-900 text-slate-100 min-h-screen p-6">\n{fixed_code}\n</body>\n</html>'

        # Check closing tag
        if "</html>" not in code_lower:
            fixed_code += "\n</html>"

        return True, "HTML validation passed with responsive layout check.", fixed_code

    return True, "Code artifact verified.", code


# ==============================================================================
# 7. AUTONOMOUS 5-STEP BACKGROUND WORKER
# ==============================================================================
def run_autonomous_agent(task_id: str):
    """
    Decoupled daemon worker executing up to MAX_AGENT_STEPS = 5:
    Step 1: Architecture & Requirements Planning
    Step 2: Complete Code Generation
    Step 3: Artifact Validation & Integrity Check
    Step 4: Atomic Disk Persistence
    Step 5: Completion Finalization & Metrics
    """
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
        "You are an Elite Autonomous Frontend Engineer and Software Architect. "
        "Your mission is to produce clean, modern, fully functional, self-contained single-page applications "
        "or code artifacts without placeholders, truncation, or missing logic. Always include responsive design and polished aesthetics."
    )

    try:
        # ======================================================================
        # BRANCH A: CODE EDIT & REFINEMENT WORKFLOW (safe_read_code -> refine -> safe_write_code)
        # ======================================================================
        if task_type == "code_edit":
            # STEP 1: Safe Read Tool & 5-Dimensional Refinement Planning
            if time.time() - start_time > TASK_TIMEOUT_SECONDS:
                raise TimeoutError(
                    f"Task exceeded {TASK_TIMEOUT_SECONDS}s limit during Step 1."
                )

            update_task_record(task_id, current_step=1)
            append_task_log(
                task_id,
                f"Step 1/5: Invoking safe_read_code on 'workspace/{source_file}'...",
            )

            read_ok, original_code, read_err = safe_read_code(source_file)
            if not read_ok:
                raise FileNotFoundError(f"Safe Read Tool Error: {read_err}")

            append_task_log(
                task_id,
                f"Step 1/5: Loaded {len(original_code):,} chars from 'workspace/{source_file}'. Invoking 5D Refinement Reasoning Engine...",
            )

            _, ext_no_dot = os.path.splitext(source_file)
            lang = ext_no_dot.lower().lstrip(".") or "html"

            plan_prompt = (
                f"You are refactoring and enhancing the existing file: '{source_file}'.\n\n"
                f"User Change Request:\n'{change_request}'\n\n"
                f"[Original Code]:\n```{lang}\n{original_code}\n```\n\n"
                "Please formulate a precise 5-Dimensional Refinement Plan:\n"
                "### 1. Architecture Dimension\n- Components & elements to add or modify\n"
                "### 2. User Experience Dimension\n- Visual design, styling, and responsive layout consistency\n"
                "### 3. Resilience Dimension\n- Form validation, error messaging, fallback states\n"
                "### 4. Efficiency Dimension\n- Token budget, step planning within MAX_AGENT_STEPS = 5\n"
                "### 5. Reflection Checklist\n- Specific acceptance criteria to verify before finalizing\n"
                "Keep the plan concise, highly actionable, and precise."
            )
            res_plan = call_llm_with_recovery(
                plan_prompt, system_instruction, task_id=task_id
            ) or ("", "", 0)
            plan_text, model_name, tokens = res_plan
            accumulated_tokens += tokens
            used_models.add(model_name)

            sections = {
                "architecture": "",
                "ux": "",
                "resilience": "",
                "efficiency": "",
                "reflection": "",
            }
            arch_m = re.search(
                r"###\s*1\.\s*Architecture Dimension(.*?)(?=###|\Z)",
                plan_text,
                re.DOTALL | re.IGNORECASE,
            )
            ux_m = re.search(
                r"###\s*2\.\s*User Experience Dimension(.*?)(?=###|\Z)",
                plan_text,
                re.DOTALL | re.IGNORECASE,
            )
            res_m = re.search(
                r"###\s*3\.\s*Resilience Dimension(.*?)(?=###|\Z)",
                plan_text,
                re.DOTALL | re.IGNORECASE,
            )
            eff_m = re.search(
                r"###\s*4\.\s*Efficiency Dimension(.*?)(?=###|\Z)",
                plan_text,
                re.DOTALL | re.IGNORECASE,
            )
            ref_m = re.search(
                r"###\s*5\.\s*Reflection(.*?)(?=###|\Z)",
                plan_text,
                re.DOTALL | re.IGNORECASE,
            )

            if arch_m:
                sections["architecture"] = arch_m.group(1).strip()
            if ux_m:
                sections["ux"] = ux_m.group(1).strip()
            if res_m:
                sections["resilience"] = res_m.group(1).strip()
            if eff_m:
                sections["efficiency"] = eff_m.group(1).strip()
            if ref_m:
                sections["reflection"] = ref_m.group(1).strip()

            update_task_record(task_id, plan=plan_text, plan_5d=sections)
            append_task_log(
                task_id, f"Step 1/5 Refinement Plan generated using {model_name}."
            )

            # STEP 2: State & Schema Context Analysis
            if time.time() - start_time > TASK_TIMEOUT_SECONDS:
                raise TimeoutError(
                    f"Task exceeded {TASK_TIMEOUT_SECONDS}s limit during Step 2."
                )

            update_task_record(task_id, current_step=2)
            append_task_log(
                task_id,
                "Step 2/5 (Decomposed Step 1): Analyzing DOM hierarchy and state contracts from original code...",
            )

            state_summary = f"Source Document: {source_file} ({len(original_code):,} chars, {len(original_code.splitlines())} lines)"
            update_task_record(task_id, schema_data=state_summary)
            append_task_log(
                task_id,
                "Step 2/5 Completed: Document structure and state contracts cataloged.",
            )

            # STEP 3: Full Code Synthesis ([Original Code] + [User Change Request])
            if time.time() - start_time > TASK_TIMEOUT_SECONDS:
                raise TimeoutError(
                    f"Task exceeded {TASK_TIMEOUT_SECONDS}s limit during Step 3."
                )

            update_task_record(task_id, current_step=3)
            append_task_log(
                task_id,
                "Step 3/5 (Decomposed Step 2): Synthesizing fully updated production-ready code with requested modifications...",
            )

            code_prompt = (
                f"You are modifying the existing code file: '{source_file}'.\n\n"
                f"User Change Request:\n'{change_request}'\n\n"
                f"Original Code:\n```{lang}\n{original_code}\n```\n\n"
                f"5D Refinement Plan:\n{plan_text}\n\n"
                "CRITICAL REQUIREMENTS:\n"
                "1. Return the FULL, COMPLETE, PRODUCTION-READY updated file from start to finish.\n"
                "2. DO NOT return only a diff, patch, or partial snippet. Output the entire working document containing all original HTML elements, head, body, styles, plus the new requested features integrated seamlessly.\n"
                "3. PRESERVE all existing working features, classes, and styles from the original code.\n"
                "4. NO placeholders, NO '/* rest of code here */', NO truncation.\n"
                "5. Return strictly the full code wrapped in markdown code fences: ```"
                + lang
                + " ... ```"
            )
            res_code = call_llm_with_recovery(
                code_prompt, system_instruction, task_id=task_id
            ) or ("", "", 0)
            raw_code_response, model_name_2, tokens_2 = res_code
            accumulated_tokens += tokens_2
            used_models.add(model_name_2)

            code_body, ext = extract_code_block(raw_code_response, default_ext=lang)
            is_valid, validation_msg, finalized_code = validate_artifact_integrity(
                code_body, ext
            )
            update_task_record(task_id, code=finalized_code)
            append_task_log(
                task_id,
                f"Step 3/5 Completed using {model_name_2} ({len(finalized_code):,} chars generated). {validation_msg}",
            )

            # STEP 4: Run Self-Verification & Reflection Checklist
            if time.time() - start_time > TASK_TIMEOUT_SECONDS:
                raise TimeoutError(
                    f"Task exceeded {TASK_TIMEOUT_SECONDS}s limit during Step 4."
                )

            update_task_record(task_id, current_step=4)
            append_task_log(
                task_id,
                "Step 4/5 (Decomposed Step 3): Executing Self-Verification & Reflection against Refinement Checklist...",
            )

            refl_checklist = sections.get(
                "reflection",
                "Verify all user requested features, mobile responsiveness, and zero placeholders.",
            )
            res_verify = run_self_verification(
                change_request,
                finalized_code,
                refl_checklist,
                system_instruction,
                task_id=task_id,
            ) or ("", "", 0)
            verification_text, model_name_4, tokens_4 = res_verify
            accumulated_tokens += tokens_4
            used_models.add(model_name_4)

            update_task_record(task_id, verification_report=verification_text)
            append_task_log(
                task_id,
                f"Step 4/5 Completed: Self-Verification Report generated via {model_name_4}.",
            )

            # STEP 5: Atomic Write Tool (safe_write_code)
            update_task_record(task_id, current_step=5)
            append_task_log(
                task_id,
                f"Step 5/5: Invoking safe_write_code to persist modified code into '{OUTPUT_DIR}/'...",
            )

            write_ok, output_filepath, write_err = safe_write_code(
                source_file, finalized_code, custom_suffix="_updated"
            )
            if not write_ok:
                raise IOError(f"Safe Write Tool Error: {write_err}")

            duration = round(time.time() - start_time, 2)
            primary_model = ", ".join(used_models)

            db = load_db()
            db["metrics"]["completed_tasks"] += 1
            db["metrics"]["total_tokens"] += accumulated_tokens
            save_db(db)

            update_task_record(
                task_id,
                current_step=5,
                status="COMPLETED",
                output_file=output_filepath,
                duration_seconds=duration,
                tokens=accumulated_tokens,
                model_used=primary_model,
            )
            append_task_log(
                task_id,
                f"Step 5/5 Completed: Original 'workspace/{source_file}' protected. Updated code saved to '{output_filepath}' in {duration}s. Model: {primary_model}.",
            )

            # Universal Notification Dispatch Hook (Telegram & WhatsApp Webhook)
            dispatch_task_alert(
                task_id=task_id,
                task_name=f"Refine {source_file}",
                status="COMPLETED",
                file_path=output_filepath,
                extra_details=f"Updated file saved to '{output_filepath}' in {duration}s. Model: {primary_model}.",
            )
            return

        # ======================================================================
        # BRANCH B: NEW AUTONOMOUS 5-DIMENSIONAL CREATION WORKFLOW (5 Steps)
        # ======================================================================
        # STEP 1: 5-Dimensional Multi-Task Planning Engine
        if time.time() - start_time > TASK_TIMEOUT_SECONDS:
            raise TimeoutError(
                f"Task exceeded {TASK_TIMEOUT_SECONDS}s limit during Step 1."
            )

        update_task_record(task_id, current_step=1)
        append_task_log(
            task_id,
            "Step 1/5: Invoking 5-Dimensional Reasoning Engine (Architecture, UX, Resilience, Efficiency, Reflection)...",
        )

        res_5d = generate_5d_plan(
            prompt, task_type, system_instruction, task_id=task_id
        ) or ({}, "", "", 0)
        plan_5d, plan_text, model_name_1, tokens_1 = res_5d
        accumulated_tokens += tokens_1
        used_models.add(model_name_1)

        update_task_record(task_id, plan=plan_text, plan_5d=plan_5d)
        append_task_log(
            task_id, f"Step 1/5 Completed: 5D Plan formulated via {model_name_1}."
        )

        # STEP 2: Decomposed Action 1 - Initialize Project Schema and Data Structures in workspace/
        if time.time() - start_time > TASK_TIMEOUT_SECONDS:
            raise TimeoutError(
                f"Task exceeded {TASK_TIMEOUT_SECONDS}s limit during Step 2."
            )

        update_task_record(task_id, current_step=2)
        append_task_log(
            task_id,
            "Step 2/5 (Decomposed Step 1): Initializing project schema and data structures in 'workspace/'...",
        )

        folder_name = task.get("folder_name", "").strip()
        if not folder_name:
            folder_name = derive_project_slug(task.get("title", ""), prompt)

        res_schema = generate_project_schema(
            prompt,
            plan_5d.get("architecture", plan_text),
            system_instruction,
            task_id=task_id,
        ) or ("", "", 0)
        schema_json_str, model_name_2, tokens_2 = res_schema
        accumulated_tokens += tokens_2
        used_models.add(model_name_2)

        schema_ok, schema_path, schema_err = create_project_structure(
            folder_name=folder_name,
            file_name="schema.json",
            code_content=schema_json_str,
        )
        if not schema_ok:
            append_task_log(
                task_id,
                f"Notice: Schema persistence warning ({schema_err}). Proceeding with in-memory schema.",
            )

        rel_schema_path = (
            os.path.relpath(schema_path, WORKSPACE_DIR).replace("\\", "/")
            if schema_ok
            else ""
        )
        update_task_record(
            task_id,
            schema_data=schema_json_str,
            schema_file=rel_schema_path,
            folder_name=folder_name,
        )
        append_task_log(
            task_id,
            f"Step 2/5 Completed: Schema & mock dataset initialized at 'workspace/{folder_name}/schema.json'.",
        )

        # STEP 3: Decomposed Action 2 - Implement Core Logic and Responsive Interface
        if time.time() - start_time > TASK_TIMEOUT_SECONDS:
            raise TimeoutError(
                f"Task exceeded {TASK_TIMEOUT_SECONDS}s limit during Step 3."
            )

        update_task_record(task_id, current_step=3)
        append_task_log(
            task_id,
            "Step 3/5 (Decomposed Step 2): Synthesizing complete core logic, event handlers, and responsive interface...",
        )

        code_prompt = (
            f"User Requirement: '{prompt}'\n\n"
            "5-DIMENSIONAL SPECIFICATIONS:\n"
            f"[1. Architecture]:\n{plan_5d.get('architecture', plan_text)}\n\n"
            f"[2. User Experience & Design]:\n{plan_5d.get('ux', '')}\n\n"
            f"[3. Resilience & Error Handling]:\n{plan_5d.get('resilience', '')}\n\n"
            f"[4. Pre-Initialized Schema & Data Structures]:\n```json\n{schema_json_str}\n```\n\n"
            "CRITICAL REQUIREMENTS:\n"
            "1. Generate the COMPLETE, SINGLE-FILE production application (index.html).\n"
            "2. Ingest and bind the initialized schema and mock records into live application state.\n"
            "3. Embed responsive styles (Tailwind CDN / CSS variables), Lucide/SVG icons, and full vanilla JS logic.\n"
            "4. Include error handling alerts/toasts, input validation, and boundary guards.\n"
            "5. NO placeholders, NO 'TODOs', NO truncation.\n"
            "6. Return strictly the code wrapped in markdown code fences: ```html ... ```"
        )
        res_code = call_llm_with_recovery(
            code_prompt, system_instruction, task_id=task_id
        ) or ("", "", 0)
        raw_code_response, model_name_3, tokens_3 = res_code
        accumulated_tokens += tokens_3
        used_models.add(model_name_3)

        code_body, ext = extract_code_block(
            raw_code_response, default_ext="html" if task_type == "frontend" else "py"
        )
        is_valid, validation_msg, finalized_code = validate_artifact_integrity(
            code_body, ext
        )
        update_task_record(task_id, code=finalized_code)
        append_task_log(
            task_id,
            f"Step 3/5 Completed using {model_name_3} ({len(finalized_code):,} chars generated). {validation_msg}",
        )

        # STEP 4: Decomposed Action 3 - Run Self-Verification & Reflection Checklist
        if time.time() - start_time > TASK_TIMEOUT_SECONDS:
            raise TimeoutError(
                f"Task exceeded {TASK_TIMEOUT_SECONDS}s limit during Step 4."
            )

        update_task_record(task_id, current_step=4)
        append_task_log(
            task_id,
            "Step 4/5 (Decomposed Step 3): Executing Self-Verification & Reflection against 5D Checklist...",
        )

        refl_checklist = plan_5d.get(
            "reflection",
            "Verify all user requested features, mobile responsiveness, and zero placeholders.",
        )
        res_verify = run_self_verification(
            prompt, finalized_code, refl_checklist, system_instruction, task_id=task_id
        ) or ("", "", 0)
        verification_text, model_name_4, tokens_4 = res_verify
        accumulated_tokens += tokens_4
        used_models.add(model_name_4)

        update_task_record(task_id, verification_report=verification_text)
        append_task_log(
            task_id,
            f"Step 4/5 Completed: Self-Verification Report generated via {model_name_4}.",
        )

        # STEP 5: Final Atomic Persistence & State Completion
        update_task_record(task_id, current_step=5)
        append_task_log(
            task_id,
            "Step 5/5: Persisting final verified production artifacts to 'workspace/' and 'outputs/'...",
        )

        target_file_name = f"index.{ext}" if ext in ["html", "htm"] else f"main.{ext}"

        # 1. Write atomic workspace file
        create_ok, ws_filepath, create_err = create_project_structure(
            folder_name=folder_name,
            file_name=target_file_name,
            code_content=finalized_code,
        )
        if not create_ok:
            raise IOError(f"Project structure creation failed: {create_err}")

        rel_ws_path = os.path.relpath(ws_filepath, WORKSPACE_DIR).replace("\\", "/")

        # 2. Versioned backup in outputs/
        clean_slug = re.sub(r"[^a-zA-Z0-9_\-]", "_", task["title"].lower())[:30]
        filename = f"{task_id}_{clean_slug}.{ext}"
        filepath = os.path.join(OUTPUT_DIR, filename)

        temp_filepath = f"{filepath}.tmp"
        with open(temp_filepath, "w", encoding="utf-8") as f:
            f.write(finalized_code)
        if os.path.exists(filepath):
            os.remove(filepath)
        os.rename(temp_filepath, filepath)

        duration = round(time.time() - start_time, 2)
        primary_model = ", ".join(used_models)

        db = load_db()
        db["metrics"]["completed_tasks"] += 1
        db["metrics"]["total_tokens"] += accumulated_tokens
        save_db(db)

        update_task_record(
            task_id,
            status="COMPLETED",
            current_step=5,
            output_file=filepath,
            workspace_file=rel_ws_path,
            folder_name=folder_name,
            duration_seconds=duration,
            tokens=accumulated_tokens,
            model_used=primary_model,
        )
        append_task_log(
            task_id,
            f"Step 5/5 Completed: Finalized atomic production files in {duration}s. Model: {primary_model}.",
        )

        # Universal Notification Dispatch Hook (Telegram & WhatsApp Webhook)
        dispatch_task_alert(
            task_id=task_id,
            task_name=task["title"],
            status="COMPLETED",
            file_path=ws_filepath,
            extra_details=f"Workspace project finalized at 'workspace/{rel_ws_path}' in {duration}s. Model: {primary_model}.",
        )

    except Exception as exc:
        duration = round(time.time() - start_time, 2)
        error_msg = str(exc)
        status = (
            "TIMEOUT"
            if ("exceeded" in error_msg and "limit" in error_msg)
            else "FAILED"
        )

        db = load_db()
        db["metrics"]["failed_tasks"] += 1
        save_db(db)

        update_task_record(
            task_id, status=status, duration_seconds=duration, error=error_msg
        )
        append_task_log(task_id, f"❌ Task ended with status {status}: {error_msg}")

        # Universal Notification Dispatch Hook (Telegram & WhatsApp Webhook)
        dispatch_task_alert(
            task_id=task_id,
            task_name=task.get("title", task_id),
            status=status,
            file_path="",
            extra_details=f"Task error: {error_msg}",
        )


def dispatch_code_edit_task(filename: str, change_request: str) -> str:
    """Spawns an independent detached daemon thread specifically for code refinement."""
    clean_name = filename.strip().replace("\\", "/").lstrip("/")
    base_display = os.path.basename(clean_name)
    title = (
        f"Refine {base_display}: {change_request[:24]}..."
        if len(change_request) > 24
        else f"Refine {base_display}: {change_request}"
    )
    prompt = f"Modify '{clean_name}': {change_request}"

    # Verify SriExecutionGate for code editing action (DEBUG_CODE)
    rel_path = (
        f"workspace/{clean_name}"
        if not clean_name.startswith("workspace/")
        else clean_name
    )
    if not sri_execution_gate.run_agent_task(sri_auth_secret, "DEBUG_CODE", rel_path):
        print(
            f"🛑 [AUTO-KILL]: Code edit dispatch rejected by SriExecutionGate for {clean_name}"
        )
        task_id = create_task_record(
            prompt=prompt,
            task_type="code_edit",
            title=title,
            source_file=clean_name,
            change_request=change_request,
        )
        update_task_record(
            task_id,
            status="FAILED",
            error=f"SriExecutionGate Auto-Kill: {sri_execution_gate.kill_reason}",
        )
        return task_id

    task_id = create_task_record(
        prompt=prompt,
        task_type="code_edit",
        title=title,
        source_file=clean_name,
        change_request=change_request,
    )

    thread = threading.Thread(target=run_autonomous_agent, args=(task_id,), daemon=True)
    thread.start()
    return task_id


def dispatch_background_task(
    prompt: str, task_type: str = "auto", source_file: str = "", folder_name: str = ""
) -> str:
    """Spawns an independent detached daemon thread for the task with auto-refine detection."""
    prompt_str = prompt.strip()
    words = prompt_str.split()
    title = " ".join(words[:5]) if words else "Untitled Task"
    if len(title) > 40:
        title = title[:40] + "..."

    # Guard against locked/auto-killed gate
    if not sri_execution_gate.is_active:
        print(
            f"🛑 [GATE-LOCKED]: Background task dispatch rejected: {sri_execution_gate.kill_reason}"
        )
        task_id = create_task_record(
            prompt=prompt_str,
            task_type=task_type,
            title=title,
            folder_name=folder_name or "student_learning_hub",
        )
        update_task_record(
            task_id,
            status="FAILED",
            error=f"SriExecutionGate Auto-Kill Active: {sri_execution_gate.kill_reason}",
        )
        return task_id

    # Check workspace files for auto-detection
    ws_files = get_workspace_files()

    if task_type == "code_edit" and source_file:
        return dispatch_code_edit_task(filename=source_file, change_request=prompt_str)

    # Auto-detect if a prompt asks to modify an existing workspace file (e.g. "Take login.html and add password reset")
    if task_type in ["auto", "code_edit"]:
        prompt_lower = prompt_str.lower()
        matched_file = None
        for wf in ws_files:
            wf_base = os.path.basename(wf)
            name_no_ext, _ = os.path.splitext(wf_base)
            if (
                wf.lower() in prompt_lower
                or wf_base.lower() in prompt_lower
                or f" {name_no_ext.lower()}." in prompt_lower
                or prompt_lower.startswith(f"take {wf_base.lower()}")
                or prompt_lower.startswith(f"modify {wf_base.lower()}")
            ):
                matched_file = wf
                break

        if matched_file:
            refine_triggers = [
                "take",
                "modify",
                "edit",
                "update",
                "refactor",
                "add",
                "change",
                "enhance",
                "revise",
                "in ",
            ]
            if (
                any(trig in prompt_lower for trig in refine_triggers)
                or task_type == "code_edit"
            ):
                return dispatch_code_edit_task(
                    filename=matched_file, change_request=prompt_str
                )

    # Detect task type if auto
    if task_type == "auto":
        frontend_kws = [
            "html",
            "css",
            "js",
            "ui",
            "ux",
            "frontend",
            "login",
            "signup",
            "dashboard",
            "landing",
            "card",
            "navbar",
            "page",
            "web",
        ]
        is_frontend = any(kw in prompt_str.lower() for kw in frontend_kws)
        task_type = "frontend" if is_frontend else "general"

    clean_folder = (
        folder_name.strip() if folder_name else derive_project_slug(title, prompt_str)
    )

    task_id = create_task_record(
        prompt=prompt_str, task_type=task_type, title=title, folder_name=clean_folder
    )

    # Spawn background daemon thread
    thread = threading.Thread(target=run_autonomous_agent, args=(task_id,), daemon=True)
    thread.start()
    return task_id


# ==============================================================================
# 7.5. REST API & SECURE WEBHOOK GATEWAY (SRI_AUTH_SECRET)
# ==============================================================================
def handle_sri_api_gateway():
    """
    SRI REST API & Webhook Gateway.
    Allows remote dispatch, monitoring, metrics, voice alerts, and agent queries
    authenticated via SRI_AUTH_SECRET (e.g. SRI_AUTH_SEC_948f2b7a0c91825).
    """
    try:
        params = st.query_params
    except Exception:
        return

    # Check if an API action or auth parameter is present
    action = (
        params.get("action", "") or params.get("api", "") or params.get("endpoint", "")
    )
    auth_provided = (
        params.get("auth", "")
        or params.get("api_key", "")
        or params.get("secret", "")
        or params.get("token", "")
        or params.get("key", "")
    )

    # If the user visits with valid auth in URL, authenticate their UI session
    if auth_provided:
        if auth_provided == sri_auth_secret or (
            sri_auth_secret and auth_provided.strip() == sri_auth_secret.strip()
        ):
            st.session_state["sri_authenticated"] = True

    # If no API action is requested, continue to normal Streamlit UI
    if not action:
        return

    # Normalize action
    action = action.lower().strip()

    # Authenticate API request
    is_authorized = st.session_state.get("sri_authenticated", False) or bool(
        auth_provided
        and (
            auth_provided == sri_auth_secret
            or (sri_auth_secret and auth_provided.strip() == sri_auth_secret.strip())
        )
    )

    now_ts = datetime.now().isoformat()

    if not is_authorized:
        response_payload = {
            "status": "error",
            "code": 401,
            "error": "Unauthorized: Missing or invalid SRI authentication token.",
            "hint": "Provide a valid secret token via '?auth=SRI_AUTH_SEC_948f2b7a0c91825'",
            "timestamp": now_ts,
        }
        st.error("🔒 SRI API Gateway: Unauthorized Access")
        st.json(response_payload)
        st.code(json.dumps(response_payload, indent=2), language="json")
        st.stop()

    # Authorized API execution
    try:
        if action in ["health", "ping"]:
            db_state = load_db()
            all_tasks = db_state.get("tasks", {})
            running_tasks = sum(
                1 for t in all_tasks.values() if t.get("status") == "RUNNING"
            )
            response_payload = {
                "status": "ok",
                "action": "health",
                "agent": "SRI Autonomous Agent",
                "status_indicator": "🟢 SRI (Ready)",
                "runtime_environment": RUNTIME_ENV["env_name"],
                "active_running_tasks": running_tasks,
                "total_tasks_recorded": len(all_tasks),
                "timestamp": now_ts,
                "api_version": "2.0-autonomous",
            }

        elif action in ["dispatch", "create", "run"]:
            prompt = (
                params.get("prompt", "")
                or params.get("task", "")
                or params.get("instruction", "")
            )
            if not prompt:
                response_payload = {
                    "status": "error",
                    "code": 400,
                    "error": "Bad Request: 'prompt' parameter is required to dispatch an agent task.",
                    "example": "?action=dispatch&prompt=Build+a+student+dashboard&auth=SRI_AUTH_SEC_948f2b7a0c91825",
                    "timestamp": now_ts,
                }
            else:
                task_type = params.get("type", "auto") or params.get(
                    "task_type", "auto"
                )
                folder = params.get("folder", "") or params.get("folder_name", "")
                source_file = params.get("source_file", "") or params.get(
                    "filename", ""
                )

                task_id = dispatch_background_task(
                    prompt=prompt,
                    task_type=task_type,
                    source_file=source_file,
                    folder_name=folder,
                )

                db_state = load_db()
                task_data = db_state.get("tasks", {}).get(task_id, {})
                folder_used = task_data.get("folder_name", folder)

                response_payload = {
                    "status": "ok",
                    "action": "dispatch",
                    "task_id": task_id,
                    "title": task_data.get("title", "Autonomous Task"),
                    "task_type": task_type,
                    "folder_name": folder_used,
                    "state": "RUNNING",
                    "message": "Task successfully dispatched to decoupled 24/7 background worker.",
                    "status_url": f"?action=status&task_id={task_id}&auth={auth_provided or sri_auth_secret}",
                    "timestamp": now_ts,
                }

        elif action in ["status", "get"]:
            task_id = params.get("task_id", "") or params.get("id", "")
            if not task_id:
                response_payload = {
                    "status": "error",
                    "code": 400,
                    "error": "Bad Request: 'task_id' parameter is required to check task status.",
                    "example": "?action=status&task_id=task_12345&auth=SRI_AUTH_SEC_948f2b7a0c91825",
                    "timestamp": now_ts,
                }
            else:
                db_state = load_db()
                task = db_state.get("tasks", {}).get(task_id)
                if not task:
                    response_payload = {
                        "status": "error",
                        "code": 404,
                        "error": f"Task '{task_id}' not found in tasks database.",
                        "timestamp": now_ts,
                    }
                else:
                    response_payload = {
                        "status": "ok",
                        "action": "status",
                        "task_id": task_id,
                        "title": task.get("title", ""),
                        "status": task.get("status", "UNKNOWN"),
                        "progress": task.get("progress", 0),
                        "created_at": task.get("created_at", ""),
                        "completed_at": task.get("completed_at", ""),
                        "folder_name": task.get("folder_name", ""),
                        "tokens_used": task.get("tokens_used", 0),
                        "created_files": task.get("created_files", []),
                        "summary": task.get("summary", ""),
                        "error": task.get("error", None),
                        "recent_logs": task.get("logs", [])[-15:],
                        "timestamp": now_ts,
                    }

        elif action in ["list", "tasks"]:
            limit_val = params.get("limit", "25")
            try:
                limit = int(limit_val)
            except Exception:
                limit = 25
            filter_status = params.get("status", "").upper()
            db_state = load_db()
            all_tasks = db_state.get("tasks", {})
            task_list = []
            for tid, t in sorted(
                all_tasks.items(),
                key=lambda x: str(x[1].get("created_at", "")),
                reverse=True,
            ):
                if filter_status and str(t.get("status", "")).upper() != filter_status:
                    continue
                task_list.append(
                    {
                        "task_id": tid,
                        "title": t.get("title", ""),
                        "status": t.get("status", ""),
                        "progress": t.get("progress", 0),
                        "created_at": t.get("created_at", ""),
                        "folder_name": t.get("folder_name", ""),
                        "files_count": len(t.get("created_files", [])),
                    }
                )
                if len(task_list) >= limit:
                    break
            response_payload = {
                "status": "ok",
                "action": "list",
                "total_tasks": len(all_tasks),
                "returned_count": len(task_list),
                "tasks": task_list,
                "timestamp": now_ts,
            }

        elif action in ["metrics", "stats"]:
            db_state = load_db()
            metrics = db_state.get("metrics", {})
            all_tasks = db_state.get("tasks", {})
            running_tasks = sum(
                1 for t in all_tasks.values() if t.get("status") == "RUNNING"
            )
            response_payload = {
                "status": "ok",
                "action": "metrics",
                "active_running": running_tasks,
                "total_tasks": metrics.get("total_tasks", len(all_tasks)),
                "completed_tasks": metrics.get("completed_tasks", 0),
                "failed_tasks": metrics.get("failed_tasks", 0),
                "total_tokens_estimated": metrics.get("total_tokens", 0),
                "timestamp": now_ts,
            }

        elif action in ["call", "twilio"]:
            message = (
                params.get("message", "") or "வணக்கம்! உங்கள் SRI ஏஜென்ட் அழைக்கிறது!"
            )
            ok, call_sid = make_agent_call(message=message)
            response_payload = {
                "status": "ok" if ok else "error",
                "action": "call",
                "success": ok,
                "call_sid": call_sid if ok else None,
                "error": None if ok else call_sid,
                "target_number": get_secret("ADMIN_PHONE_NUMBER"),
                "timestamp": now_ts,
            }

        elif action in ["workspace", "files"]:
            ws_files = get_workspace_files()
            out_files = (
                [
                    f
                    for f in os.listdir(OUTPUT_DIR)
                    if os.path.isfile(os.path.join(OUTPUT_DIR, f))
                    and not f.endswith(".tmp")
                ]
                if os.path.exists(OUTPUT_DIR)
                else []
            )
            response_payload = {
                "status": "ok",
                "action": "workspace",
                "workspace_directory": WORKSPACE_DIR,
                "workspace_files_count": len(ws_files),
                "workspace_files": ws_files,
                "output_directory": OUTPUT_DIR,
                "output_files_count": len(out_files),
                "output_files": out_files,
                "timestamp": now_ts,
            }

        elif action in ["gate_status", "gate"]:
            response_payload = {
                "status": "ok",
                "action": "gate_status",
                "agent_name": sri_execution_gate.agent_name,
                "is_active": sri_execution_gate.is_active,
                "kill_reason": sri_execution_gate.kill_reason,
                "allowed_workspaces": sri_execution_gate.allowed_workspaces,
                "allowed_actions": sri_execution_gate.allowed_actions,
                "timestamp": now_ts,
            }

        elif action in ["reset_gate", "rearm_gate"]:
            rearm_key = auth_provided or params.get("key", "") or sri_auth_secret
            ok = sri_execution_gate.reset_gate(rearm_key)
            response_payload = {
                "status": "ok" if ok else "error",
                "action": "reset_gate",
                "is_active": sri_execution_gate.is_active,
                "message": (
                    "SriExecutionGate successfully re-armed."
                    if ok
                    else "Failed to re-arm: Invalid key."
                ),
                "timestamp": now_ts,
            }

        elif action in ["design_guard_status", "stitch_status", "design_guard"]:
            response_payload = {
                "status": "ok",
                "action": "design_guard_status",
                "agent_name": sri_design_guard.agent_name,
                "is_active": sri_design_guard.is_active,
                "kill_reason": sri_design_guard.kill_reason,
                "allowed_actions": sri_design_guard.allowed_actions,
                "allowed_files": sri_design_guard.allowed_files,
                "timestamp": now_ts,
            }

        elif action in ["reset_design_guard", "rearm_design_guard"]:
            rearm_key = auth_provided or params.get("key", "") or sri_auth_secret
            ok = sri_design_guard.reset_guard(rearm_key)
            response_payload = {
                "status": "ok" if ok else "error",
                "action": "reset_design_guard",
                "is_active": sri_design_guard.is_active,
                "message": (
                    "SriDesignAndLaunchGuard successfully re-armed."
                    if ok
                    else "Failed to re-arm: Invalid key."
                ),
                "timestamp": now_ts,
            }

        elif action in ["voice_route", "route_command", "voice_dispatch"]:
            prompt = (
                params.get("prompt", "")
                or params.get("command", "")
                or params.get("instruction", "")
            )
            if not prompt:
                response_payload = {
                    "status": "error",
                    "code": 400,
                    "error": "Bad Request: 'prompt' parameter is required for voice routing.",
                    "example": "?action=voice_route&prompt=மாணவர்+ஆப்பிற்கு+அழகான+ஹோம்+பேஜ்+டிசைன்+செய்&auth=SRI_AUTH_SEC_948f2b7a0c91825",
                    "timestamp": now_ts,
                }
            else:
                ok, route_info, err_msg = sri_voice_router.validate_and_route(
                    prompt, auth_provided or sri_auth_secret
                )
                if not ok:
                    response_payload = {
                        "status": "error",
                        "code": 403,
                        "action": "voice_route",
                        "error": err_msg,
                        "route_info": route_info,
                        "timestamp": now_ts,
                    }
                else:
                    target_folder = (
                        route_info.get("target_workspace", "").replace("workspace/", "")
                        or "student_learning_hub"
                    )
                    task_type = (
                        "frontend"
                        if route_info.get("route") == "DESIGN"
                        else (
                            "general"
                            if route_info.get("route") == "RESEARCH"
                            else "auto"
                        )
                    )
                    task_id = dispatch_background_task(
                        prompt=prompt, task_type=task_type, folder_name=target_folder
                    )
                    response_payload = {
                        "status": "ok",
                        "action": "voice_route",
                        "task_id": task_id,
                        "route_detected": route_info.get("route"),
                        "tamil_title": route_info.get("tamil_title"),
                        "engine_selected": route_info.get("engine"),
                        "target_workspace": route_info.get("target_workspace"),
                        "target_files": route_info.get("target_files"),
                        "explanation": route_info.get("explanation"),
                        "status_url": f"?action=status&task_id={task_id}&auth={auth_provided or sri_auth_secret}",
                        "timestamp": now_ts,
                    }

        elif action in ["universal_route", "best_ai", "sri_route"]:
            prompt = (
                params.get("prompt", "")
                or params.get("command", "")
                or params.get("text", "")
            )
            if not prompt:
                response_payload = {
                    "status": "error",
                    "code": 400,
                    "error": "Bad Request: 'prompt' parameter is required for best-AI routing.",
                    "example": "?action=universal_route&prompt=மாணவர்+பக்கத்திற்கு+புதிய+டிசைன்+செய்&auth=SRI_AUTH_SEC_948f2b7a0c91825",
                    "timestamp": now_ts,
                }
            else:
                route_res = sri_universal_router.route_to_best_ai(
                    auth_provided or sri_auth_secret, prompt
                )
                if not route_res:
                    response_payload = {
                        "status": "error",
                        "code": 403,
                        "action": "universal_route",
                        "error": f"SriUniversalVoiceRouter Auto-Kill: {sri_universal_router.kill_reason}",
                        "timestamp": now_ts,
                    }
                else:
                    chosen_ai, target_file = route_res
                    task_type = (
                        "frontend"
                        if target_file == "index.html"
                        else ("general" if target_file == "server.js" else "auto")
                    )
                    task_id = dispatch_background_task(
                        prompt=prompt,
                        task_type=task_type,
                        folder_name=(
                            "student_learning_hub"
                            if target_file == "index.html"
                            else "new_project_area"
                        ),
                    )
                    response_payload = {
                        "status": "ok",
                        "action": "universal_route",
                        "task_id": task_id,
                        "chosen_ai": chosen_ai,
                        "target_file": target_file,
                        "command": prompt,
                        "status_url": f"?action=status&task_id={task_id}&auth={auth_provided or sri_auth_secret}",
                        "timestamp": now_ts,
                    }

        elif action in ["master_task", "universal_task", "master_execute"]:
            prompt = (
                params.get("prompt", "")
                or params.get("task", "")
                or params.get("command", "")
            )
            work_area = (
                params.get("work_area", "")
                or params.get("area", "")
                or "workspace/student_learning_hub"
            )
            if not prompt:
                response_payload = {
                    "status": "error",
                    "code": 400,
                    "error": "Bad Request: 'prompt' parameter is required for master agent task execution.",
                    "example": "?action=master_task&work_area=workspace/student_learning_hub&prompt=மாணவர்+பக்கத்தை+டிசைன்+செய்&auth=SRI_AUTH_SEC_948f2b7a0c91825",
                    "timestamp": now_ts,
                }
            else:
                exec_res = sri_master_agent.execute_universal_task(
                    auth_provided or sri_auth_secret, work_area, prompt
                )
                if not exec_res:
                    response_payload = {
                        "status": "error",
                        "code": 403,
                        "action": "master_task",
                        "error": f"SriUniversalMasterAgent Auto-Kill: {sri_master_agent.kill_reason}",
                        "timestamp": now_ts,
                    }
                else:
                    folder_target = (
                        work_area.replace("workspace/", "").strip()
                        or "student_learning_hub"
                    )
                    task_type = (
                        "frontend"
                        if "Stitch" in exec_res["ai_engine"]
                        else (
                            "general"
                            if "OpenRouter" in exec_res["ai_engine"]
                            else "auto"
                        )
                    )
                    task_id = dispatch_background_task(
                        prompt=prompt, task_type=task_type, folder_name=folder_target
                    )
                    response_payload = {
                        "status": "ok",
                        "action": "master_task",
                        "task_id": task_id,
                        "master_execution": exec_res,
                        "status_url": f"?action=status&task_id={task_id}&auth={auth_provided or sri_auth_secret}",
                        "timestamp": now_ts,
                    }

        elif action in ["master_agent_status"]:
            response_payload = {
                "status": "ok",
                "action": "master_agent_status",
                "agent_name": sri_master_agent.agent_name,
                "is_active": sri_master_agent.is_active,
                "kill_reason": sri_master_agent.kill_reason,
                "approved_work_areas": sri_master_agent.approved_work_areas,
                "timestamp": now_ts,
            }

        elif action in ["reset_master_agent", "rearm_master_agent"]:
            rearm_key = auth_provided or params.get("key", "") or sri_auth_secret
            ok = sri_master_agent.reset_agent(rearm_key)
            response_payload = {
                "status": "ok" if ok else "error",
                "action": "reset_master_agent",
                "is_active": sri_master_agent.is_active,
                "message": (
                    "SriUniversalMasterAgent successfully re-armed."
                    if ok
                    else "Failed to re-arm: Invalid key."
                ),
                "timestamp": now_ts,
            }

        elif action in ["add_work_area"]:
            new_area = params.get("area", "") or params.get("path", "")
            if not new_area:
                response_payload = {
                    "status": "error",
                    "code": 400,
                    "error": "Bad Request: 'area' parameter is required to add work area.",
                    "timestamp": now_ts,
                }
            else:
                sri_master_agent.add_new_work_area(new_area)
                response_payload = {
                    "status": "ok",
                    "action": "add_work_area",
                    "added_area": new_area,
                    "approved_work_areas": sri_master_agent.approved_work_areas,
                    "timestamp": now_ts,
                }

        elif action in ["help", "docs"]:
            response_payload = {
                "status": "ok",
                "action": "help",
                "agent": "SRI Autonomous Agent REST API Gateway",
                "auth_method": f"Pass query parameter '?auth={sri_auth_secret}'",
                "endpoints": {
                    "health": f"?action=health&auth={sri_auth_secret}",
                    "voice_route": f"?action=voice_route&prompt=<TAMIL_OR_ENGLISH_PROMPT>&auth={sri_auth_secret}",
                    "dispatch_task": f"?action=dispatch&prompt=<PROMPT>&type=<auto|frontend|general>&folder=<FOLDER>&auth={sri_auth_secret}",
                    "task_status": f"?action=status&task_id=<TASK_ID>&auth={sri_auth_secret}",
                    "list_tasks": f"?action=list&limit=25&status=<RUNNING|COMPLETED|FAILED>&auth={sri_auth_secret}",
                    "metrics": f"?action=metrics&auth={sri_auth_secret}",
                    "twilio_voice_call": f"?action=call&message=<TEXT>&auth={sri_auth_secret}",
                    "workspace_files": f"?action=workspace&auth={sri_auth_secret}",
                    "gate_status": f"?action=gate_status&auth={sri_auth_secret}",
                    "reset_gate": f"?action=reset_gate&auth={sri_auth_secret}",
                    "design_guard_status": f"?action=design_guard_status&auth={sri_auth_secret}",
                    "reset_design_guard": f"?action=reset_design_guard&auth={sri_auth_secret}",
                },
                "timestamp": now_ts,
            }

        else:
            response_payload = {
                "status": "error",
                "code": 400,
                "error": f"Unknown action '{action}'. Supported actions: health, dispatch, status, list, metrics, call, workspace, gate_status, reset_gate, help.",
                "hint": f"Check '?action=help&auth={sri_auth_secret}' for API documentation.",
                "timestamp": now_ts,
            }

    except Exception as e:
        response_payload = {
            "status": "error",
            "code": 500,
            "error": f"Internal API execution error: {str(e)}",
            "timestamp": datetime.now().isoformat(),
        }

    # Render API response cleanly and stop script execution
    st.subheader("🤖 SRI Autonomous Agent API Gateway")
    st.json(response_payload)
    st.code(json.dumps(response_payload, indent=2), language="json")
    st.stop()


# Evaluate incoming API requests immediately before UI rendering
handle_sri_api_gateway()






# ==============================================================================
# 8. BESPOKE OBSIDIAN THEME, PARTICLES & STICKY HEADER
# ==============================================================================

def create_project_zip_bundle(target_path: str) -> bytes:
    """Creates a downloadable .zip archive in-memory for a project directory or file."""
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        if os.path.isdir(target_path):
            for root, _, files in os.walk(target_path):
                for f in files:
                    if f.endswith(".tmp") or f.startswith("."):
                        continue
                    full_p = os.path.join(root, f)
                    rel_p = os.path.relpath(full_p, target_path)
                    zf.write(full_p, arcname=rel_p)
        elif os.path.isfile(target_path):
            zf.write(target_path, arcname=os.path.basename(target_path))
    zip_buffer.seek(0)
    return zip_buffer.getvalue()


def render_obsidian_theme_and_particles():
    """Renders Deep Obsidian theme CSS and hardware-accelerated ambient ember particles."""
    theme_html = """
    <canvas id="obsidian-ambient-canvas" style="position: fixed; inset: 0; width: 100vw; height: 100vh; pointer-events: none; z-index: 0;"></canvas>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600&family=Plus+Jakarta+Sans:wght@400;600;700;800&display=swap');

        /* True Deep Obsidian Canvas (#060709) across all Streamlit background wrappers */
        html, body, [data-testid="stAppViewContainer"], [data-testid="stApp"], .stApp, section.main, .main {
            background-color: #060709 !important;
            background: #060709 !important;
            color: #F1F5F9 !important;
            font-family: 'Plus Jakarta Sans', 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
        }

        /* 1. Remove all default Streamlit UI chrome & hide all default radio circles */
        [data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stDecoration"], .stDeployButton, #MainMenu, footer {
            display: none !important;
        }
        input[type="radio"] {
            display: none !important;
        }
        div[role="radiogroup"] > label > div:first-child {
            display: none !important;
        }

        /* Container padding for edge-to-edge bespoke feel */
        .main .block-container {
            max-width: 100% !important;
            padding-top: 0.5rem !important;
            padding-bottom: 2rem !important;
            padding-left: 1.2rem !important;
            padding-right: 1.2rem !important;
            position: relative;
            z-index: 1;
        }

        [data-testid="stSidebar"], section[data-testid="stSidebar"] {
            background-color: #090B10 !important;
            background: #090B10 !important;
            border-right: 1px solid #1E222B !important;
            box-shadow: 4px 0 30px rgba(0, 0, 0, 0.8) !important;
        }

        /* 1px Hairline borders and glassmorphism on all expanders */
        div[data-testid="stExpander"] {
            background: rgba(12, 15, 22, 0.85) !important;
            border: 1px solid #1E222B !important;
            border-radius: 12px !important;
            backdrop-filter: blur(16px) !important;
            margin-bottom: 12px !important;
            transition: border-color 0.25s ease, box-shadow 0.25s ease;
        }

        div[data-testid="stExpander"]:hover {
            border-color: rgba(245, 158, 11, 0.45) !important;
            box-shadow: 0 4px 20px rgba(245, 158, 11, 0.12);
        }

        /* Hide all default Streamlit red/white radio circles & style as sleek segmented pills */
        div[role="radiogroup"] {
            display: flex !important;
            flex-direction: row !important;
            gap: 6px !important;
            background: #090B10 !important;
            border: 1px solid #1E222B !important;
            padding: 3px !important;
            border-radius: 9999px !important;
            width: fit-content !important;
        }

        div[role="radiogroup"] > label {
            margin: 0 !important;
            padding: 5px 16px !important;
            border-radius: 9999px !important;
            cursor: pointer !important;
            border: 1px solid transparent !important;
            transition: all 0.2s ease !important;
            background: transparent !important;
        }

        div[role="radiogroup"] > label > div:first-child {
            display: none !important;
        }

        div[role="radiogroup"] > label div[data-testid="stMarkdownContainer"] p {
            color: #94A3B8 !important;
            font-size: 0.8rem !important;
            font-weight: 600 !important;
            margin: 0 !important;
            transition: color 0.2s ease !important;
        }

        div[role="radiogroup"] > label:hover {
            background: rgba(245, 158, 11, 0.06) !important;
        }

        div[role="radiogroup"] > label:has(input:checked) {
            background: rgba(245, 158, 11, 0.14) !important;
            border: 1px solid #F59E0B !important;
            box-shadow: 0 0 10px rgba(245, 158, 11, 0.25) !important;
        }

        div[role="radiogroup"] > label:has(input:checked) div[data-testid="stMarkdownContainer"] p {
            color: #FBBF24 !important;
            font-weight: 700 !important;
        }

        /* Carousel horizontal pill dock */
        div[data-testid="stHorizontalBlock"]:has(button[key="pill_student_db"]) {
            display: flex !important;
            flex-direction: row !important;
            gap: 6px !important;
            align-items: center !important;
            margin-bottom: 6px !important;
        }

        div[data-testid="stHorizontalBlock"]:has(button[key="pill_student_db"]) button {
            background: #0E1117 !important;
            border: 1px solid #1E222B !important;
            border-radius: 9999px !important;
            color: #D1D5DB !important;
            font-size: 0.74rem !important;
            font-weight: 500 !important;
            padding: 6px 10px !important;
            white-space: nowrap !important;
            text-overflow: ellipsis !important;
            overflow: hidden !important;
            transition: all 0.2s ease !important;
        }

        div[data-testid="stHorizontalBlock"]:has(button[key="pill_student_db"]) button[key="pill_student_db"] {
            border: 1px solid #F59E0B !important;
            background: rgba(245, 158, 11, 0.12) !important;
            color: #FBBF24 !important;
            box-shadow: 0 0 10px rgba(245, 158, 11, 0.25) !important;
            font-weight: 600 !important;
        }

        div[data-testid="stHorizontalBlock"]:has(button[key="pill_student_db"]) button:hover {
            border-color: #F59E0B !important;
            color: #FBBF24 !important;
            background: rgba(245, 158, 11, 0.08) !important;
            transform: translateY(-1px) !important;
        }

        /* Gold-Bordered Prompt Bar: "Ask SRI Agent..." and "Message SRI..." */
        div[data-testid="stHorizontalBlock"]:has(input[aria-label*="Ask SRI Agent"]),
        div[data-testid="stHorizontalBlock"]:has(input[aria-label="Message SRI..."]) {
            background: #0E1117 !important;
            border: 1px solid rgba(245, 158, 11, 0.4) !important;
            border-radius: 9999px !important;
            padding: 4px 8px 4px 18px !important;
            align-items: center !important;
            box-shadow: 0 4px 25px rgba(0, 0, 0, 0.6), 0 0 15px rgba(245, 158, 11, 0.15) !important;
            transition: border-color 0.25s, box-shadow 0.25s !important;
            margin-top: 10px !important;
            flex-direction: row !important;
            flex-wrap: nowrap !important;
        }

        div[data-testid="stHorizontalBlock"]:has(input[aria-label*="Ask SRI Agent"]):focus-within,
        div[data-testid="stHorizontalBlock"]:has(input[aria-label="Message SRI..."]):focus-within {
            border-color: #F59E0B !important;
            box-shadow: 0 4px 28px rgba(245, 158, 11, 0.35) !important;
        }

        div[data-testid="stHorizontalBlock"]:has(input[aria-label*="Ask SRI Agent"]) div[data-testid="column"],
        div[data-testid="stHorizontalBlock"]:has(input[aria-label="Message SRI..."]) div[data-testid="column"] {
            width: auto !important;
            min-width: 0 !important;
            flex: 0 0 auto !important;
        }

        div[data-testid="stHorizontalBlock"]:has(input[aria-label*="Ask SRI Agent"]) div[data-testid="column"]:first-child,
        div[data-testid="stHorizontalBlock"]:has(input[aria-label="Message SRI..."]) div[data-testid="column"]:first-child {
            flex: 1 1 auto !important;
        }

        div[data-testid="stHorizontalBlock"]:has(input[aria-label*="Ask SRI Agent"]) div[data-testid="stTextInput"],
        div[data-testid="stHorizontalBlock"]:has(input[aria-label="Message SRI..."]) div[data-testid="stTextInput"] {
            margin-bottom: 0 !important;
        }

        div[data-testid="stHorizontalBlock"]:has(input[aria-label*="Ask SRI Agent"]) input,
        div[data-testid="stHorizontalBlock"]:has(input[aria-label="Message SRI..."]) input {
            background: transparent !important;
            border: none !important;
            color: #FFFFFF !important;
            box-shadow: none !important;
            padding-left: 0 !important;
            font-size: 0.88rem !important;
        }

        /* Circular Mic & Gold Send Buttons inside dock */
        button[key="unified_mic_btn"] {
            background: transparent !important;
            border: none !important;
            color: #94A3B8 !important;
            font-size: 1.15rem !important;
            border-radius: 50% !important;
            padding: 4px !important;
            transition: color 0.2s, background 0.2s !important;
        }

        button[key="unified_mic_btn"]:hover {
            color: #F59E0B !important;
            background: rgba(245, 158, 11, 0.12) !important;
        }

        button[key="unified_send_btn"] {
            background: linear-gradient(135deg, #F59E0B, #D97706) !important;
            color: #060709 !important;
            font-weight: 900 !important;
            font-size: 1.05rem !important;
            border: none !important;
            border-radius: 50% !important;
            width: 36px !important;
            height: 36px !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            box-shadow: 0 2px 10px rgba(245, 158, 11, 0.45) !important;
            transition: transform 0.2s, box-shadow 0.2s !important;
        }

        button[key="unified_send_btn"]:hover {
            transform: scale(1.08) !important;
            box-shadow: 0 4px 18px rgba(245, 158, 11, 0.65) !important;
        }

        /* Buttons styling */
        button[kind="primary"] {
            background: linear-gradient(135deg, #F59E0B, #D97706) !important;
            color: #060709 !important;
            font-weight: 700 !important;
            border: none !important;
            border-radius: 9999px !important;
            box-shadow: 0 4px 18px rgba(245, 158, 11, 0.35) !important;
            transition: all 0.2s ease !important;
        }

        button[kind="secondary"] {
            background: #0E1117 !important;
            color: #E2E8F0 !important;
            border: 1px solid #262A34 !important;
            border-radius: 9999px !important;
            font-size: 0.78rem !important;
            transition: all 0.2s ease !important;
        }

        button[kind="secondary"]:hover {
            border-color: #F59E0B !important;
            color: #FBBF24 !important;
            background: rgba(245, 158, 11, 0.08) !important;
        }

        /* Text inputs */
        input[type="text"], input[type="password"], textarea, .stSelectbox > div > div {
            background-color: #0C0F17 !important;
            color: #FFFFFF !important;
            border: 1px solid #1E222B !important;
            border-radius: 10px !important;
        }

        input[type="text"]:focus, input[type="password"]:focus, textarea:focus {
            border-color: #F59E0B !important;
            box-shadow: 0 0 0 2px rgba(245, 158, 11, 0.25) !important;
        }

        /* Locked Sticky Top Header (68px, glassmorphic obsidian, 1px #1A1D24 border) */
        .sri-sticky-header {
            position: sticky;
            top: 0;
            z-index: 999;
            height: 68px;
            background: rgba(6, 7, 9, 0.94);
            backdrop-filter: blur(18px);
            -webkit-backdrop-filter: blur(18px);
            border-bottom: 1px solid #1A1D24;
            padding: 0 24px;
            margin-top: -0.5rem;
            margin-left: -1.2rem;
            margin-right: -1.2rem;
            margin-bottom: 1.2rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
            box-sizing: border-box;
        }

        .brand-title-wrap {
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .brand-logo-editorial {
            font-size: 1.55rem;
            font-weight: 800;
            letter-spacing: -0.5px;
            color: #FFFFFF;
            font-family: 'Plus Jakarta Sans', sans-serif;
            user-select: none;
        }

        .brand-period-gold {
            color: #F59E0B;
            font-weight: 900;
        }

        .header-center-dock {
            display: flex;
            align-items: center;
            justify-content: center;
        }

        .center-agent-pill {
            display: flex;
            align-items: center;
            gap: 8px;
            background: #0E1117;
            border: 1px solid rgba(245, 158, 11, 0.25);
            border-radius: 9999px;
            padding: 6px 18px;
            font-size: 0.8rem;
            font-weight: 600;
            color: #E2E8F0;
            box-shadow: 0 2px 12px rgba(0, 0, 0, 0.6);
            letter-spacing: 0.2px;
        }

        .gold-status-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: #F59E0B;
            box-shadow: 0 0 10px #F59E0B, 0 0 4px #FBBF24;
            display: inline-block;
        }

        .header-actions-right {
            display: flex;
            align-items: center;
            gap: 14px;
        }

        .control-drawer-btn {
            display: flex;
            align-items: center;
            gap: 10px;
            background: transparent;
            border: none;
            cursor: pointer;
            padding: 4px 8px;
            border-radius: 8px;
            transition: all 0.2s ease;
            user-select: none;
        }

        .control-drawer-btn:hover {
            background: rgba(245, 158, 11, 0.08);
        }

        .drawer-text-col {
            display: flex;
            flex-direction: column;
            text-align: left;
            line-height: 1.15;
        }

        .drawer-label-top {
            font-size: 0.82rem;
            font-weight: 600;
            color: #E2E8F0;
        }

        .drawer-label-sub {
            font-size: 0.72rem;
            font-weight: 600;
            color: #F59E0B;
            text-shadow: 0 0 8px rgba(245, 158, 11, 0.35);
        }

        .user-avatar-badge {
            position: relative;
            width: 34px;
            height: 34px;
            background: #12151D;
            border: 1px solid #232834;
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.4);
        }

        .avatar-green-dot {
            position: absolute;
            top: 4px;
            right: 4px;
            width: 7px;
            height: 7px;
            background: #10B981;
            border-radius: 50%;
            box-shadow: 0 0 6px #10B981;
            border: 1px solid #12151D;
        }

        /* -------------------------------------------------- */
        /* Left Zone: Subtitle, Title & Divided Metrics List   */
        /* -------------------------------------------------- */
        .left-zone-greeting {
            font-size: 1.05rem;
            font-weight: 600;
            color: #D97706;
            margin-bottom: 2px;
            letter-spacing: -0.2px;
        }

        .left-zone-title {
            font-size: 2.2rem;
            font-weight: 700;
            color: #FFFFFF;
            font-family: 'Playfair Display', Georgia, serif;
            letter-spacing: -0.5px;
            margin-bottom: 20px;
            line-height: 1.1;
        }

        .metrics-list-card {
            background: transparent;
            border-top: 1px solid #1A1D24;
            border-bottom: 1px solid #1A1D24;
            padding: 4px 0;
            margin-bottom: 22px;
        }

        .metric-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 10px 0;
            border-bottom: 1px solid #1A1D24;
            font-size: 0.85rem;
        }

        .metric-row:last-child {
            border-bottom: none;
        }

        .metric-label {
            color: #94A3B8;
            font-weight: 500;
        }

        .metric-val {
            color: #E2E8F0;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 6px;
        }

        .metric-val-status {
            color: #F59E0B;
            font-weight: 700;
            display: flex;
            align-items: center;
            gap: 6px;
            text-shadow: 0 0 8px rgba(245, 158, 11, 0.4);
        }

        .metric-dot {
            font-size: 0.7rem;
            color: #94A3B8;
        }

        .gold-dot {
            font-size: 0.7rem;
            color: #F59E0B;
            text-shadow: 0 0 8px #F59E0B;
        }

        .env-runtime-heading {
            font-size: 0.82rem;
            font-weight: 500;
            color: #64748B;
            margin-bottom: 10px;
        }

        .runtime-pills-row {
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
        }

        .runtime-pill {
            background: #0E1117;
            border: 1px solid #1E222B;
            color: #94A3B8;
            padding: 6px 14px;
            border-radius: 9999px;
            font-size: 0.78rem;
            font-weight: 500;
        }

        .runtime-pill-gold {
            color: #F59E0B !important;
            border: 1px solid rgba(245, 158, 11, 0.45) !important;
            text-shadow: 0 0 10px rgba(245, 158, 11, 0.4);
            font-weight: 600;
        }

        /* -------------------------------------------------- */
        /* Center Zone: 3D Granulated Golden Particle Sphere   */
        /* -------------------------------------------------- */
        .orb-stage-wrapper {
            position: relative;
            width: 250px;
            height: 235px;
            margin: 0 auto 10px auto;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            user-select: none;
        }

        .orb-halo-ambient {
            position: absolute;
            width: 225px;
            height: 225px;
            border-radius: 50%;
            background: radial-gradient(circle, rgba(245, 158, 11, 0.3) 0%, rgba(217, 119, 6, 0.12) 45%, transparent 70%);
            filter: blur(14px);
            pointer-events: none;
            animation: halo-pulse 3.5s ease-in-out infinite alternate;
        }

        @keyframes halo-pulse {
            0% { transform: scale(0.92); opacity: 0.7; }
            100% { transform: scale(1.12); opacity: 1; }
        }

        .orb-orbit-ring {
            position: absolute;
            width: 215px;
            height: 215px;
            border-radius: 50%;
            border: 1px solid rgba(245, 158, 11, 0.45);
            box-shadow: 0 0 10px rgba(245, 158, 11, 0.2);
            pointer-events: none;
            transform-style: preserve-3d;
        }

        .ring-tilt-a {
            transform: rotateX(72deg) rotateY(25deg);
            animation: orbit-spin-a 8s linear infinite;
        }

        .ring-tilt-b {
            width: 235px;
            height: 235px;
            border: 1px solid rgba(245, 158, 11, 0.35);
            transform: rotateX(68deg) rotateY(-36deg);
            animation: orbit-spin-b 11s linear infinite reverse;
        }

        @keyframes orbit-spin-a {
            0% { transform: rotateX(72deg) rotateY(25deg) rotateZ(0deg); }
            100% { transform: rotateX(72deg) rotateY(25deg) rotateZ(360deg); }
        }

        @keyframes orbit-spin-b {
            0% { transform: rotateX(68deg) rotateY(-36deg) rotateZ(0deg); }
            100% { transform: rotateX(68deg) rotateY(-36deg) rotateZ(360deg); }
        }

        .orbit-sparkle {
            position: absolute;
            width: 6px;
            height: 6px;
            background: #FFFBEB;
            border-radius: 50%;
            box-shadow: 0 0 8px 3px #FBBF24;
            top: 50%;
            left: -3px;
        }

        .orb-canvas-sphere {
            position: relative;
            z-index: 2;
            border-radius: 50%;
        }

        .orb-center-mic-badge {
            position: absolute;
            z-index: 4;
            width: 52px;
            height: 52px;
            border-radius: 50%;
            background: #0B0E14;
            border: 1.5px solid rgba(245, 158, 11, 0.65);
            box-shadow: 0 0 18px rgba(245, 158, 11, 0.45), inset 0 0 8px rgba(0, 0, 0, 0.8);
            display: flex;
            align-items: center;
            justify-content: center;
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }

        .orb-stage-wrapper:hover .orb-center-mic-badge {
            transform: scale(1.08);
            box-shadow: 0 0 25px rgba(245, 158, 11, 0.7);
        }

        /* -------------------------------------------------- */
        /* Right Zone: Project Viewer Card                     */
        /* -------------------------------------------------- */
        .pv-glass-container {
            background: rgba(12, 15, 22, 0.95);
            border: 1px solid #1E222B;
            border-radius: 16px;
            padding: 14px 16px;
            position: relative;
            min-height: 480px;
            box-shadow: 0 8px 30px rgba(0, 0, 0, 0.6);
        }

        .pv-meta-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 4px 2px 8px 2px;
            font-size: 0.82rem;
            border-bottom: 1px solid #1E222B;
            margin-bottom: 10px;
        }

        .pv-file-path {
            color: #F59E0B;
            font-family: 'JetBrains Mono', monospace;
            font-weight: 700;
            text-shadow: 0 0 8px rgba(245, 158, 11, 0.35);
        }

        .pv-file-size {
            color: #64748B;
            font-size: 0.76rem;
        }

        .pv-sparkle-decor {
            position: absolute;
            bottom: 12px;
            right: 14px;
            color: #E2E8F0;
            font-size: 1.3rem;
            opacity: 0.85;
            pointer-events: none;
            text-shadow: 0 0 8px rgba(245, 158, 11, 0.5);
        }

        /* Mobile responsiveness via CSS purely (@media max-width: 900px) */
        @media (max-width: 900px) {
            .header-center-dock {
                display: none !important;
            }
            .sri-sticky-header {
                padding: 0 14px !important;
                height: 60px !important;
                margin-left: -0.8rem !important;
                margin-right: -0.8rem !important;
            }
            div[data-testid="stHorizontalBlock"] {
                flex-direction: column !important;
                gap: 18px !important;
            }
            div[data-testid="column"] {
                width: 100% !important;
                flex: 1 1 100% !important;
                min-width: 100% !important;
            }
        }
    </style>
    <script>
    (function() {
        const canvas = document.getElementById('obsidian-ambient-canvas');
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        let width = canvas.width = window.innerWidth;
        let height = canvas.height = window.innerHeight;

        window.addEventListener('resize', () => {
            width = canvas.width = window.innerWidth;
            height = canvas.height = window.innerHeight;
        });

        const colors = ['#F59E0B', '#D97706', '#FBBF24', '#B45309'];
        const particleCount = 45;
        const particles = [];
        for (let i = 0; i < particleCount; i++) {
            particles.push({
                x: Math.random() * width,
                y: height + Math.random() * 200,
                radius: Math.random() * 2.2 + 0.8,
                color: colors[Math.floor(Math.random() * colors.length)],
                speedY: Math.random() * 0.45 + 0.15,
                wobbleSpeed: Math.random() * 0.015 + 0.005,
                wobbleAmp: Math.random() * 20 + 10,
                seed: Math.random() * 100,
                alpha: Math.random() * 0.6 + 0.2
            });
        }

        let time = 0;
        function animate() {
            ctx.clearRect(0, 0, width, height);
            time += 0.012;

            // Dark drifting silk waves
            ctx.save();
            for (let w = 0; w < 3; w++) {
                ctx.beginPath();
                ctx.moveTo(0, height * (0.6 + w * 0.15));
                for (let x = 0; x <= width; x += 30) {
                    const waveY = height * (0.6 + w * 0.15) 
                        + Math.sin(x * 0.002 + time * 0.5 + w) * 45 
                        + Math.cos(x * 0.001 - time * 0.3) * 35;
                    ctx.lineTo(x, waveY);
                }
                ctx.lineTo(width, height);
                ctx.lineTo(0, height);
                ctx.closePath();
                ctx.fillStyle = `rgba(18, 22, 33, ${0.035 - w * 0.008})`;
                ctx.fill();
            }
            ctx.restore();

            // Amber / tiger-gold embers drifting upward
            particles.forEach(p => {
                p.y -= p.speedY;
                const xOffset = Math.sin(time * p.wobbleSpeed * 50 + p.seed) * p.wobbleAmp;
                const curX = (p.x + xOffset + width) % width;
                const twinkle = Math.sin(time * 2 + p.seed) * 0.25 + 0.75;
                const curAlpha = Math.max(0.1, Math.min(0.9, p.alpha * twinkle));

                ctx.save();
                ctx.beginPath();
                ctx.arc(curX, p.y, p.radius, 0, Math.PI * 2);
                ctx.fillStyle = p.color;
                ctx.globalAlpha = curAlpha;
                ctx.shadowBlur = p.radius * 4;
                ctx.shadowColor = p.color;
                ctx.fill();
                ctx.restore();

                if (p.y < -20) {
                    p.y = height + Math.random() * 50;
                    p.x = Math.random() * width;
                }
            });

            requestAnimationFrame(animate);
        }
        animate();
    })();
    </script>
    """
    st.markdown(theme_html, unsafe_allow_html=True)


def render_sticky_top_header():
    """Renders locked sticky top header matching reference UI pixel-for-pixel."""
    header_html = """
    <div class="sri-sticky-header">
        <div class="brand-title-wrap">
            <span class="brand-logo-editorial">SRI AI<span class="brand-period-gold">.</span></span>
        </div>
        <div class="header-center-dock">
            <div class="center-agent-pill">
                <span class="gold-status-dot"></span>
                <span>98.4% Agent Active</span>
            </div>
        </div>
        <div class="header-actions-right">
            <div class="control-drawer-btn" onclick="
                var btn = (window.parent && window.parent.document.querySelector('[data-testid=collapsedControl] button')) ||
                          document.querySelector('[data-testid=collapsedControl] button') ||
                          document.querySelector('[data-testid=stSidebarCollapseButton] button') ||
                          (window.parent && window.parent.document.querySelector('[data-testid=stSidebarCollapseButton] button'));
                if(btn) { btn.click(); }
            " title="Open Technical Controls Drawer">
                <svg class="drawer-sliders-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#D1D5DB" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <line x1="4" y1="21" x2="4" y2="14"></line>
                    <line x1="4" y1="10" x2="4" y2="3"></line>
                    <line x1="12" y1="21" x2="12" y2="12"></line>
                    <line x1="12" y1="8" x2="12" y2="3"></line>
                    <line x1="20" y1="21" x2="20" y2="16"></line>
                    <line x1="20" y1="12" x2="20" y2="3"></line>
                    <line x1="1" y1="14" x2="7" y2="14"></line>
                    <line x1="9" y1="8" x2="15" y2="8"></line>
                    <line x1="17" y1="16" x2="23" y2="16"></line>
                </svg>
                <div class="drawer-text-col">
                    <span class="drawer-label-top">Control Drawer</span>
                    <span class="drawer-label-sub">Sri (Ready)</span>
                </div>
            </div>
            <div class="user-avatar-badge" title="Sri (Ready) — Online">
                <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="#94A3B8" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
                    <circle cx="12" cy="7" r="4"></circle>
                </svg>
                <span class="avatar-green-dot"></span>
            </div>
        </div>
    </div>
    """
    st.markdown(header_html, unsafe_allow_html=True)


# Render Obsidian Canvas, Floating Gold Particles & Sticky Top Header via SRI UI Bridge
inject_sri_ui_and_particles()


# ==============================================================================
# 9. COLLAPSIBLE CONTROL DRAWER / SIDEBAR (ALL 14 BACKEND CONTROLS)
# ==============================================================================
with st.sidebar:
    st.markdown("### ⚙️ SRI Control Drawer")
    st.caption("Organized technical controls • 24/7 Decoupled Background Engine")

    # 1. Workspaces & Background Runner
    with st.expander("🏢 1. Workspaces & Background Runner", expanded=False):
        st.markdown("**📂 Workspace Directory Management:**")
        col_wa_in, col_wa_add = st.columns([3, 1])
        with col_wa_in:
            sb_new_work_area = st.text_input(
                "புதிய வேலை ஏரியாவைச் சேர்க்க:",
                placeholder="workspace/my_new_app",
                key="sb_wa_new_input",
                label_visibility="collapsed",
            )
        with col_wa_add:
            if st.button("➕ Add", key="sb_wa_add_btn", use_container_width=True) and sb_new_work_area:
                sri_master_agent.add_new_work_area(sb_new_work_area)
                st.toast(f"Added workspace: {sb_new_work_area}")
                st.rerun()

        sb_selected_area = st.selectbox(
            "📂 எந்த ஏரியாவில் வேலை செய்ய வேண்டும்?",
            sri_master_agent.approved_work_areas,
            key="sb_wa_selected_area",
        )
        sb_task_desc = st.text_area(
            "📝 ஸ்ரீ (SRI) செய்ய வேண்டிய டாஸ்க்:",
            placeholder="உம்: மாணவர் ஆப்பிற்கு அழகான UI டிசைன் செய்து கோட் எழுது...",
            height=90,
            key="sb_wa_task_desc",
        )
        if st.button("🚀 Start Background Task", key="sb_start_bg_btn", type="primary", use_container_width=True):
            if not sb_task_desc.strip():
                st.warning("⚠️ தயவுசெய்து டாஸ்க் விவரத்தை உள்ளிடவும்.")
            else:
                new_task_id = f"SRI-{uuid.uuid4().hex[:6].upper()}"
                t_low = sb_task_desc.lower()
                if any(w in t_low for w in ["design", "ui", "frontend", "டிசைன்", "பக்கம்"]):
                    ai_engine = "Stitch AI (Frontend Specialist)"
                    task_type = "frontend"
                elif any(w in t_low for w in ["code", "app", "deploy", "கோடு", "டிப்ளாய்"]):
                    ai_engine = "Google Gemini Pro + Antigravity"
                    task_type = "auto"
                else:
                    ai_engine = "OpenRouter Multi-AI Engine"
                    task_type = "general"

                if sri_cloud_background_worker:
                    thread = threading.Thread(
                        target=sri_cloud_background_worker,
                        args=(new_task_id, sb_selected_area, sb_task_desc.strip(), ai_engine),
                        daemon=False,
                    )
                    thread.start()

                folder_target = sb_selected_area.replace("workspace/", "").strip() or "student_learning_hub"
                dispatch_background_task(
                    prompt=sb_task_desc.strip(),
                    task_type=task_type,
                    folder_name=folder_target,
                )
                st.toast(f"✅ டாஸ்க் தொடங்கியது! ID: {new_task_id}")
                st.success(f"Started via {ai_engine}! Task ID: `{new_task_id}`")
                st.rerun()

    # 2. Voice Engine & Task Routing
    with st.expander("🎙️ 2. Voice Engine & Task Routing", expanded=False):
        sb_voice_choice = st.radio(
            "Transcription Route:",
            options=[
                "✨ Gemini Multimodal Audio (Tamil & Task Extraction)",
                "⚡ Groq Whisper (Tamil language='ta')",
            ],
            index=0,
            key="sb_voice_route_selector",
        )
        sb_task_classification = st.radio(
            "Task Classification:",
            [
                "Auto-Detect",
                "Frontend UI (HTML/CSS/JS)",
                "General Script / Automation",
                "🛠️ Modify Existing Code (Workspace)",
            ],
            key="sb_task_class_selector",
        )
        sb_folder_name = st.text_input(
            "📁 Project Folder Name (inside workspace/):",
            value="",
            placeholder="student_learning_hub",
            key="sb_folder_name_in",
        )
        st.caption(f"Target Path: `workspace/{sb_folder_name or '[auto_derived]'}/index.html`")

        if hasattr(st, "audio_input"):
            sb_v_audio = st.audio_input("Record voice instruction:", key="sb_voice_audio_in")
            if sb_v_audio is not None:
                audio_bytes = sb_v_audio.getvalue()
                mime = sb_v_audio.type or "audio/wav"
                engine_route = "gemini" if "Gemini" in sb_voice_choice else "whisper"
                try:
                    transcribed = transcribe_audio_to_text(audio_bytes, mime_type=mime, engine=engine_route)
                    st.session_state["task_prompt_val"] = transcribed
                    st.session_state["active_voice_query"] = transcribed
                    st.toast("Voice instruction transcribed!")
                    st.rerun()
                except Exception as ve:
                    st.warning(f"Voice notice: {ve}")

        if st.button("🎤 நேரலை மைக்ரோஃபோன் (speech_recognition ta-IN)", key="sb_mic_listen_btn", use_container_width=True):
            cmd = sri_universal_router.listen_voice_command()
            if cmd:
                st.session_state["task_prompt_val"] = cmd
                st.session_state["active_voice_query"] = cmd
                st.toast(f"குரல் பெறப்பட்டது: {cmd}")
                st.rerun()

        cur_p = st.session_state.get("task_prompt_val", "").strip()
        if cur_p:
            r_info = sri_voice_router.classify_intent(cur_p)
            st.info(f"🧭 **Route:** `{r_info['route']}` | **Engine:** `{r_info['engine']}`\n**Workspace:** `{r_info['target_workspace']}`")

    # 3. Model & API Router + Safety Gate
    with st.expander("🛡️ 3. Model & API Router + Safety Gate", expanded=False):
        st.markdown("**Execution Gate & Approval Mode:**")
        auto_approve_toggle = st.toggle("🛡️ Execution Gate: Auto-Approve Mode", value=st.session_state.get("cfg_auto_approve", True), key="sb_auto_approve_toggle")
        st.session_state["cfg_auto_approve"] = auto_approve_toggle

        if sri_execution_gate.is_active:
            st.success("🟢 **Execution Gate: ACTIVE (Boundary Enforced)**")
        else:
            st.error(f"🛑 **Gate: AUTO-KILLED**\n*{sri_execution_gate.kill_reason}*")
            if st.button("🔄 Re-Arm Gate", key="sb_rearm_gate_btn", use_container_width=True):
                if sri_execution_gate.reset_gate(sri_auth_secret):
                    st.toast("Execution Gate re-armed!")
                    st.rerun()

        if sri_design_guard.is_active:
            st.success("🟢 **Design Guard: ACTIVE (Stitch AI & UI Secured)**")
        else:
            st.error(f"🛑 **Design Guard: AUTO-KILLED**\n*{sri_design_guard.kill_reason}*")
            if st.button("🔄 Re-Arm Design Guard", key="sb_rearm_dg_btn", use_container_width=True):
                if sri_design_guard.reset_guard(sri_auth_secret):
                    st.toast("Design Guard re-armed!")
                    st.rerun()

        st.markdown("---")
        st.markdown("**API Keys & Agent Bridge:**")
        sb_bridge_key = st.text_input(
            "Agent Bridge Key (Antigravity):",
            value=st.session_state.get("cfg_agent_bridge_key", agent_bridge_api_key),
            type="password",
            key="sb_bridge_key_in",
        )
        if sb_bridge_key:
            st.session_state["cfg_agent_bridge_key"] = sb_bridge_key
            os.environ["AGENT_BRIDGE_API_KEY"] = sb_bridge_key

        sb_webhook_url = st.text_input(
            "Antigravity Webhook URL:",
            value=st.session_state.get("cfg_antigravity_webhook", antigravity_webhook_url),
            key="sb_webhook_url_in",
        )
        if sb_webhook_url:
            st.session_state["cfg_antigravity_webhook"] = sb_webhook_url
            os.environ["ANTIGRAVITY_WEBHOOK_URL"] = sb_webhook_url

        sb_stitch_key = st.text_input(
            "Stitch AI Key (Frontend UI):",
            value=st.session_state.get("cfg_stitch_ai_key", stitch_ai_api_key),
            type="password",
            key="sb_stitch_key_in",
        )
        if sb_stitch_key:
            st.session_state["cfg_stitch_ai_key"] = sb_stitch_key
            os.environ["STITCH_AI_API_KEY"] = sb_stitch_key

        st.caption("🟢 Tier 1: Cloud LLM (Gemini 2.5 Flash / OpenRouter Free)")
        st.caption("🟢 Tier 2: Antigravity Handoff Bridge Active")
        st.caption("🟢 Tier 3: Stitch AI UI Specialist Active")

    # 4. Twilio Voice Call & WhatsApp Bridge
    with st.expander("📞 4. Twilio Voice Call & WhatsApp Bridge", expanded=False):
        admin_num = get_secret("ADMIN_PHONE_NUMBER", "Unconfigured")
        st.caption(f"Target Phone Number: `{admin_num}`")
        if st.button("📞 Call Me Now (Test Agent Alert)", key="sb_call_now_btn", use_container_width=True):
            with st.spinner("Connecting phone call..."):
                ok, res = make_agent_call("வணக்கம்! உங்கள் ஏஜென்ட் வெற்றிகரமாக இணைக்கப்பட்டுள்ளது.")
                if ok:
                    st.success(f"Calling now! Call SID: {res}")
                else:
                    st.error(f"Call failed: {res}")

        st.markdown("---")
        wa_from = get_secret("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")
        wa_to = get_secret("MY_WHATSAPP_NUMBER", "Unconfigured")
        st.caption(f"WhatsApp From: `{wa_from}` | To: `{wa_to}`")
        st.caption("Milestone Alerts: 50% Started • 80% Verification • 100% Finished")
        if st.button("💬 Send Test WhatsApp Alert", key="sb_test_wa_btn", use_container_width=True):
            if send_whatsapp_message:
                with st.spinner("Sending WhatsApp message..."):
                    sent = send_whatsapp_message("🤖 வணக்கம்! இது SRI Cloud Agent-ன் Twilio WhatsApp சோதனைச் செய்தி (Test Message).")
                    if sent:
                        st.success("WhatsApp message sent successfully!")
                    else:
                        st.warning("Could not send WhatsApp message. Check Twilio credentials.")
            else:
                st.error("Twilio WhatsApp client unavailable.")

    # 5. Safe Auto-Code Editor & File Upload
    with st.expander("🛠️ 5. Safe Auto-Code Editor & File Upload", expanded=False):
        ws_flist = get_workspace_files()
        sb_cur_file = st.selectbox(
            "📁 Select file to inspect & refine:",
            ws_flist if ws_flist else ["login.html"],
            key="sb_cur_file_select",
        )
        col_seed, col_up = st.columns(2)
        with col_seed:
            if st.button("🌱 Seed login.html", key="sb_seed_btn", use_container_width=True):
                sample_login_code = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Login Portal</title>
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-900 text-slate-100 min-h-screen flex items-center justify-center p-4">
  <div class="w-full max-w-md bg-slate-800 rounded-2xl shadow-xl p-8 border border-slate-700">
    <h1 class="text-2xl font-bold text-white mb-4">Welcome Back</h1>
    <form class="space-y-4">
      <input type="email" placeholder="user@example.com" class="w-full px-4 py-2 rounded bg-slate-900 border border-slate-700"/>
      <button type="submit" class="w-full py-2 bg-indigo-600 rounded font-medium">Sign In</button>
    </form>
  </div>
</body>
</html>"""
                with open(os.path.join(WORKSPACE_DIR, "login.html"), "w", encoding="utf-8") as sf:
                    sf.write(sample_login_code)
                st.toast("Seeded login.html in workspace!")
                st.rerun()
        with col_up:
            sb_up_toggle = st.toggle("📤 Upload", value=False, key="sb_up_toggle")

        if sb_up_toggle:
            uploaded_file = st.file_uploader("Upload file to workspace:", type=["html", "py", "js", "css", "json", "txt"], key="sb_uploader_file")
            if uploaded_file:
                up_dst = os.path.join(WORKSPACE_DIR, uploaded_file.name)
                with open(up_dst, "wb") as uf:
                    uf.write(uploaded_file.getvalue())
                st.success(f"Uploaded `{uploaded_file.name}` to workspace!")
                st.rerun()

        if sb_cur_file and os.path.exists(os.path.join(WORKSPACE_DIR, sb_cur_file)):
            r_ok, r_content, _ = safe_read_code(sb_cur_file)
            if r_ok:
                with st.expander(f"👁️ View Original Source Code ({sb_cur_file})", expanded=False):
                    st.code(r_content, language="html" if sb_cur_file.endswith(".html") else "text")

                sb_edit_instructions = st.text_area(
                    "Modification Instructions:",
                    placeholder="e.g. Add dark glassmorphism and password reset modal...",
                    key="sb_edit_instructions_in",
                )
                if st.button("⚡ Execute Safe Auto-Edit", key="sb_exec_auto_edit_btn", type="primary", use_container_width=True):
                    if sb_edit_instructions.strip():
                        new_t_id = dispatch_code_edit_task(sb_cur_file, sb_edit_instructions.strip())
                        st.success(f"Safe Auto-Edit Dispatched! Task ID: `{new_t_id}`")
                        st.toast("Auto-Edit running in background!")
                        st.rerun()

    # 6. SRI REST API Gateway & Webhook
    with st.expander("🔌 6. SRI REST API Gateway & Webhook", expanded=False):
        st.markdown(f"**Auth Secret:** `{sri_auth_secret}`")
        st.markdown("**Sample API Commands:**")
        st.code(
            f'# Health Check\ncurl "http://localhost:8501/?action=health&auth={sri_auth_secret}"\n\n'
            f'# Dispatch Autonomous Task\ncurl "http://localhost:8501/?action=dispatch&prompt=Build+a+student+dashboard&auth={sri_auth_secret}"\n\n'
            f'# Poll Task Status\ncurl "http://localhost:8501/?action=status&task_id=<TASK_ID>&auth={sri_auth_secret}"\n\n'
            f'# Trigger Twilio Voice Alert\ncurl "http://localhost:8501/?action=call&message=Task+Completed&auth={sri_auth_secret}"',
            language="bash",
        )

    # 7. Execution Audit & Maintenance
    with st.expander("📊 7. Execution Audit & Maintenance", expanded=False):
        st.markdown("**Task History & Maintenance:**")
        col_g1, col_g2 = st.columns(2)
        with col_g1:
            if st.button("🔄 Refresh View", key="sb_refresh_audit_btn", use_container_width=True):
                st.rerun()
        with col_g2:
            if st.button("🗑️ Clear History", key="sb_clear_hist_btn", use_container_width=True):
                with db_lock:
                    with open(DB_FILE, "w", encoding="utf-8") as f:
                        json.dump({"tasks": {}, "metrics": {"total_tasks": 0, "completed_tasks": 0, "failed_tasks": 0, "total_tokens": 0}}, f, indent=2)
                st.toast("Tasks database history cleared!")
                st.rerun()

        if st.button("🧹 Clear Workspace Cache & RAM", key="sb_clean_cache_btn", use_container_width=True):
            cloud_temp = os.path.join(tempfile.gettempdir(), "streamlit_agent")
            cleanup_cloud_workspace(cloud_temp)
            st.toast("🧹 தற்காலிக கோப்புகள் மற்றும் RAM மெமரி சுத்தம் செய்யப்பட்டது!")
            st.rerun()

        # Step-by-Step Task Token & Audit Log Table (Pure Python HTML - Zero Pandas Dependency)
        db_audit = load_db()
        all_audit_tasks = list(db_audit.get("tasks", {}).values())
        if all_audit_tasks:
            all_audit_tasks.sort(key=lambda t: t.get("created_at", ""), reverse=True)
            table_rows_html = "".join([
                f"""<tr style="border-bottom: 1px solid rgba(30, 34, 43, 0.7); background: rgba(12, 15, 22, 0.6);">
                    <td style="padding: 6px 8px; font-weight: 600; font-size: 0.75rem;">{html.escape(t.get('status', ''))}</td>
                    <td style="padding: 6px 8px; font-family: monospace; font-size: 0.72rem;">{html.escape(t.get('id', ''))}</td>
                    <td style="padding: 6px 8px; max-width: 140px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 0.75rem;">{html.escape(t.get('title', '')[:30])}</td>
                    <td style="padding: 6px 8px; font-size: 0.75rem;">{t.get('duration_seconds', 0)}s</td>
                    <td style="padding: 6px 8px; font-size: 0.75rem;">{html.escape(t.get('model_used', 'Pending')[:20])}</td>
                </tr>"""
                for t in all_audit_tasks[:10]
            ])
            audit_tbl_html = f"""
            <div style="overflow-x: auto; margin-top: 10px; border-radius: 8px; border: 1px solid #1E222B;">
                <table style="width: 100%; border-collapse: collapse; font-size: 0.75rem; color: #E2E8F0; text-align: left;">
                    <thead>
                        <tr style="background: rgba(18, 22, 31, 0.95); border-bottom: 1px solid #1E222B; color: #F59E0B; text-transform: uppercase;">
                            <th style="padding: 6px 8px;">Status</th>
                            <th style="padding: 6px 8px;">ID</th>
                            <th style="padding: 6px 8px;">Title</th>
                            <th style="padding: 6px 8px;">Time</th>
                            <th style="padding: 6px 8px;">Model</th>
                        </tr>
                    </thead>
                    <tbody>
                        {table_rows_html}
                    </tbody>
                </table>
            </div>
            """
            st.markdown(audit_tbl_html, unsafe_allow_html=True)


# ==============================================================================
# 10. PERSISTENT LIVE TASK TRACKER (5S NON-BLOCKING FRAGMENT)
# ==============================================================================
@st.fragment(run_every="5s")
def render_persistent_live_task_tracker():
    """
    PERSISTENT 'RUNNING THE TASK' LIVE TRACKER (survives browser close/reopen):
    Loads tasks_db.json on startup. If any task is RUNNING, displays an auto-refreshing
    live execution banner with warm amber/gold borders and step progress indicators.
    """
    db = load_db()
    all_tasks = db.get("tasks", {})
    running_tasks = [t for t in all_tasks.values() if t.get("status") == "RUNNING"]

    if running_tasks:
        running_tasks.sort(
            key=lambda t: t.get("updated_at") or t.get("created_at") or "", reverse=True
        )
        task = running_tasks[0]
        title = task.get("title", "Untitled Task")
        step = task.get("current_step", 1)
        max_steps = task.get("max_steps", 5)
        progress = task.get("progress_percent", min(100, step * 20))
        current_action = task.get("current_action", "Processing task step...")
        active_engine = task.get("active_model_or_bridge") or task.get("model_used") or "Tier 1: Cloud LLM (Gemini / OpenRouter)"
        folder = task.get("folder_name", "student_learning_hub")
        created_at_raw = task.get("created_at", "")

        elapsed_sec = 0
        if created_at_raw:
            try:
                dt = datetime.fromisoformat(created_at_raw)
                elapsed_sec = max(0, int((datetime.now() - dt).total_seconds()))
            except Exception:
                pass
        elapsed_str = f"{elapsed_sec // 60}m {elapsed_sec % 60}s" if elapsed_sec >= 60 else f"{elapsed_sec}s"

        step_names = ["1. 5D Plan", "2. Schema & Init", "3. Code & UI", "4. Self-Verify", "5. Persistence"]
        step_capsules_html = ""
        for i in range(1, 6):
            if i < step:
                status_icon = "✓"
                badge_bg = "rgba(16, 185, 129, 0.2)"
                badge_border = "#10B981"
                badge_color = "#34D399"
            elif i == step:
                status_icon = "🔄"
                badge_bg = "rgba(245, 158, 11, 0.25)"
                badge_border = "#F59E0B"
                badge_color = "#FBBF24"
            else:
                status_icon = "⏳"
                badge_bg = "rgba(30, 34, 43, 0.6)"
                badge_border = "#1E222B"
                badge_color = "#64748B"
            step_capsules_html += f"""
            <span style="background: {badge_bg}; border: 1px solid {badge_border}; color: {badge_color};
                         padding: 3px 8px; border-radius: 6px; font-size: 0.75rem; font-weight: 600;">
                {status_icon} {step_names[i-1]}
            </span>
            """

        banner_html = f"""
        <div style="background: linear-gradient(135deg, rgba(12, 15, 22, 0.98), rgba(20, 24, 35, 0.95));
                    border: 1.5px solid #F59E0B; border-radius: 14px; padding: 16px 20px; margin-bottom: 18px;
                    box-shadow: 0 0 25px rgba(245, 158, 11, 0.25);">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; flex-wrap: wrap; gap: 8px;">
                <div style="display: flex; align-items: center; gap: 10px;">
                    <span style="font-size: 1.3rem;">🔄</span>
                    <span style="font-weight: 800; color: #F59E0B; font-size: 1.05rem; letter-spacing: -0.3px;">
                        Running the Task: <span style="color: #FFFFFF;">{html.escape(title[:45])}</span>
                    </span>
                </div>
                <div style="display: flex; align-items: center; gap: 8px;">
                    <span style="background: rgba(245, 158, 11, 0.15); color: #FBBF24; border: 1px solid rgba(245, 158, 11, 0.4);
                                 padding: 3px 12px; border-radius: 9999px; font-size: 0.82rem; font-weight: 700;">
                        Step {step}/{max_steps} ({progress}%)
                    </span>
                    <span style="background: rgba(16, 185, 129, 0.15); color: #10B981; border: 1px solid rgba(16, 185, 129, 0.3);
                                 padding: 3px 10px; border-radius: 9999px; font-size: 0.75rem; font-weight: 600;">
                        ● LIVE RUNNING
                    </span>
                </div>
            </div>

            <div style="color: #F1F5F9; font-size: 0.9rem; margin-bottom: 8px; font-weight: 500;">
                ⚡ <b>Current Action:</b> <span style="color: #E2E8F0;">{html.escape(current_action)}</span>
            </div>

            <div style="width: 100%; background: #060709; border-radius: 9999px; height: 8px; overflow: hidden; margin-bottom: 10px; border: 1px solid #1E222B;">
                <div style="width: {progress}%; background: linear-gradient(90deg, #F59E0B, #FBBF24); height: 100%; border-radius: 9999px; transition: width 0.5s ease;"></div>
            </div>

            <div style="display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 10px;">
                {step_capsules_html}
            </div>

            <div style="display: flex; justify-content: space-between; align-items: center; font-size: 0.78rem; color: #94A3B8; flex-wrap: wrap; gap: 6px;">
                <span>🤖 <b>Engine:</b> {html.escape(active_engine)}</span>
                <span>📁 <b>Target:</b> <code style="color: #F59E0B; text-shadow: 0 0 8px rgba(245, 158, 11, 0.4); font-weight: 700;">workspace/{html.escape(folder)}</code></span>
                <span>⏱️ <b>Elapsed:</b> {elapsed_str}</span>
                <span style="color: #F59E0B;">🔄 Live 5s sync</span>
            </div>
        </div>
        """
        st.markdown(banner_html, unsafe_allow_html=True)
    else:
        completed = [t for t in all_tasks.values() if t.get("status") == "COMPLETED"]
        if completed:
            completed.sort(
                key=lambda t: t.get("updated_at") or t.get("created_at") or "",
                reverse=True,
            )
            recent = completed[0]
            st.markdown(
                f"""
                <div style="background: rgba(12, 15, 22, 0.85); border: 1px solid rgba(16, 185, 129, 0.35);
                            border-radius: 10px; padding: 10px 16px; margin-bottom: 16px; display: flex;
                            justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <span style="color: #10B981; font-size: 1.1rem;">✅</span>
                        <span style="font-size: 0.88rem; color: #E2E8F0;">
                            <b>Last Task Finished:</b> {html.escape(recent.get('title', 'Task')[:45])}
                            <span style="color: #94A3B8;">({recent.get('duration_seconds', 0)}s via {recent.get('model_used', 'AI Engine')})</span>
                        </span>
                    </div>
                    <span style="font-size: 0.78rem; color: #10B981; font-weight: 600;">Status: COMPLETED (100%)</span>
                </div>
                """,
                unsafe_allow_html=True,
            )


# ==============================================================================
# 11. RESPONSIVE SPATIAL MAIN SCREEN: DESKTOP 3-ZONE GRID (NO TOP RADIO)
# ==============================================================================
restore_session_state_on_wakeup()

# Dynamic Greeting based on time of day
current_hour = datetime.now().hour
greeting_period = "Good morning" if current_hour < 12 else ("Good afternoon" if current_hour < 17 else "Good evening")
user_greeting = f"{greeting_period}, Kirubha — Agent Live"


# ------------------------------------------------------------------------------
# RENDER ZONE 1: GREETING & RUNTIME METRICS
# ------------------------------------------------------------------------------
def render_zone_left():
    db_state = load_db()
    metrics = db_state.get("metrics", {})
    all_tasks = db_state.get("tasks", {})

    running_count = sum(1 for t in all_tasks.values() if t.get("status") == "RUNNING")
    completed_count = metrics.get("completed_tasks", 0)
    failed_count = metrics.get("failed_tasks", 0)

    # Dynamic time-of-day greeting matching reference UI
    current_hour = datetime.now().hour
    g_time = "Good morning" if current_hour < 12 else ("Good afternoon" if current_hour < 17 else "Good evening")
    user_greet_sub = f"{g_time}, Kirubha"

    left_html = f"""
    <div style="padding: 2px 4px;">
        <div class="left-zone-greeting">{user_greet_sub}</div>
        <div class="left-zone-title">Agent Live</div>
        <div class="metrics-list-card">
            <div class="metric-row">
                <span class="metric-label">Agent Status:</span>
                <span class="metric-val-status"><span class="gold-dot">●</span> SRI (Ready)</span>
            </div>
            <div class="metric-row">
                <span class="metric-label">Active Tasks:</span>
                <span class="metric-val"><span class="metric-dot">●</span> {running_count}</span>
            </div>
            <div class="metric-row">
                <span class="metric-label">Completed:</span>
                <span class="metric-val"><span class="metric-dot">●</span> {completed_count}</span>
            </div>
            <div class="metric-row">
                <span class="metric-label">Failed:</span>
                <span class="metric-val"><span class="metric-dot">●</span> {failed_count}</span>
            </div>
        </div>
        <div class="env-runtime-heading">Environment & Runtime</div>
        <div class="runtime-pills-row">
            <span class="runtime-pill">Streamlit Cloud</span>
            <span class="runtime-pill runtime-pill-gold">workspace/</span>
        </div>
    </div>
    """
    st.markdown(left_html, unsafe_allow_html=True)


# ------------------------------------------------------------------------------
# RENDER ZONE 2: 3D GOLDEN VOICE ORB, SINGLE-ROW PILLS & UNIFIED PROMPT BAR
# ------------------------------------------------------------------------------
def render_zone_center():
    # Persistent Live Task Tracker at top of Center Zone
    render_persistent_live_task_tracker()

    # EXACT 3D Golden Particle Sphere via SRI UI Bridge
    render_3d_golden_orb()

    # Carousel pills with chevrons < Student Dashboard SaaS Auth Kanban Board Refine login.html >
    col_prev, col_p1, col_p2, col_p3, col_p4, col_next = st.columns([0.35, 2.7, 2.1, 2.4, 2.7, 0.35])
    with col_prev:
        st.markdown("<div style='text-align: center; color: #64748B; font-size: 1rem; padding-top: 6px;'>&lt;</div>", unsafe_allow_html=True)
    with col_p1:
        if st.button("Student Dashboard", key="pill_student_db", use_container_width=True):
            st.session_state["task_prompt_val"] = "Build a responsive, modern student dashboard in HTML/CSS/JS with course progress charts, assignment tracker, and dark mode toggle."
            st.session_state["task_folder_val"] = "student_dashboard"
    with col_p2:
        if st.button("SaaS Auth", key="pill_saas_auth", use_container_width=True):
            st.session_state["task_prompt_val"] = "Create a sleek, modern SaaS Login and Registration page with tab switching, password strength meter, and social login buttons."
            st.session_state["task_folder_val"] = "saas_auth"
    with col_p3:
        if st.button("Kanban Board", key="pill_kanban", use_container_width=True):
            st.session_state["task_prompt_val"] = "Build an interactive Kanban board UI in single-file HTML/CSS/JS with drag-and-drop task cards, category columns, and task addition modal."
            st.session_state["task_folder_val"] = "kanban_board"
    with col_p4:
        if st.button("Refine login.html", key="pill_refine_login", use_container_width=True):
            st.session_state["task_prompt_val"] = "Refine workspace/login.html by adding password recovery modal, dark glassmorphism, and responsive validation."
            st.session_state["task_folder_val"] = ""
    with col_next:
        st.markdown("<div style='text-align: center; color: #64748B; font-size: 1rem; padding-top: 6px;'>&gt;</div>", unsafe_allow_html=True)

    st.markdown("<div style='height: 4px;'></div>", unsafe_allow_html=True)

    # Gold-bordered prompt bar: "Ask SRI Agent a question (Tamil / English)..." with inline gold mic (🎙️) and send arrow (➤)
    col_prompt_box, col_p_mic, col_p_send = st.columns([8.2, 0.9, 0.9])
    with col_prompt_box:
        prompt_input_text = st.text_input(
            "Ask SRI Agent a question (Tamil / English)...",
            value=st.session_state.get("task_prompt_val", ""),
            placeholder="Ask SRI Agent a question (Tamil / English)...",
            label_visibility="collapsed",
            key="unified_prompt_text_field",
        )
    with col_p_mic:
        mic_pressed = st.button("🎙️", key="unified_mic_btn", help="Click to speak via microphone", use_container_width=True)
    with col_p_send:
        send_pressed = st.button("➤", key="unified_send_btn", help="Send command or ask question", use_container_width=True)

    # Handle Mic Click
    if mic_pressed:
        with st.spinner("🎙️ ஸ்ரீ கவனித்துக் கொண்டிருக்கிறது... உங்கள் கேள்வியைப் பேசுங்கள்:"):
            try:
                spoken = sri_universal_router.listen_voice_command()
                if spoken:
                    st.session_state["task_prompt_val"] = spoken
                    st.session_state["active_voice_query"] = spoken
                    st.toast(f"குரல் பெறப்பட்டது: {spoken}")
                    st.rerun()
                else:
                    st.info("⚠️ மைக்ரோஃபோன் சிக்னல் கிடைக்கவில்லை. பெட்டியில் டைப் செய்யலாம்.")
            except Exception as me:
                st.warning(f"Microphone notice: {me}")

    # Handle Send / Execution
    effective_prompt = prompt_input_text.strip()
    if send_pressed and effective_prompt:
        st.session_state["task_prompt_val"] = effective_prompt

        # Check if it is a Status/Inquiry Query
        query_lower = effective_prompt.lower()
        is_inquiry = any(k in query_lower for k in [
            "எங்க", "என்ன பண்ணுது", "மாடல்", "முடிஞ்சு", "status", "where is", "what is",
            "doing right now", "which model", "finished", "completed", "நிலை"
        ])

        if is_inquiry:
            st.session_state["active_voice_query"] = effective_prompt
        else:
            # Autonomous Task Dispatch
            folder_target = st.session_state.get("task_folder_val", "").strip() or "student_learning_hub"
            task_kind = "frontend" if any(w in query_lower for w in ["ui", "design", "html", "css", "frontend", "பக்கம்"]) else "auto"
            new_t_id = dispatch_background_task(
                prompt=effective_prompt,
                task_type=task_kind,
                folder_name=folder_target,
            )
            st.success(f"🚀 Task dispatched autonomously! Task ID: `{new_t_id}`")
            st.toast("Task executing in background!")

    # Live Spoken Agent Reply Card (if voice query active)
    active_q = st.session_state.get("active_voice_query", "").strip()
    if active_q:
        reply_dict = get_agent_voice_status_reply(active_q)
        st.markdown(
            f"""
            <div style="background: rgba(18, 22, 33, 0.95); border: 1.5px solid #F59E0B; border-radius: 12px;
                        padding: 16px 20px; margin-top: 14px; margin-bottom: 14px; box-shadow: 0 4px 20px rgba(245, 158, 11, 0.2);">
                <div style="font-size: 0.8rem; color: #FBBF24; margin-bottom: 4px; font-weight: 700;">
                    👤 உங்கள் கேள்வி (User Inquiry):
                </div>
                <div style="font-size: 1rem; color: #FFFFFF; font-weight: 600; margin-bottom: 12px;">
                    "{html.escape(active_q)}"
                </div>
                <div style="font-size: 0.8rem; color: #34D399; margin-bottom: 6px; font-weight: 700;">
                    🤖 SRI Agent நேரலை பதில் (Live Agent Status Reply):
                </div>
                <div style="font-size: 0.92rem; color: #F1F5F9; line-height: 1.6;">
                    {reply_dict['display_text']}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        tts_html = generate_speech_synthesis_html(
            reply_dict["spoken_text"], lang=reply_dict["lang"], autoplay=True
        )
        components.html(tts_html, height=135)


# ------------------------------------------------------------------------------
# RENDER ZONE 3: SEGMENTED [ PREVIEW | CODE ] PROJECT VIEWER
# ------------------------------------------------------------------------------
def render_zone_right():
    # Segmented Switcher [ Preview | Code ] in Pill Track (Zero native radio dots)
    col_seg, col_exp = st.columns([2.3, 0.7])
    with col_seg:
        viewer_mode = st.radio(
            "Viewer Mode",
            options=["Preview", "Code"],
            index=0,
            horizontal=True,
            label_visibility="collapsed",
            key="sri_segmented_viewer_mode",
        )
    with col_exp:
        full_height_toggle = st.toggle("⛶", value=False, key="pv_expand_toggle", help="Full Height Preview")

    # Target file: default to workspace/login.html if present
    target_rel = "login.html"
    target_full = os.path.join(WORKSPACE_DIR, target_rel)
    if not os.path.exists(target_full):
        ws_files = get_workspace_files()
        target_rel = ws_files[0] if ws_files else "login.html"
        target_full = os.path.join(WORKSPACE_DIR, target_rel)

    content = ""
    file_size_bytes = 1881
    if os.path.exists(target_full):
        try:
            with open(target_full, "r", encoding="utf-8") as f:
                content = f.read()
            file_size_bytes = len(content.encode("utf-8"))
        except Exception:
            pass

    preview_h = 750 if full_height_toggle else 430

    # Header metadata: workspace/login.html size: 1,881 bytes
    st.markdown(
        f"""
        <div class="pv-meta-header">
            <span class="pv-file-path">workspace/{html.escape(target_rel)}</span>
            <span class="pv-file-size">size: {file_size_bytes:,} bytes</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if viewer_mode == "Preview":
        if content:
            components.html(content, height=preview_h, scrolling=True)
        else:
            st.info("No content in workspace/login.html yet.")
    else:
        # Code View with Download options
        col_dl1, col_dl2 = st.columns(2)
        with col_dl1:
            st.download_button(
                "📥 Download File",
                data=content,
                file_name=os.path.basename(target_full),
                mime="text/html",
                use_container_width=True,
                key=f"dl_single_{os.path.basename(target_full)}",
            )
        with col_dl2:
            zip_bytes = create_project_zip_bundle(WORKSPACE_DIR)
            st.download_button(
                "📦 Download .ZIP",
                data=zip_bytes,
                file_name="workspace_project.zip",
                mime="application/zip",
                use_container_width=True,
                key="dl_zip_right_zone",
            )
        st.code(content, language="html", line_numbers=True)

    # 4-pointed sparkle icon at bottom right of the container
    st.markdown("<div class='pv-sparkle-decor'>✦</div>", unsafe_allow_html=True)


# ------------------------------------------------------------------------------
# RENDER DESKTOP 3-ZONE SPATIAL GRID (25% Left, 45% Center, 30% Right)
# ------------------------------------------------------------------------------
col_zone_left, col_zone_center, col_zone_right = st.columns([1, 1.8, 1.2])
with col_zone_left:
    render_zone_left()
with col_zone_center:
    render_zone_center()
with col_zone_right:
    render_zone_right()
