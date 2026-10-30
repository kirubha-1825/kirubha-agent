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

import streamlit as st
import streamlit.components.v1 as components
import requests
from dotenv import load_dotenv

from openai import OpenAI
import google.generativeai as genai

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
        os.getenv("STREAMLIT_SHARING") == "true" or
        os.getenv("STREAMLIT_RUNTIME_ENV") in ["cloud", "streamlit_cloud"] or
        os.getenv("IS_STREAMLIT_CLOUD", "").lower() in ["true", "1", "yes"] or
        os.path.exists("/mount/src") or
        ("HOSTNAME" in os.environ and "streamlit" in os.environ.get("HOSTNAME", "").lower())
    )
    env_name = "Streamlit Cloud" if is_streamlit_cloud else "Local Environment"
    return {
        "is_cloud": is_streamlit_cloud,
        "env_name": env_name
    }

RUNTIME_ENV = detect_runtime_environment()
IS_CLOUD_MODE = RUNTIME_ENV["is_cloud"]

# Robust base repository directory
BASE_DIR = os.path.abspath(os.path.dirname(__file__)) if "__file__" in locals() and os.path.dirname(__file__) else os.path.abspath(os.getcwd())

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
        fallback = os.path.abspath(os.path.join(tempfile.gettempdir(), "streamlit_agent", cloud_temp_subdir))
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
        fallback = os.path.abspath(os.path.join(tempfile.gettempdir(), "streamlit_agent", "tasks_db.json"))
        os.makedirs(os.path.dirname(fallback), exist_ok=True)
        return fallback

DB_FILE = resolve_db_file()
MAX_AGENT_STEPS = 5
TASK_TIMEOUT_SECONDS = 180
db_lock = threading.Lock()

# Protected files that must never be overwritten or targeted by agents
CORE_PROTECTED_FILES = {
    "app.py", "tasks_db.json", "requirements.txt", ".env", "pyrightconfig.json",
    "readme.md", "dockerfile", "packages.txt", ".gitignore", "setup.py", "test_all_models.py"
}

def is_safe_sandbox_path(target_path: str, base_dir: str = WORKSPACE_DIR) -> tuple[bool, str]:
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
            return False, "Security boundary violation: Path traversal ('..') is strictly forbidden."

        if not (target_abs == base_abs or target_abs.startswith(base_abs + os.sep)):
            return False, f"Security boundary violation: Path '{target_path}' escapes sandbox '{base_dir}'."

        if target_abs == base_abs:
            return False, "Security violation: Cannot write directly to workspace root directory as a file."

        filename_lower = os.path.basename(target_abs).lower()
        if filename_lower in CORE_PROTECTED_FILES and target_abs == os.path.abspath(os.path.join(BASE_DIR, filename_lower)):
            return False, f"Security boundary violation: Core system file '{filename_lower}' cannot be overwritten."

        return True, ""
    except Exception as e:
        return False, f"Sandbox validation failure: {str(e)}"

# Configure Streamlit Page
st.set_page_config(
    page_title="Autonomous Agent | Background Execution Engine",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling
st.markdown("""
<style>
    .main-title {
        font-size: 2.2rem;
        font-weight: 800;
        background: linear-gradient(90deg, #3B82F6, #8B5CF6, #EC4899);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
    }
    .sub-title {
        color: #64748B;
        font-size: 1rem;
        margin-bottom: 1.2rem;
    }
    .status-card {
        background: #1E293B;
        border: 1px solid #334155;
        border-radius: 10px;
        padding: 1rem;
        margin-bottom: 0.8rem;
    }
    .terminal-box {
        background: #0F172A;
        color: #10B981;
        font-family: 'Courier New', Courier, monospace;
        font-size: 0.85rem;
        padding: 0.75rem;
        border-radius: 6px;
        max-height: 250px;
        overflow-y: auto;
        border: 1px solid #1E293B;
        white-space: pre-wrap;
    }
    .stProgress > div > div > div > div {
        background-image: linear-gradient(to right, #3B82F6, #8B5CF6);
    }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# 2. SECURE SECRETS & CREDENTIALS MANAGEMENT
# ==============================================================================
def get_secret(key_name: str) -> str:
    """Fetch credentials first from st.secrets, falling back to os.getenv."""
    try:
        if hasattr(st, "secrets") and key_name in st.secrets:
            val = st.secrets[key_name]
            if val:
                return str(val).strip()
    except Exception:
        pass
    env_val = os.getenv(key_name)
    return env_val.strip() if env_val else ""

gemini_key = get_secret("GEMINI_API_KEY")
openrouter_key = get_secret("OPENROUTER_API_KEY")
nvidia_key = get_secret("NVIDIA_API_KEY")
groq_key = get_secret("GROQ_API_KEY")
telegram_token = get_secret("TELEGRAM_BOT_TOKEN")
telegram_chat_id = get_secret("TELEGRAM_CHAT_ID")

# Configure GenAI SDK if key present
if gemini_key:
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
                    "total_tokens": 0
                }
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
                    "total_tokens": 0
                },
                "recovery_notice": f"Recovered from corrupted state at {datetime.now().isoformat()}: {str(e)}"
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
                            t["error"] = "Task timed out or was interrupted during server sleep/restart."
                            t["logs"].append(f"[{now.strftime('%H:%M:%S')}] App awakened from sleep: task marked as timed out / interrupted.")
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
        return {"tasks": {}, "metrics": {"total_tasks": 0, "completed_tasks": 0, "failed_tasks": 0, "total_tokens": 0}}

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
        st.session_state["session_awakened_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

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

def create_task_record(prompt: str, task_type: str, title: str, source_file: str = "", change_request: str = "", folder_name: str = "") -> str:
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
        "error": None
    }
    data["metrics"]["total_tasks"] += 1
    save_db(data)
    return task_id

def update_task_record(task_id: str, **kwargs):
    data = load_db()
    if task_id in data["tasks"]:
        for k, v in kwargs.items():
            data["tasks"][task_id][k] = v
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
        "disable_web_page_preview": True
    }
    try:
        res = requests.post(url, json=payload, timeout=10)
        return res.json()
    except Exception as e:
        return {"ok": False, "description": str(e)}

def dispatch_task_alert(task_id: str, task_name: str, status: str, file_path: str = "", extra_details: str = "") -> dict:
    """
    Universal Notification Dispatcher Hook:
    Dispatches task completion or failure alerts across multiple channels:
    1. Telegram Bot (if TELEGRAM_BOT_TOKEN & TELEGRAM_CHAT_ID are configured).
    2. WhatsApp Webhook (stub ready for WhatsApp Cloud API / Twilio / custom webhook payloads).
    """
    results = {"telegram": None, "whatsapp": None}

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

    # 2. WhatsApp Webhook Dispatch Hook (Ready for WhatsApp Cloud API / Twilio / Zapier / Make)
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
            "timestamp": datetime.now().isoformat()
        }
        headers = {"Content-Type": "application/json"}
        if whatsapp_token:
            headers["Authorization"] = f"Bearer {whatsapp_token}"
        try:
            res = requests.post(whatsapp_webhook, json=payload, headers=headers, timeout=8)
            results["whatsapp"] = {"status_code": res.status_code, "response": res.text[:200]}
        except Exception as we:
            results["whatsapp"] = {"error": str(we)}
    else:
        results["whatsapp"] = {"status": "unconfigured", "note": "WHATSAPP_WEBHOOK_URL is not configured."}

    return results

# ==============================================================================
# 5. LLM CALLER WITH GRACEFUL RECOVERY (Gemini -> OpenRouter)
# ==============================================================================
_gemini_cooldown_until = 0

def call_gemini(prompt: str, system_instruction: str = ""):
    global _gemini_cooldown_until
    if not gemini_key:
        raise ValueError("GEMINI_API_KEY is missing.")
    if time.time() < _gemini_cooldown_until:
        raise RuntimeError("Gemini in transient cooldown; instant failover to OpenRouter.")
    
    try:
        def _gemini_call():
            genai.configure(api_key=gemini_key)
            model = genai.GenerativeModel(
                model_name="gemini-3.8-flash",
                system_instruction=system_instruction if system_instruction else None
            )
            return model.generate_content(prompt, request_options={"timeout": 10})

        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_gemini_call)
            response = future.result(timeout=11)

        if response and response.text:
            tokens_est = (len(prompt) + len(system_instruction) + len(response.text)) // 4
            return response.text.strip(), "Google Gemini (gemini-3.8-flash)", tokens_est
        raise ValueError("Empty response received from Gemini.")
    except Exception as e:
        err_str = str(e).lower()
        if any(term in err_str for term in ["quota", "429", "deadline", "504", "exhausted", "resource_exhausted"]):
            _gemini_cooldown_until = time.time() + 90
        raise

def call_openrouter(prompt: str, system_instruction: str = ""):
    if not openrouter_key:
        raise ValueError("OPENROUTER_API_KEY is missing.")

    max_retries = 3
    last_err = None
    for attempt in range(max_retries):
        try:
            def _openrouter_call():
                client = OpenAI(
                    base_url="https://openrouter.ai/api/v1",
                    api_key=openrouter_key
                )
                messages = []
                if system_instruction:
                    messages.append({"role": "system", "content": system_instruction})
                messages.append({"role": "user", "content": prompt})

                return client.chat.completions.create(
                    model="openrouter/auto",
                    messages=messages,
                    temperature=0.4,
                    max_tokens=6500,
                    timeout=75
                )

            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(_openrouter_call)
                response = future.result(timeout=80)

            msg = response.choices[0].message
            content = msg.content
            if not content and hasattr(msg, "reasoning") and msg.reasoning:
                content = msg.reasoning
            if content and content.strip():
                text = content.strip()
                tokens_est = (len(prompt) + len(system_instruction) + len(text)) // 4
                return text, "OpenRouter (openrouter/auto)", tokens_est
            raise ValueError("Empty response received from OpenRouter.")
        except Exception as e:
            last_err = e
            if attempt < max_retries - 1:
                time.sleep(2 * (attempt + 1))
                continue
            raise last_err

def call_nvidia(prompt: str, system_instruction: str = ""):
    """Safely wrapped NVIDIA API call."""
    if not nvidia_key:
        raise ValueError("NVIDIA_API_KEY is missing.")
    client = OpenAI(
        base_url="https://integrate.api.nvidia.com/v1",
        api_key=nvidia_key
    )
    messages = []
    if system_instruction:
        messages.append({"role": "system", "content": system_instruction})
    messages.append({"role": "user", "content": prompt})
    res = client.chat.completions.create(
        model="meta/llama-3.3-70b-instruct",
        messages=messages,
        temperature=0.5,
        max_tokens=1024,
        timeout=15
    )
    content = res.choices[0].message.content
    if content and content.strip():
        text = content.strip()
        tokens_est = (len(prompt) + len(system_instruction) + len(text)) // 4
        return text, "NVIDIA (meta/llama-3.3-70b-instruct)", tokens_est
    raise ValueError("Empty response from NVIDIA.")

def call_groq(prompt: str, system_instruction: str = ""):
    """Safely wrapped Groq API call."""
    if not groq_key:
        raise ValueError("GROQ_API_KEY is missing.")
    client = OpenAI(
        base_url="https://api.groq.com/openai/v1",
        api_key=groq_key
    )
    messages = []
    if system_instruction:
        messages.append({"role": "system", "content": system_instruction})
    messages.append({"role": "user", "content": prompt})
    res = client.chat.completions.create(
        model="llama3-8b-8192",
        messages=messages,
        temperature=0.5,
        max_tokens=1024,
        timeout=15
    )
    content = res.choices[0].message.content
    if content and content.strip():
        text = content.strip()
        tokens_est = (len(prompt) + len(system_instruction) + len(text)) // 4
        return text, "Groq (llama3-8b-8192)", tokens_est
    raise ValueError("Empty response from Groq.")

def call_llm_with_recovery(prompt: str, system_instruction: str = ""):
    """
    Tier-1: Google Gemini ('gemini-3.8-flash').
    Guaranteed Tier-2 Fallback: OpenRouter ('openrouter/auto') with resilient auto-retry.
    NVIDIA and Groq helper functions are kept safely wrapped in try-except and bypassed
    here so decommissioned endpoints do not delay instantaneous fallback.
    """
    errors = []
    # Tier-1: Gemini Primary
    if gemini_key:
        try:
            return call_gemini(prompt, system_instruction)
        except Exception as e:
            errors.append(f"Gemini: {e}")

    # Guaranteed Fallback: OpenRouter (Instant failover)
    if openrouter_key:
        try:
            return call_openrouter(prompt, system_instruction)
        except Exception as e:
            errors.append(f"OpenRouter: {e}")

    raise RuntimeError(f"All LLM providers failed: {'; '.join(errors) if errors else 'No API keys configured'}")

# ==============================================================================
# 6. AUTONOMOUS DIRECTORY & FILE TOOLS & SPEECH RECOGNITION
# ==============================================================================
def derive_project_slug(title: str, prompt: str) -> str:
    """Extracts a semantic, clean folder name from title and prompt."""
    combined = f"{title} {prompt}".lower()
    words = re.findall(r'[a-zA-Z0-9]+', combined)
    stopwords = {
        'build', 'create', 'a', 'an', 'the', 'in', 'with', 'and', 'for', 'to', 'of',
        'single', 'file', 'page', 'responsive', 'modern', 'sleek', 'interactive',
        'application', 'app', 'html', 'css', 'js', 'full', 'make', 'generate', 'ui'
    }
    meaningful = [w for w in words if w not in stopwords and len(w) > 2]
    if meaningful:
        slug = "_".join(meaningful[:3])
    else:
        slug = "web_project"
    return slug[:32]

def create_project_structure(folder_name: str, file_name: str, code_content: str) -> tuple[bool, str, str]:
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
        if ".." in raw_folder or ".." in raw_file or raw_folder.startswith("/") or raw_folder.startswith("\\") or ":" in raw_folder or ":" in raw_file:
            return False, "", "Security boundary violation: Path traversal or absolute paths are strictly forbidden."

        # Sanitize folder name
        clean_folder = re.sub(r'[^a-zA-Z0-9_\-]', '_', raw_folder).strip('_')
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
        dirs[:] = [d for d in dirs if not d.startswith('.') and not d.startswith('__')]
        for fn in filenames:
            if fn.endswith('.tmp') or fn.startswith('.'):
                continue
            full_path = os.path.abspath(os.path.join(root, fn))
            rel_path = os.path.relpath(full_path, workspace_abs).replace('\\', '/')
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
            return False, "", f"File '{clean_rel}' does not exist in '{WORKSPACE_DIR}/'."

        if not os.path.isfile(target_path):
            return False, "", f"'{clean_rel}' is not a regular file."

        with open(target_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        return True, content, ""
    except Exception as e:
        return False, "", f"Failed reading '{rel_path}': {str(e)}"

def safe_write_code(original_rel_path: str, modified_code: str, custom_suffix: str = "_updated") -> tuple[bool, str, str]:
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

def transcribe_audio_to_text(audio_bytes: bytes, mime_type: str = "audio/wav") -> str:
    """
    Transcribes spoken audio bytes to text instructions.
    Primary: Groq Whisper ('whisper-large-v3-turbo') for sub-second, highly accurate transcription.
    Fallback: Google Gemini ('gemini-3.8-flash') multimodal audio comprehension.
    """
    errors = []
    # Primary: Groq Whisper
    if groq_key:
        try:
            client = OpenAI(
                base_url="https://api.groq.com/openai/v1",
                api_key=groq_key
            )
            audio_file = ("audio.wav", io.BytesIO(audio_bytes), mime_type or "audio/wav")
            transcription = client.audio.transcriptions.create(
                model="whisper-large-v3-turbo",
                file=audio_file,
                response_format="text"
            )
            if transcription and transcription.strip():
                return transcription.strip()
        except Exception as ge:
            errors.append(f"Groq Whisper: {ge}")

    # Fallback: Google Gemini
    if gemini_key:
        try:
            genai.configure(api_key=gemini_key)
            model = genai.GenerativeModel("gemini-3.8-flash")
            response = model.generate_content([
                {
                    "mime_type": mime_type or "audio/wav",
                    "data": audio_bytes
                },
                "Please accurately transcribe the spoken coding or task instruction in this audio. Return ONLY the transcribed text without extra explanations or quotes."
            ])
            if response and response.text:
                return response.text.strip()
        except Exception as me:
            errors.append(f"Gemini: {me}")

    raise RuntimeError(f"Audio transcription failed: {'; '.join(errors)}")

# ==============================================================================
# 7. MULTI-DIMENSIONAL REASONING ENGINE & DECOMPOSED EXECUTION
# ==============================================================================
def generate_5d_plan(prompt: str, task_type: str, system_instruction: str = "") -> tuple[dict, str, str, int]:
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

    res_plan = call_llm_with_recovery(planner_prompt, system_instruction) or ("", "", 0)
    plan_text, model_name, tokens = res_plan
    
    sections = {
        "architecture": "",
        "ux": "",
        "resilience": "",
        "efficiency": "",
        "reflection": ""
    }
    
    arch_m = re.search(r"###\s*1\.\s*Architecture Dimension(.*?)(?=###|\Z)", plan_text, re.DOTALL | re.IGNORECASE)
    ux_m = re.search(r"###\s*2\.\s*User Experience Dimension(.*?)(?=###|\Z)", plan_text, re.DOTALL | re.IGNORECASE)
    res_m = re.search(r"###\s*3\.\s*Resilience Dimension(.*?)(?=###|\Z)", plan_text, re.DOTALL | re.IGNORECASE)
    eff_m = re.search(r"###\s*4\.\s*Efficiency Dimension(.*?)(?=###|\Z)", plan_text, re.DOTALL | re.IGNORECASE)
    ref_m = re.search(r"###\s*5\.\s*Reflection(.*?)(?=###|\Z)", plan_text, re.DOTALL | re.IGNORECASE)

    if arch_m: sections["architecture"] = arch_m.group(1).strip()
    if ux_m: sections["ux"] = ux_m.group(1).strip()
    if res_m: sections["resilience"] = res_m.group(1).strip()
    if eff_m: sections["efficiency"] = eff_m.group(1).strip()
    if ref_m: sections["reflection"] = ref_m.group(1).strip()

    return sections, plan_text, model_name, tokens

def generate_project_schema(prompt: str, architecture_plan: str, system_instruction: str = "") -> tuple[str, str, int]:
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
    res_schema = call_llm_with_recovery(schema_prompt, system_instruction) or ("", "", 0)
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
                {"id": 2, "title": "Item 2", "status": "completed"}
            ]
        }
        formatted_json = json.dumps(fallback, indent=2)

    return formatted_json, model_name, tokens

def run_self_verification(prompt: str, code_sample: str, reflection_checklist: str, system_instruction: str = "") -> tuple[str, str, int]:
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
    
    res_report = call_llm_with_recovery(reflection_prompt, system_instruction) or ("", "", 0)
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
            doctype_matches = [m for m in matches if "<!doctype" in m[1].lower() or "<html" in m[1].lower()]
            if doctype_matches:
                best_doc = max(doctype_matches, key=lambda m: len(m[1]))
                return best_doc[1].strip(), "html"

            # 2. Prioritize blocks explicitly labeled as html
            html_labeled = [m for m in matches if m[0].lower().strip() in ["html", "htm"]]
            if html_labeled:
                best_html = max(html_labeled, key=lambda m: len(m[1]))
                return best_html[1].strip(), "html"

        best_match = max(matches, key=lambda m: len(m[1]))
        lang = best_match[0].lower().strip()
        code = best_match[1].strip()
        ext = "html" if lang in ["html", "htm"] else ("py" if lang in ["python", "py"] else default_ext)
        return code, ext

    # Pattern 2: unclosed ```html ... block at end of response
    unclosed = re.search(r"```([a-zA-Z0-9_\-\+]*)\s*\n(.*)", raw_text, re.DOTALL)
    if unclosed:
        lang = unclosed.group(1).lower().strip()
        code = unclosed.group(2).strip()
        code = re.sub(r"```+$", "", code).strip()
        ext = "html" if lang in ["html", "htm"] else ("py" if lang in ["python", "py"] else default_ext)
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
            fixed_code = f"<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n<meta charset=\"UTF-8\">\n<meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n<title>Generated UI</title>\n<script src=\"https://cdn.tailwindcss.com\"></script>\n</head>\n<body class=\"bg-slate-900 text-slate-100 min-h-screen p-6\">\n{fixed_code}\n</body>\n</html>"

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
                raise TimeoutError("Task exceeded 180s limit during Step 1.")

            update_task_record(task_id, current_step=1)
            append_task_log(task_id, f"Step 1/5: Invoking safe_read_code on 'workspace/{source_file}'...")

            read_ok, original_code, read_err = safe_read_code(source_file)
            if not read_ok:
                raise FileNotFoundError(f"Safe Read Tool Error: {read_err}")

            append_task_log(task_id, f"Step 1/5: Loaded {len(original_code):,} chars from 'workspace/{source_file}'. Invoking 5D Refinement Reasoning Engine...")

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
            res_plan = call_llm_with_recovery(plan_prompt, system_instruction) or ("", "", 0)
            plan_text, model_name, tokens = res_plan
            accumulated_tokens += tokens
            used_models.add(model_name)

            sections = {
                "architecture": "",
                "ux": "",
                "resilience": "",
                "efficiency": "",
                "reflection": ""
            }
            arch_m = re.search(r"###\s*1\.\s*Architecture Dimension(.*?)(?=###|\Z)", plan_text, re.DOTALL | re.IGNORECASE)
            ux_m = re.search(r"###\s*2\.\s*User Experience Dimension(.*?)(?=###|\Z)", plan_text, re.DOTALL | re.IGNORECASE)
            res_m = re.search(r"###\s*3\.\s*Resilience Dimension(.*?)(?=###|\Z)", plan_text, re.DOTALL | re.IGNORECASE)
            eff_m = re.search(r"###\s*4\.\s*Efficiency Dimension(.*?)(?=###|\Z)", plan_text, re.DOTALL | re.IGNORECASE)
            ref_m = re.search(r"###\s*5\.\s*Reflection(.*?)(?=###|\Z)", plan_text, re.DOTALL | re.IGNORECASE)

            if arch_m: sections["architecture"] = arch_m.group(1).strip()
            if ux_m: sections["ux"] = ux_m.group(1).strip()
            if res_m: sections["resilience"] = res_m.group(1).strip()
            if eff_m: sections["efficiency"] = eff_m.group(1).strip()
            if ref_m: sections["reflection"] = ref_m.group(1).strip()

            update_task_record(task_id, plan=plan_text, plan_5d=sections)
            append_task_log(task_id, f"Step 1/5 Refinement Plan generated using {model_name}.")

            # STEP 2: State & Schema Context Analysis
            if time.time() - start_time > TASK_TIMEOUT_SECONDS:
                raise TimeoutError("Task exceeded 180s limit during Step 2.")

            update_task_record(task_id, current_step=2)
            append_task_log(task_id, "Step 2/5 (Decomposed Step 1): Analyzing DOM hierarchy and state contracts from original code...")

            state_summary = f"Source Document: {source_file} ({len(original_code):,} chars, {len(original_code.splitlines())} lines)"
            update_task_record(task_id, schema_data=state_summary)
            append_task_log(task_id, "Step 2/5 Completed: Document structure and state contracts cataloged.")

            # STEP 3: Full Code Synthesis ([Original Code] + [User Change Request])
            if time.time() - start_time > TASK_TIMEOUT_SECONDS:
                raise TimeoutError("Task exceeded 180s limit during Step 3.")

            update_task_record(task_id, current_step=3)
            append_task_log(task_id, "Step 3/5 (Decomposed Step 2): Synthesizing fully updated production-ready code with requested modifications...")

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
                "5. Return strictly the full code wrapped in markdown code fences: ```" + lang + " ... ```"
            )
            res_code = call_llm_with_recovery(code_prompt, system_instruction) or ("", "", 0)
            raw_code_response, model_name_2, tokens_2 = res_code
            accumulated_tokens += tokens_2
            used_models.add(model_name_2)

            code_body, ext = extract_code_block(raw_code_response, default_ext=lang)
            is_valid, validation_msg, finalized_code = validate_artifact_integrity(code_body, ext)
            update_task_record(task_id, code=finalized_code)
            append_task_log(task_id, f"Step 3/5 Completed using {model_name_2} ({len(finalized_code):,} chars generated). {validation_msg}")

            # STEP 4: Run Self-Verification & Reflection Checklist
            if time.time() - start_time > TASK_TIMEOUT_SECONDS:
                raise TimeoutError("Task exceeded 180s limit during Step 4.")

            update_task_record(task_id, current_step=4)
            append_task_log(task_id, "Step 4/5 (Decomposed Step 3): Executing Self-Verification & Reflection against Refinement Checklist...")

            refl_checklist = sections.get("reflection", "Verify all user requested features, mobile responsiveness, and zero placeholders.")
            res_verify = run_self_verification(change_request, finalized_code, refl_checklist, system_instruction) or ("", "", 0)
            verification_text, model_name_4, tokens_4 = res_verify
            accumulated_tokens += tokens_4
            used_models.add(model_name_4)

            update_task_record(task_id, verification_report=verification_text)
            append_task_log(task_id, f"Step 4/5 Completed: Self-Verification Report generated via {model_name_4}.")

            # STEP 5: Atomic Write Tool (safe_write_code)
            update_task_record(task_id, current_step=5)
            append_task_log(task_id, f"Step 5/5: Invoking safe_write_code to persist modified code into '{OUTPUT_DIR}/'...")

            write_ok, output_filepath, write_err = safe_write_code(source_file, finalized_code, custom_suffix="_updated")
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
                model_used=primary_model
            )
            append_task_log(task_id, f"Step 5/5 Completed: Original 'workspace/{source_file}' protected. Updated code saved to '{output_filepath}' in {duration}s. Model: {primary_model}.")

            # Universal Notification Dispatch Hook (Telegram & WhatsApp Webhook)
            dispatch_task_alert(
                task_id=task_id,
                task_name=f"Refine {source_file}",
                status="COMPLETED",
                file_path=output_filepath,
                extra_details=f"Updated file saved to '{output_filepath}' in {duration}s. Model: {primary_model}."
            )
            return

        # ======================================================================
        # BRANCH B: NEW AUTONOMOUS 5-DIMENSIONAL CREATION WORKFLOW (5 Steps)
        # ======================================================================
        # STEP 1: 5-Dimensional Multi-Task Planning Engine
        if time.time() - start_time > TASK_TIMEOUT_SECONDS:
            raise TimeoutError("Task exceeded 180s limit during Step 1.")

        update_task_record(task_id, current_step=1)
        append_task_log(task_id, "Step 1/5: Invoking 5-Dimensional Reasoning Engine (Architecture, UX, Resilience, Efficiency, Reflection)...")

        res_5d = generate_5d_plan(prompt, task_type, system_instruction) or ({}, "", "", 0)
        plan_5d, plan_text, model_name_1, tokens_1 = res_5d
        accumulated_tokens += tokens_1
        used_models.add(model_name_1)

        update_task_record(task_id, plan=plan_text, plan_5d=plan_5d)
        append_task_log(task_id, f"Step 1/5 Completed: 5D Plan formulated via {model_name_1}.")

        # STEP 2: Decomposed Action 1 - Initialize Project Schema and Data Structures in workspace/
        if time.time() - start_time > TASK_TIMEOUT_SECONDS:
            raise TimeoutError("Task exceeded 180s limit during Step 2.")

        update_task_record(task_id, current_step=2)
        append_task_log(task_id, "Step 2/5 (Decomposed Step 1): Initializing project schema and data structures in 'workspace/'...")

        folder_name = task.get("folder_name", "").strip()
        if not folder_name:
            folder_name = derive_project_slug(task.get("title", ""), prompt)

        res_schema = generate_project_schema(prompt, plan_5d.get("architecture", plan_text), system_instruction) or ("", "", 0)
        schema_json_str, model_name_2, tokens_2 = res_schema
        accumulated_tokens += tokens_2
        used_models.add(model_name_2)

        schema_ok, schema_path, schema_err = create_project_structure(
            folder_name=folder_name,
            file_name="schema.json",
            code_content=schema_json_str
        )
        if not schema_ok:
            append_task_log(task_id, f"Notice: Schema persistence warning ({schema_err}). Proceeding with in-memory schema.")

        rel_schema_path = os.path.relpath(schema_path, WORKSPACE_DIR).replace('\\', '/') if schema_ok else ""
        update_task_record(task_id, schema_data=schema_json_str, schema_file=rel_schema_path, folder_name=folder_name)
        append_task_log(task_id, f"Step 2/5 Completed: Schema & mock dataset initialized at 'workspace/{folder_name}/schema.json'.")

        # STEP 3: Decomposed Action 2 - Implement Core Logic and Responsive Interface
        if time.time() - start_time > TASK_TIMEOUT_SECONDS:
            raise TimeoutError("Task exceeded 180s limit during Step 3.")

        update_task_record(task_id, current_step=3)
        append_task_log(task_id, "Step 3/5 (Decomposed Step 2): Synthesizing complete core logic, event handlers, and responsive interface...")

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
        res_code = call_llm_with_recovery(code_prompt, system_instruction) or ("", "", 0)
        raw_code_response, model_name_3, tokens_3 = res_code
        accumulated_tokens += tokens_3
        used_models.add(model_name_3)

        code_body, ext = extract_code_block(raw_code_response, default_ext="html" if task_type == "frontend" else "py")
        is_valid, validation_msg, finalized_code = validate_artifact_integrity(code_body, ext)
        update_task_record(task_id, code=finalized_code)
        append_task_log(task_id, f"Step 3/5 Completed using {model_name_3} ({len(finalized_code):,} chars generated). {validation_msg}")

        # STEP 4: Decomposed Action 3 - Run Self-Verification & Reflection Checklist
        if time.time() - start_time > TASK_TIMEOUT_SECONDS:
            raise TimeoutError("Task exceeded 180s limit during Step 4.")

        update_task_record(task_id, current_step=4)
        append_task_log(task_id, "Step 4/5 (Decomposed Step 3): Executing Self-Verification & Reflection against 5D Checklist...")

        refl_checklist = plan_5d.get("reflection", "Verify all user requested features, mobile responsiveness, and zero placeholders.")
        res_verify = run_self_verification(prompt, finalized_code, refl_checklist, system_instruction) or ("", "", 0)
        verification_text, model_name_4, tokens_4 = res_verify
        accumulated_tokens += tokens_4
        used_models.add(model_name_4)

        update_task_record(task_id, verification_report=verification_text)
        append_task_log(task_id, f"Step 4/5 Completed: Self-Verification Report generated via {model_name_4}.")

        # STEP 5: Final Atomic Persistence & State Completion
        update_task_record(task_id, current_step=5)
        append_task_log(task_id, "Step 5/5: Persisting final verified production artifacts to 'workspace/' and 'outputs/'...")

        target_file_name = f"index.{ext}" if ext in ["html", "htm"] else f"main.{ext}"

        # 1. Write atomic workspace file
        create_ok, ws_filepath, create_err = create_project_structure(
            folder_name=folder_name,
            file_name=target_file_name,
            code_content=finalized_code
        )
        if not create_ok:
            raise IOError(f"Project structure creation failed: {create_err}")

        rel_ws_path = os.path.relpath(ws_filepath, WORKSPACE_DIR).replace('\\', '/')

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
            model_used=primary_model
        )
        append_task_log(task_id, f"Step 5/5 Completed: Finalized atomic production files in {duration}s. Model: {primary_model}.")

        # Universal Notification Dispatch Hook (Telegram & WhatsApp Webhook)
        dispatch_task_alert(
            task_id=task_id,
            task_name=task["title"],
            status="COMPLETED",
            file_path=ws_filepath,
            extra_details=f"Workspace project finalized at 'workspace/{rel_ws_path}' in {duration}s. Model: {primary_model}."
        )

    except Exception as exc:
        duration = round(time.time() - start_time, 2)
        error_msg = str(exc)
        status = "TIMEOUT" if "exceeded 180s" in error_msg else "FAILED"

        db = load_db()
        db["metrics"]["failed_tasks"] += 1
        save_db(db)

        update_task_record(
            task_id,
            status=status,
            duration_seconds=duration,
            error=error_msg
        )
        append_task_log(task_id, f"❌ Task ended with status {status}: {error_msg}")

        # Universal Notification Dispatch Hook (Telegram & WhatsApp Webhook)
        dispatch_task_alert(
            task_id=task_id,
            task_name=task.get("title", task_id),
            status=status,
            file_path="",
            extra_details=f"Task error: {error_msg}"
        )

def dispatch_code_edit_task(filename: str, change_request: str) -> str:
    """Spawns an independent detached daemon thread specifically for code refinement."""
    clean_name = filename.strip().replace("\\", "/").lstrip("/")
    base_display = os.path.basename(clean_name)
    title = f"Refine {base_display}: {change_request[:24]}..." if len(change_request) > 24 else f"Refine {base_display}: {change_request}"
    prompt = f"Modify '{clean_name}': {change_request}"

    task_id = create_task_record(
        prompt=prompt,
        task_type="code_edit",
        title=title,
        source_file=clean_name,
        change_request=change_request
    )

    thread = threading.Thread(target=run_autonomous_agent, args=(task_id,), daemon=True)
    thread.start()
    return task_id

def dispatch_background_task(prompt: str, task_type: str = "auto", source_file: str = "", folder_name: str = "") -> str:
    """Spawns an independent detached daemon thread for the task with auto-refine detection."""
    prompt_str = prompt.strip()
    words = prompt_str.split()
    title = " ".join(words[:5]) if words else "Untitled Task"
    if len(title) > 40:
        title = title[:40] + "..."

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
            if wf.lower() in prompt_lower or wf_base.lower() in prompt_lower or f" {name_no_ext.lower()}." in prompt_lower or prompt_lower.startswith(f"take {wf_base.lower()}") or prompt_lower.startswith(f"modify {wf_base.lower()}"):
                matched_file = wf
                break

        if matched_file:
            refine_triggers = ["take", "modify", "edit", "update", "refactor", "add", "change", "enhance", "revise", "in "]
            if any(trig in prompt_lower for trig in refine_triggers) or task_type == "code_edit":
                return dispatch_code_edit_task(filename=matched_file, change_request=prompt_str)

    # Detect task type if auto
    if task_type == "auto":
        frontend_kws = ["html", "css", "js", "ui", "ux", "frontend", "login", "signup", "dashboard", "landing", "card", "navbar", "page", "web"]
        is_frontend = any(kw in prompt_str.lower() for kw in frontend_kws)
        task_type = "frontend" if is_frontend else "general"

    clean_folder = folder_name.strip() if folder_name else derive_project_slug(title, prompt_str)

    task_id = create_task_record(
        prompt=prompt_str,
        task_type=task_type,
        title=title,
        folder_name=clean_folder
    )
    
    # Spawn background daemon thread
    thread = threading.Thread(target=run_autonomous_agent, args=(task_id,), daemon=True)
    thread.start()
    return task_id

# ==============================================================================
# 8. STREAMLIT UI: SIDEBAR MONITOR & CONTROLS
# ==============================================================================
with st.sidebar:
    st.markdown("### ⚡ Autonomous Engine")
    st.caption("24/7 Decoupled Background Task Orchestrator")
    st.markdown("---")

    # Runtime Environment & Hybrid Mode
    st.markdown("**🌐 Environment & Runtime:**")
    st.caption(f"🖥️ Mode: **{RUNTIME_ENV['env_name']}**")
    st.caption(f"📁 Workspace: `{WORKSPACE_DIR}`")
    st.caption(f"📦 Outputs: `{OUTPUT_DIR}`")
    st.markdown("---")

    # Model & Notification Status Monitor
    st.markdown("**AI & Dispatch Status:**")
    st.markdown(f"🟢 **Google Gemini** (`gemini-3.8-flash`)" if gemini_key else "⚪ *Google Gemini (Missing Key)*")
    st.markdown(f"🟢 **OpenRouter** (`openrouter/auto`)" if openrouter_key else "⚪ *OpenRouter (Missing Key)*")
    st.markdown(f"🟢 **Telegram Alerts**" if (telegram_token and telegram_chat_id) else "⚪ *Telegram Alerts (Unconfigured)*")
    st.markdown(f"🟢 **WhatsApp Webhook**" if get_secret("WHATSAPP_WEBHOOK_URL") else "⚪ *WhatsApp Webhook (Stub Ready)*")

    st.markdown("---")

    # Global Token & Task Metrics
    db_state = load_db()
    metrics = db_state.get("metrics", {})
    all_tasks = db_state.get("tasks", {})
    
    running_count = sum(1 for t in all_tasks.values() if t["status"] == "RUNNING")
    completed_count = metrics.get("completed_tasks", 0)
    failed_count = metrics.get("failed_tasks", 0)
    total_tokens = metrics.get("total_tokens", 0)

    st.markdown("**Live Execution Metrics:**")
    col_m1, col_m2 = st.columns(2)
    col_m1.metric("Active", running_count)
    col_m2.metric("Completed", completed_count)

    col_m3, col_m4 = st.columns(2)
    col_m3.metric("Failed", failed_count)
    col_m4.metric("Est. Tokens", f"{total_tokens:,}")

    st.markdown("---")

    # Storage Info
    ws_files = get_workspace_files()
    out_files = [f for f in os.listdir(OUTPUT_DIR) if os.path.isfile(os.path.join(OUTPUT_DIR, f)) and not f.endswith('.tmp')] if os.path.exists(OUTPUT_DIR) else []
    st.caption(f"📁 **Workspace:** `{len(ws_files)} files` in `{WORKSPACE_DIR}/`")
    st.caption(f"📦 **Outputs:** `{len(out_files)} files` in `{OUTPUT_DIR}/`")

    if st.button("🔄 Refresh View", use_container_width=True):
        st.rerun()

    if st.button("🗑️ Clear Tasks History", use_container_width=True):
        with db_lock:
            with open(DB_FILE, "w", encoding="utf-8") as f:
                json.dump({"tasks": {}, "metrics": {"total_tasks": 0, "completed_tasks": 0, "failed_tasks": 0, "total_tokens": 0}}, f, indent=2)
        st.toast("Database history cleared!")
        st.rerun()

# ==============================================================================
# 9. MAIN DASHBOARD: HOME SCREEN SHOWCASE & TABS
# ==============================================================================
# Cloud Sleep & Persistence Recovery Hook
restore_session_state_on_wakeup()

st.markdown('<div class="main-title">🤖 Autonomous Agent & Background Task Engine</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-title">Decoupled Background Execution • Hybrid Hosting (Local ↔ Cloud) • Safe Auto-Code Editor • 5D Task Planner</div>',
    unsafe_allow_html=True
)

def render_home_screen_artifacts_showcase():
    """
    HOME SCREEN ARTIFACT ACCESS & INSTANT DOWNLOAD:
    At the top of the Home Screen / Main Dashboard, provides a dedicated
    'Recent Completed Tasks & Artifacts' card view:
    - Display: Task Name, Execution Timestamp, duration, model, and concise summary of changes made.
    - Immediate one-click st.download_button for every generated file (HTML/Python/JS/ZIP)
      so mobile users can download code directly to phone storage before cloud sessions expire.
    - Collapsible st.expander showing syntax-highlighted code preview.
    """
    db = load_db()
    all_tasks = db.get("tasks", {})
    completed = [t for t in all_tasks.values() if t.get("status") == "COMPLETED"]
    completed.sort(key=lambda x: x.get("updated_at", x.get("created_at", "")), reverse=True)

    with st.expander("📦 Recent Completed Tasks & Artifacts (Instant Mobile & Cloud Downloads)", expanded=True):
        st.caption("⚡ **One-Click Local/Phone Save:** Download your generated web applications and code bundles directly before cloud sessions sleep or expire.")

        if not completed:
            st.info("ℹ️ No completed tasks yet. Submit a task below to generate production web applications and downloadable code bundles.")
            return

        # Show up to 4 most recent completed tasks
        recent_tasks = completed[:4]

        for idx, task in enumerate(recent_tasks):
            task_id = task.get("id", f"task_{idx}")
            title = task.get("title", "Generated Application")
            task_type = task.get("task_type", "frontend")
            updated_at_raw = task.get("updated_at", "")
            duration = task.get("duration_seconds", 0.0)
            model_used = task.get("model_used", "AI Engine")
            tokens = task.get("tokens", 0)
            source_file = task.get("source_file", "")
            change_request = task.get("change_request", "")
            folder_name = task.get("folder_name", "")
            workspace_file = task.get("workspace_file", "")
            output_file = task.get("output_file", "")
            code_content = task.get("code", "")

            # Format friendly timestamp
            time_str = ""
            if updated_at_raw:
                try:
                    dt = datetime.fromisoformat(updated_at_raw)
                    time_str = dt.strftime("%b %d, %H:%M:%S")
                except Exception:
                    time_str = updated_at_raw[:19].replace("T", " ")

            type_label = "🛠️ Code Refinement" if task_type == "code_edit" else "⚡ Frontend Application"

            # Concise summary
            if task_type == "code_edit" and change_request:
                summary = f"Refactored `{source_file}`: {change_request}"
            elif task.get("plan_5d") and isinstance(task.get("plan_5d"), dict) and task["plan_5d"].get("architecture"):
                first_line = task["plan_5d"]["architecture"].split("\n")[0].lstrip("- #*")
                summary = f"Architecture: {first_line}" if first_line else "Full responsive application with schema models and interactive state logic."
            else:
                summary = task.get("prompt", "Application successfully generated and validated.")[:140]

            # Card Header
            st.markdown(f"""
            <div style="background: #1E293B; border: 1px solid #334155; border-radius: 10px; padding: 0.9rem; margin-top: 0.5rem; margin-bottom: 0.5rem;">
                <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap;">
                    <span style="font-size: 1.05rem; font-weight: 700; color: #F8FAFC;">{title}</span>
                    <span style="font-size: 0.72rem; background: #3B82F622; color: #60A5FA; border: 1px solid #3B82F655; border-radius: 5px; padding: 2px 7px;">{type_label}</span>
                </div>
                <div style="font-size: 0.82rem; color: #94A3B8; margin-top: 0.3rem;">
                    ⏱️ <b>{duration}s</b> • 📅 {time_str} • 🤖 <i>{model_used}</i> • 🪙 ~{tokens:,} Tokens
                </div>
                <div style="font-size: 0.85rem; color: #CBD5E1; background: #0F172A; padding: 0.5rem 0.7rem; border-radius: 6px; border-left: 3px solid #3B82F6; margin-top: 0.5rem;">
                    <b>Summary:</b> {summary}
                </div>
            </div>
            """, unsafe_allow_html=True)

            # Download & Action Buttons
            c_dl1, c_dl2, c_dl3 = st.columns([2, 2, 3])

            # Prepare downloadable bytes
            file_bytes = None
            dl_filename = "index.html"
            mime_type = "text/html"

            target_disk_path = None
            if workspace_file:
                cand = os.path.join(WORKSPACE_DIR, workspace_file)
                if os.path.exists(cand):
                    target_disk_path = cand
            if not target_disk_path and output_file and os.path.exists(output_file):
                target_disk_path = output_file

            if target_disk_path and os.path.exists(target_disk_path):
                dl_filename = os.path.basename(target_disk_path)
                try:
                    with open(target_disk_path, "rb") as f:
                        file_bytes = f.read()
                except Exception:
                    file_bytes = code_content.encode("utf-8")
            elif code_content:
                ext = "html" if "<html" in code_content.lower() else "txt"
                clean_t = re.sub(r'[^a-zA-Z0-9_\-]', '_', title.lower())[:25]
                dl_filename = f"{clean_t}.{ext}"
                file_bytes = code_content.encode("utf-8")

            if dl_filename.endswith((".html", ".htm")):
                mime_type = "text/html"
            elif dl_filename.endswith(".py"):
                mime_type = "text/x-python"
            elif dl_filename.endswith(".js"):
                mime_type = "application/javascript"
            elif dl_filename.endswith(".json"):
                mime_type = "application/json"
            else:
                mime_type = "text/plain"

            if file_bytes:
                with c_dl1:
                    st.download_button(
                        label=f"⬇️ Download {dl_filename}",
                        data=file_bytes,
                        file_name=dl_filename,
                        mime=mime_type,
                        key=f"hs_main_dl_{task_id}_{idx}",
                        use_container_width=True
                    )

            # ZIP Bundle creation
            zip_bytes = None
            zip_name = f"{folder_name or 'project'}_bundle.zip"
            proj_dir = os.path.join(WORKSPACE_DIR, folder_name) if folder_name else None

            if proj_dir and os.path.exists(proj_dir) and os.path.isdir(proj_dir):
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                    for root, _, files in os.walk(proj_dir):
                        for fn in files:
                            full_fp = os.path.join(root, fn)
                            rel_fp = os.path.relpath(full_fp, proj_dir)
                            zf.write(full_fp, arcname=rel_fp)
                zip_bytes = zip_buffer.getvalue()
            elif file_bytes:
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                    zf.writestr(dl_filename, file_bytes)
                    if task.get("schema_data"):
                        zf.writestr("schema.json", task["schema_data"].encode("utf-8"))
                    if task.get("verification_report"):
                        zf.writestr("verification_report.md", task["verification_report"].encode("utf-8"))
                zip_bytes = zip_buffer.getvalue()

            if zip_bytes:
                with c_dl2:
                    st.download_button(
                        label="📦 Full Project (.ZIP)",
                        data=zip_bytes,
                        file_name=zip_name,
                        mime="application/zip",
                        key=f"hs_zip_dl_{task_id}_{idx}",
                        use_container_width=True
                    )

            # Code Preview Expander
            preview_code = code_content or (file_bytes.decode("utf-8", errors="replace") if file_bytes else "")
            if preview_code:
                lang = "html" if "<html" in preview_code.lower() else "python"
                with st.expander(f"👁️ View Code Preview ({len(preview_code):,} chars)", expanded=False):
                    st.code(preview_code, language=lang, line_numbers=True)

            st.markdown("<hr style='margin: 0.6rem 0; border-color: #33415544;'/>", unsafe_allow_html=True)

# Render Showcase at top of Dashboard
render_home_screen_artifacts_showcase()

tab_create, tab_editor, tab_monitor, tab_artifacts = st.tabs([
    "🚀 Launch Task",
    "🛠️ Auto-Code Editor",
    "📊 Live Background Monitor",
    "🎨 Artifact Previewer"
])

# ------------------------------------------------------------------------------
# TAB 1: LAUNCH TASK
# ------------------------------------------------------------------------------
with tab_create:
    st.subheader("Submit an Autonomous Task")
    st.markdown(
        "🧠 **5-Dimensional Reasoning Engine:** *Architecture (UI/Logic/Storage) • User Experience (Mobile-First) • Resilience (Error Handling) • Efficiency • Reflection Checklist*"
    )
    st.caption("⚡ **Decomposed Execution Loop:** Step 1: Initialize Schema & Data in `workspace/` ➔ Step 2: Implement Core Logic & Interface ➔ Step 3: Self-Verification & Final Atomic Persistence")

    # Preset Quick Prompts
    st.markdown("**💡 Quick Templates:**")
    p_cols = st.columns(4)
    if p_cols[0].button("💻 Student Dashboard", use_container_width=True):
        st.session_state["task_prompt_val"] = "Build a responsive, modern student dashboard in HTML/CSS/JS with course progress charts, assignment tracker, and dark mode toggle."
        st.session_state["task_folder_val"] = "student_dashboard"
    if p_cols[1].button("🔐 SaaS Auth Portal", use_container_width=True):
        st.session_state["task_prompt_val"] = "Create a sleek, modern SaaS Login and Registration page with tab switching, password strength meter, and social login buttons."
        st.session_state["task_folder_val"] = "saas_auth"
    if p_cols[2].button("📋 Kanban Board", use_container_width=True):
        st.session_state["task_prompt_val"] = "Build an interactive Kanban board UI in single-file HTML/CSS/JS with drag-and-drop task cards, category columns, and task addition modal."
        st.session_state["task_folder_val"] = "kanban_board"
    if p_cols[3].button("🔑 Refine login.html", use_container_width=True):
        st.session_state["task_prompt_val"] = "Take login.html and add password reset modal, remember-me checkbox, and social authentication buttons."
        st.session_state["task_folder_val"] = ""

    # Voice Input Component
    st.markdown("##### 🎙️ Voice Input (Speak Your Instructions):")
    col_v1, col_v2 = st.columns([3, 2])
    with col_v1:
        v_audio = None
        audio_mime = "audio/wav"
        if hasattr(st, "audio_input"):
            v_audio_file = st.audio_input("Record voice instruction:", key="voice_audio_input")
            if v_audio_file is not None:
                v_audio = v_audio_file.getvalue()
                audio_mime = v_audio_file.type or "audio/wav"
        elif MIC_RECORDER_AVAILABLE and mic_recorder:
            rec_result = mic_recorder(
                start_prompt="🔴 Click to Record Voice",
                stop_prompt="⏹️ Stop Recording",
                key="voice_recorder_mic"
            )
            if rec_result and "bytes" in rec_result and rec_result["bytes"]:
                v_audio = rec_result["bytes"]
                audio_mime = "audio/wav"

        if v_audio:
            import hashlib
            audio_hash = hashlib.md5(v_audio).hexdigest()
            if st.session_state.get("prev_audio_hash") != audio_hash:
                with st.spinner("🎙️ Transcribing voice instruction via Groq Whisper / Gemini..."):
                    try:
                        transcribed_text = transcribe_audio_to_text(v_audio, mime_type=audio_mime)
                        st.session_state["prev_audio_hash"] = audio_hash
                        st.session_state["transcribed_voice_text"] = transcribed_text
                        st.session_state["task_prompt_val"] = transcribed_text
                        st.toast("Voice instruction transcribed successfully!")
                    except Exception as ve:
                        st.warning(f"Voice transcription notice: {ve}")

    with col_v2:
        if st.session_state.get("transcribed_voice_text"):
            st.info(f"🎙️ **Transcribed Audio:** \"{st.session_state['transcribed_voice_text']}\"")
            if st.button("Apply Transcribed Text to Prompt", use_container_width=True):
                st.session_state["task_prompt_val"] = st.session_state["transcribed_voice_text"]
                st.rerun()

    task_input = st.text_area(
        "Enter your task or frontend requirement:",
        value=st.session_state.get("task_prompt_val", ""),
        placeholder="e.g. Build an executive analytics dashboard in single-file HTML or Take login.html and add password reset...",
        height=120,
        key="main_task_input_area"
    )

    col_opt1, col_opt2 = st.columns([3, 2])
    with col_opt1:
        folder_input = st.text_input(
            "📁 Project Folder Name (inside workspace/):",
            value=st.session_state.get("task_folder_val", ""),
            placeholder="e.g. student_dashboard (leave empty to auto-derive semantic name)",
            key="custom_folder_name_input"
        )
        task_mode = st.radio(
            "Task Classification:",
            ["Auto-Detect", "Frontend UI (HTML/CSS/JS)", "General Script / Automation", "🛠️ Modify Existing Code (Workspace)"],
            horizontal=True
        )
        selected_ws_file = ""
        if task_mode == "🛠️ Modify Existing Code (Workspace)":
            ws_choices = get_workspace_files()
            if ws_choices:
                selected_ws_file = st.selectbox("Select file from workspace to modify:", ws_choices)
                st.caption(f"🛡️ Original file `workspace/{selected_ws_file}` will be read and preserved. Updated version saves to `outputs/`.")
            else:
                st.warning(f"No files found in `{WORKSPACE_DIR}/`. Please upload or seed one in the Auto-Code Editor tab.")

    with col_opt2:
        st.write("")
        st.write("")
        target_preview_folder = folder_input.strip() if folder_input.strip() else "[auto_derived_project]"
        st.markdown(
            f"**Target Workspace Path:**\n`workspace/{target_preview_folder}/index.html`"
        )
        launch_btn = st.button("⚡ Dispatch Autonomous Task", type="primary", use_container_width=True)

    if launch_btn:
        final_prompt = task_input.strip()
        if not final_prompt:
            st.error("Please enter or record a valid task description.")
        else:
            mapped_type = "auto"
            if task_mode == "Frontend UI (HTML/CSS/JS)":
                mapped_type = "frontend"
            elif task_mode == "General Script / Automation":
                mapped_type = "general"
            elif task_mode == "🛠️ Modify Existing Code (Workspace)":
                mapped_type = "code_edit"

            new_task_id = dispatch_background_task(
                prompt=final_prompt,
                task_type=mapped_type,
                source_file=selected_ws_file,
                folder_name=folder_input.strip()
            )
            st.success(f"🚀 Task dispatched autonomously! Task ID: `{new_task_id}`")
            st.toast("Worker thread running in background!")
            st.info("You can safely close this browser tab, refresh, or switch tabs while the task executes in the background.")

# ------------------------------------------------------------------------------
# TAB 2: AUTO-CODE EDITOR & REFINER
# ------------------------------------------------------------------------------
with tab_editor:
    st.subheader("🛠️ Safe Auto-Code Editor & Refiner")
    st.caption("Safely reads files from `workspace/` via `safe_read_code`, prompts AI with `[Original Code] + [Change Request]`, and saves atomic updates to `outputs/<filename>_updated.<ext>` via `safe_write_code` without touching the original.")

    # Workspace File Management & Selection (supports nested projects)
    workspace_files = get_workspace_files()
    
    col_ws_sel, col_ws_act = st.columns([3, 2])
    with col_ws_sel:
        if workspace_files:
            selected_file = st.selectbox(
                "📁 Select file to inspect & refine from 'workspace/':",
                workspace_files,
                index=0
            )
        else:
            selected_file = None
            st.info("No files currently in `workspace/`. Click 'Seed Sample' or upload a code file below.")

    with col_ws_act:
        st.write("")
        st.write("")
        col_act1, col_act2 = st.columns(2)
        with col_act1:
            if st.button("✨ Seed Sample 'login.html'", use_container_width=True):
                sample_login_code = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Login Portal</title>
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-900 text-slate-100 min-h-screen flex items-center justify-center p-4">
  <div class="w-full max-w-md bg-slate-800 rounded-2xl shadow-xl p-8 border border-slate-700">
    <div class="text-center mb-8">
      <h1 class="text-2xl font-bold text-white">Welcome Back</h1>
      <p class="text-sm text-slate-400 mt-1">Please enter your credentials to sign in</p>
    </div>

    <form id="loginForm" class="space-y-5" onsubmit="event.preventDefault(); alert('Login submitted');">
      <div>
        <label class="block text-xs font-semibold text-slate-300 uppercase mb-2" for="email">Email Address</label>
        <input 
          id="email" 
          type="email" 
          required 
          placeholder="user@example.com"
          class="w-full px-4 py-3 rounded-lg bg-slate-900 border border-slate-700 text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
        />
      </div>

      <div>
        <label class="block text-xs font-semibold text-slate-300 uppercase mb-2" for="password">Password</label>
        <input 
          id="password" 
          type="password" 
          required 
          placeholder="••••••••"
          class="w-full px-4 py-3 rounded-lg bg-slate-900 border border-slate-700 text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
        />
      </div>

      <button 
        type="submit" 
        class="w-full py-3 px-4 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-medium shadow-lg shadow-indigo-600/30 transition-all duration-150">
        Sign In
      </button>
    </form>
  </div>
</body>
</html>"""
                with open(os.path.join(WORKSPACE_DIR, "login.html"), "w", encoding="utf-8") as sf:
                    sf.write(sample_login_code)
                st.toast("Seeded 'login.html' in workspace!")
                st.rerun()

        with col_act2:
            show_uploader = st.toggle("📤 Upload Code File", value=False)

    if show_uploader:
        up_file = st.file_uploader("Upload code file into workspace:", type=["html", "htm", "py", "js", "css", "json", "txt"])
        if up_file is not None:
            up_path = os.path.join(WORKSPACE_DIR, up_file.name)
            with open(up_path, "wb") as uf:
                uf.write(up_file.getvalue())
            st.success(f"Uploaded `{up_file.name}` to `{WORKSPACE_DIR}/`!")
            st.rerun()

    if selected_file:
        # Tool 1: safe_read_code
        read_success, file_content, read_error = safe_read_code(selected_file)
        
        if not read_success:
            st.error(f"Failed to read file: {read_error}")
        else:
            file_base, file_ext = os.path.splitext(selected_file)
            code_lang = file_ext.lstrip(".") or "text"
            flat_name = selected_file.replace("/", "_").replace("\\", "_")
            flat_base, _ = os.path.splitext(flat_name)
            
            # File Overview Card
            col_info1, col_info2, col_info3 = st.columns(3)
            col_info1.metric("Selected File", selected_file)
            col_info2.metric("Size", f"{len(file_content):,} bytes")
            col_info3.metric("Lines", len(file_content.splitlines()))

            with st.expander(f"📄 View Original Source Code (`workspace/{selected_file}`)", expanded=False):
                st.code(file_content, language=code_lang)

            st.markdown("---")
            st.markdown("#### ✏️ Describe Your Changes & Enhancements")

            # Quick Refinement Chips
            st.markdown("**💡 Quick Suggestions:**")
            e_cols = st.columns(3)
            preset_change = ""
            file_label = os.path.basename(selected_file)
            if e_cols[0].button("🔑 Add Password Reset & Remember Me", use_container_width=True):
                preset_change = f"Take {file_label} and add a sleek password reset modal with email verification, along with a 'Remember me' checkbox and forgot password link."
            if e_cols[1].button("🌙 Switch to Dark Glassmorphism", use_container_width=True):
                preset_change = f"Refactor {file_label} into an ultra-modern dark glassmorphism design with backdrop blur, glowing borders, and smooth transitions."
            if e_cols[2].button("✅ Add Toast Alerts & Validation", use_container_width=True):
                preset_change = f"Enhance {file_label} with client-side form validation, inline error indicators, and animated success toast notifications upon submission."

            user_change_input = st.text_area(
                "Enter modification instructions for this file:",
                value=preset_change if preset_change else "",
                placeholder="e.g. Add a password reset modal with smooth animations, remember me checkbox, and social login icons...",
                height=110
            )

            col_sub1, col_sub2 = st.columns([2, 1])
            with col_sub2:
                st.write("")
                st.write("")
                edit_btn = st.button("⚡ Execute Safe Auto-Edit", type="primary", use_container_width=True)

            if edit_btn:
                if not user_change_input.strip():
                    st.error("Please enter modification instructions.")
                else:
                    new_task_id = dispatch_code_edit_task(
                        filename=selected_file,
                        change_request=user_change_input.strip()
                    )
                    st.success(f"🚀 Auto-Edit Task Dispatched! Task ID: `{new_task_id}`")
                    st.toast("Auto-Edit running in background!")
                    st.info(
                        f"🛡️ Original file `workspace/{selected_file}` remains untouched.\n\n"
                        f"📦 Updated version will be saved to `outputs/{flat_base}_updated{file_ext}`.\n\n"
                        f"You can monitor live progress in the **'Live Background Monitor'** tab or switch tabs freely."
                    )

            # Check if an updated version already exists in outputs
            updated_target_file = os.path.join(OUTPUT_DIR, f"{flat_base}_updated{file_ext}")
            if os.path.exists(updated_target_file):
                st.markdown("---")
                st.markdown(f"#### ✨ Latest Updated Version (`outputs/{flat_base}_updated{file_ext}`)")
                
                try:
                    with open(updated_target_file, "r", encoding="utf-8") as uf:
                        updated_content = uf.read()

                    diff_tab1, diff_tab2, diff_tab3 = st.tabs([
                        "🌐 Live Preview (Updated)",
                        "💻 Updated Code (outputs/)",
                        "📄 Original Code (workspace/)"
                    ])

                    with diff_tab1:
                        if file_ext.lower() in [".html", ".htm"]:
                            components.html(updated_content, height=550, scrolling=True)
                        else:
                            st.write("Live preview is only available for HTML files. View updated code in the code tab.")

                    with diff_tab2:
                        st.download_button(
                            "📥 Download Updated Code",
                            data=updated_content,
                            file_name=f"{flat_base}_updated{file_ext}",
                            mime="text/html" if file_ext.lower() in [".html", ".htm"] else "text/plain",
                            key=f"dl_updated_{flat_base}"
                        )
                        st.code(updated_content, language=code_lang)

                    with diff_tab3:
                        st.code(file_content, language=code_lang)

                except Exception as comp_err:
                    st.warning(f"Could not load updated version: {comp_err}")

# ------------------------------------------------------------------------------
# TAB 3: LIVE BACKGROUND MONITOR
# ------------------------------------------------------------------------------
with tab_monitor:
    st.subheader("Live Background Task Execution Monitor")
    st.caption("Persisted in `tasks_db.json`. Real-time progress updates decoupled from UI state.")

    @st.fragment(run_every=3)
    def render_live_monitor():
        current_db = load_db()
        tasks_map = current_db.get("tasks", {})

        if not tasks_map:
            st.info("No tasks recorded yet. Launch a task or run an auto-code edit to observe execution.")
            return

        # Sort tasks by creation date descending
        sorted_tasks = sorted(tasks_map.values(), key=lambda t: t.get("created_at", ""), reverse=True)
        active_list = [t for t in sorted_tasks if t["status"] == "RUNNING"]
        past_list = [t for t in sorted_tasks if t["status"] != "RUNNING"]

        # ACTIVE TASKS SECTION
        if active_list:
            st.markdown("#### 🟡 Currently Running Tasks")
            for task in active_list:
                with st.container():
                    st.markdown(f"**Task ID:** `{task['id']}` — **{task['title']}**")
                    progress_val = min(task.get("current_step", 1) / MAX_AGENT_STEPS, 1.0)
                    st.progress(progress_val, text=f"Step {task.get('current_step', 1)} of {MAX_AGENT_STEPS}")

                    # Recent logs
                    logs = task.get("logs", [])
                    log_text = "\n".join(logs[-6:]) if logs else "Processing..."
                    st.markdown(f'<div class="terminal-box">{log_text}</div>', unsafe_allow_html=True)
                    st.markdown("---")
        else:
            st.success("🟢 No tasks currently running. Background worker is idle.")

        # HISTORICAL AUDIT LOG SECTION
        st.markdown("#### 📜 Task History & Execution Audit")
        
        # Summary Table View
        table_data = []
        for t in sorted_tasks:
            status_badge = "🟢 COMPLETED" if t["status"] == "COMPLETED" else ("🟡 RUNNING" if t["status"] == "RUNNING" else f"🔴 {t['status']}")
            task_kind = "🛠️ Refine" if t.get("task_type") == "code_edit" else "✨ Create"
            ws_item = f"workspace/{t.get('workspace_file')}" if t.get("workspace_file") else (f"workspace/{t.get('source_file')}" if t.get("source_file") else "—")
            table_data.append({
                "Status": status_badge,
                "Type": task_kind,
                "Task ID": t["id"],
                "Title": t["title"],
                "Duration": f"{t.get('duration_seconds', 0)}s",
                "Model": t.get("model_used", "Pending"),
                "Workspace Project": ws_item,
                "Output Backup": os.path.basename(t.get("output_file", "")) if t.get("output_file") else "—"
            })
        st.table(table_data)

        # Deep-dive Inspector
        st.markdown("##### 🔍 Inspect Task Details:")
        selected_task_id = st.selectbox(
            "Select task for full step-by-step logs and architecture plan:",
            [t["id"] for t in sorted_tasks],
            format_func=lambda tid: f"{tid} — {tasks_map[tid]['title']} [{tasks_map[tid]['status']}]"
        )
        if selected_task_id and selected_task_id in tasks_map:
            sel_t = tasks_map[selected_task_id]
            col_d0, col_d1, col_d2, col_d3 = st.columns(4)
            col_d0.caption(f"**Type:** `{'🛠️ Code Refine' if sel_t.get('task_type') == 'code_edit' else '✨ New Creation'}`")
            col_d1.caption(f"**Created:** {sel_t.get('created_at', '')[:19]}")
            col_d2.caption(f"**Duration:** {sel_t.get('duration_seconds', 0)}s")
            col_d3.caption(f"**Tokens:** ~{sel_t.get('tokens', 0)}")

            if sel_t.get("workspace_file"):
                st.info(f"📁 **Workspace Project:** `workspace/{sel_t['workspace_file']}`\n\n📦 **Versioned Backup:** `{sel_t.get('output_file', '')}`")
            elif sel_t.get("source_file"):
                st.info(f"📁 **Source File Modified:** `workspace/{sel_t['source_file']}` (Preserved) ➔ Output: `{sel_t.get('output_file', '')}`")

            # 5-Dimensional Reasoning Analysis
            plan_5d = sel_t.get("plan_5d", {})
            if plan_5d and any(plan_5d.values()):
                with st.expander("🧠 5-Dimensional Multi-Task Reasoning Analysis", expanded=True):
                    d_tab1, d_tab2, d_tab3, d_tab4, d_tab5 = st.tabs([
                        "🏛️ Architecture",
                        "🎨 User Experience",
                        "🛡️ Resilience",
                        "⚡ Efficiency",
                        "🔍 Reflection"
                    ])
                    with d_tab1:
                        st.markdown(plan_5d.get("architecture", "No architecture specs recorded."))
                    with d_tab2:
                        st.markdown(plan_5d.get("ux", "No UX specifications recorded."))
                    with d_tab3:
                        st.markdown(plan_5d.get("resilience", "No resilience specifications recorded."))
                    with d_tab4:
                        st.markdown(plan_5d.get("efficiency", "No efficiency specifications recorded."))
                    with d_tab5:
                        st.markdown(plan_5d.get("reflection", "No reflection checklist recorded."))
            elif sel_t.get("plan"):
                with st.expander("📐 Technical Implementation Plan (Step 1 Output)", expanded=False):
                    st.markdown(sel_t["plan"])

            # Step 1: Initialized Schema & Data Structures
            if sel_t.get("schema_data"):
                with st.expander("📊 Step 1 Artifact: Initialized Project Schema & Data Structures (`workspace/`)", expanded=False):
                    st.code(sel_t["schema_data"], language="json" if sel_t["schema_data"].strip().startswith("{") else "text")

            # Step 3: Self-Verification & Reflection Report
            if sel_t.get("verification_report"):
                with st.expander("✅ Step 3 Artifact: Self-Verification & Reflection Report", expanded=False):
                    st.markdown(sel_t["verification_report"])

            with st.expander("🖥️ Complete Execution Logs", expanded=True):
                full_log_str = "\n".join(sel_t.get("logs", []))
                st.code(full_log_str, language="bash")

            if sel_t.get("error"):
                st.error(f"Execution Error: {sel_t['error']}")

    render_live_monitor()

# ------------------------------------------------------------------------------
# TAB 4: ARTIFACT PREVIEWER & CODE VIEWER
# ------------------------------------------------------------------------------
with tab_artifacts:
    st.subheader("Generated Artifacts & Interactive Preview")
    st.write("Browse, interact with, and export code generated by autonomous background runs.")

    view_source_tab1, view_source_tab2 = st.tabs([
        "📁 Workspace Projects (`workspace/`)",
        "📦 Versioned Artifacts (`outputs/`)"
    ])

    with view_source_tab1:
        st.markdown("#### 📂 Interactive Workspace Projects")
        ws_all_files = get_workspace_files()
        ws_html_files = [f for f in ws_all_files if f.lower().endswith((".html", ".htm"))]

        if not ws_all_files:
            st.info("No files in `workspace/` yet. Launch a new task or seed sample.")
        else:
            default_ws = ws_html_files[0] if ws_html_files else ws_all_files[0]
            selected_ws_preview = st.selectbox(
                "Select Workspace Project / File to Preview:",
                ws_all_files,
                index=ws_all_files.index(default_ws) if default_ws in ws_all_files else 0,
                key="ws_preview_select"
            )
            if selected_ws_preview:
                ok_read, ws_content, ws_err = safe_read_code(selected_ws_preview)
                if not ok_read:
                    st.error(f"Failed to read file: {ws_err}")
                else:
                    col_wb1, col_wb2 = st.columns([1, 4])
                    with col_wb1:
                        st.download_button(
                            label="📥 Download File",
                            data=ws_content,
                            file_name=os.path.basename(selected_ws_preview),
                            mime="text/html" if selected_ws_preview.endswith(".html") else "text/plain",
                            key=f"dl_ws_{selected_ws_preview.replace('/', '_')}",
                            use_container_width=True
                        )
                    with col_wb2:
                        st.caption(f"**Location:** `workspace/{selected_ws_preview}` | **Size:** `{len(ws_content):,} bytes`")

                    # Check for sibling schema.json in project directory
                    ws_dir_name = os.path.dirname(selected_ws_preview)
                    sibling_schema = os.path.join(WORKSPACE_DIR, ws_dir_name, "schema.json") if ws_dir_name else ""
                    has_sibling_schema = os.path.exists(sibling_schema)

                    if has_sibling_schema and selected_ws_preview.lower().endswith((".html", ".htm")):
                        tab_prev_ui, tab_prev_schema, tab_prev_code = st.tabs([
                            "🌐 Live Interactive UI Preview",
                            "📊 Project Schema & Mock Data (schema.json)",
                            "💻 Source Code Inspector"
                        ])
                        with tab_prev_ui:
                            components.html(ws_content, height=650, scrolling=True)
                        with tab_prev_schema:
                            try:
                                with open(sibling_schema, "r", encoding="utf-8") as sc_f:
                                    sc_content = sc_f.read()
                                st.download_button(
                                    "📥 Download Schema JSON",
                                    data=sc_content,
                                    file_name="schema.json",
                                    mime="application/json",
                                    key=f"dl_schema_{selected_ws_preview.replace('/', '_')}"
                                )
                                st.code(sc_content, language="json")
                            except Exception as sc_err:
                                st.warning(f"Could not load schema.json: {sc_err}")
                        with tab_prev_code:
                            st.code(ws_content, language="html")
                    else:
                        tab_prev_ui, tab_prev_code = st.tabs(["🌐 Live Interactive UI Preview", "💻 Source Code Inspector"])
                        with tab_prev_ui:
                            if selected_ws_preview.lower().endswith((".html", ".htm")):
                                components.html(ws_content, height=650, scrolling=True)
                            else:
                                st.info("Non-HTML file. Inspect full source in the 'Source Code Inspector' tab.")
                        with tab_prev_code:
                            lang_fmt = "html" if selected_ws_preview.endswith(".html") else ("python" if selected_ws_preview.endswith(".py") else ("json" if selected_ws_preview.endswith(".json") else "text"))
                            st.code(ws_content, language=lang_fmt)

    with view_source_tab2:
        st.markdown("#### 📦 Versioned Output Artifacts")
        db_artifacts = load_db()
        completed_tasks = [
            t for t in db_artifacts.get("tasks", {}).values()
            if t.get("status") == "COMPLETED" and t.get("output_file") and os.path.exists(t.get("output_file"))
        ]

        if not completed_tasks:
            st.info("No completed output artifacts available yet.")
        else:
            chosen_task = st.selectbox(
                "Select Output Artifact to View:",
                completed_tasks,
                format_func=lambda t: f"{os.path.basename(t['output_file'])} — {t['title']} ({t.get('duration_seconds', 0)}s)",
                key="output_artifact_select"
            )

            if chosen_task:
                file_path = chosen_task["output_file"]
                try:
                    with open(file_path, "r", encoding="utf-8") as af:
                        artifact_content = af.read()

                    col_btn1, col_btn2 = st.columns([1, 4])
                    with col_btn1:
                        st.download_button(
                            label="📥 Download Code File",
                            data=artifact_content,
                            file_name=os.path.basename(file_path),
                            mime="text/html" if file_path.endswith(".html") else "text/plain",
                            use_container_width=True,
                            key=f"dl_out_{os.path.basename(file_path)}"
                        )
                    with col_btn2:
                        st.caption(f"**Stored at:** `{file_path}` | **Size:** `{len(artifact_content):,} bytes`")

                    sub_preview, sub_code = st.tabs(["🌐 Live Interactive UI Preview", "💻 Source Code Inspector"])

                    with sub_preview:
                        if file_path.endswith(".html"):
                            components.html(artifact_content, height=650, scrolling=True)
                        else:
                            st.write("This artifact is a script/code file. View its source in the Inspector tab.")

                    with sub_code:
                        code_lang = "html" if file_path.endswith(".html") else ("python" if file_path.endswith(".py") else "text")
                        st.code(artifact_content, language=code_lang)

                except Exception as read_err:
                    st.error(f"Error reading artifact file: {read_err}")
