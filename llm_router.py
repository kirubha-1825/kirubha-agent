"""
llm_router.py - Tier 1: Multi-Model Free Cloud LLM Loop.
Safely executes generation with:
1. Gemini API (gemini-2.5-flash / gemini-2.0-flash) with 120s timeout.
2. Sequential OpenRouter Free Models loop with safe max_tokens=2048 and timeout=120.
3. Zero crashes on 402 Insufficient Credits or 504 Deadline Expired.
4. Clean handoff signal to Tier 2 (Antigravity) upon exhaustion or if force_antigravity is True.
"""

import os
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, Tuple, Optional, Callable

try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except Exception:
    genai = None
    GENAI_AVAILABLE = False

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except Exception:
    OpenAI = None
    OPENAI_AVAILABLE = False

try:
    import streamlit as st
except Exception:
    st = None


def get_secret(key_name: str, default: str = "") -> str:
    """Safely retrieves credentials from st.secrets or os.getenv."""
    try:
        if st and hasattr(st, "secrets") and key_name in st.secrets:
            val = st.secrets[key_name]
            if val:
                return str(val).strip()
    except Exception:
        pass
    env_val = os.getenv(key_name)
    return env_val.strip() if env_val else default


# Ordered list of top free OpenRouter models as required by Tier 1
OPENROUTER_FREE_MODELS = [
    "google/gemini-2.0-flash-exp:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "deepseek/deepseek-chat-v3-0324:free",
    "qwen/qwen-2.5-coder-32b-instruct:free",
    "openrouter/free"
]

# Shared transient cooldown tracker for Gemini
_gemini_cooldown_until = 0.0


def execute_tier1_cloud_llm(
    prompt: str,
    system_instruction: str = "",
    task_id: str = "",
    force_antigravity: bool = False,
    log_callback: Optional[Callable[[str, str], None]] = None
) -> Dict[str, Any]:
    """
    Tier 1 Smart Cloud LLM Loop:
    - Bypassed immediately if force_antigravity is True.
    - Loops sequentially through Gemini (120s timeout) and Free OpenRouter models (max_tokens=2048).
    - Returns structured result dict with success status, generated text, model used, and token estimate.
    """
    global _gemini_cooldown_until

    def _log(msg: str):
        print(f"⚡ [Tier 1 Cloud LLM]: {msg}")
        if log_callback and task_id:
            try:
                log_callback(task_id, f"⚡ {msg}")
            except Exception:
                pass

    # 1. Guard against force_antigravity
    if force_antigravity:
        _log("Bypassing Tier 1: User requested explicit Google Antigravity execution.")
        return {
            "success": False,
            "bypassed": True,
            "reason": "force_antigravity is True",
            "text": "",
            "model": "None (Bypassed)",
            "tokens": 0,
            "errors": []
        }

    gemini_key = get_secret("GEMINI_API_KEY")
    openrouter_key = get_secret("OPENROUTER_API_KEY")
    errors = []

    # 2. Step 1: Google Gemini API (gemini-2.5-flash / gemini-2.0-flash)
    now = time.time()
    if gemini_key and GENAI_AVAILABLE and now >= _gemini_cooldown_until:
        gemini_candidates = ["gemini-2.5-flash", "gemini-2.0-flash"]
        for cand_model in gemini_candidates:
            _log(f"Attempting Google Gemini '{cand_model}' (timeout=120s)...")
            try:
                genai.configure(api_key=gemini_key)
                model = genai.GenerativeModel(
                    cand_model,
                    system_instruction=system_instruction if system_instruction else None
                )

                def _call_gemini_sdk():
                    return model.generate_content(prompt, request_options={"timeout": 120})

                with ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(_call_gemini_sdk)
                    response = future.result(timeout=125)

                if response and response.text and response.text.strip():
                    text = response.text.strip()
                    tokens = (len(prompt) + len(system_instruction) + len(text)) // 4
                    _log(f"✅ Success via Google Gemini '{cand_model}' ({len(text):,} chars, ~{tokens} tokens).")
                    return {
                        "success": True,
                        "bypassed": False,
                        "text": text,
                        "model": f"Gemini ({cand_model})",
                        "tokens": tokens,
                        "errors": errors
                    }
                else:
                    err_msg = f"Gemini '{cand_model}' returned empty response."
                    _log(f"⚠️ {err_msg}")
                    errors.append(err_msg)
            except Exception as ge:
                err_str = str(ge)
                _log(f"⚠️ Gemini '{cand_model}' failed: {err_str}")
                errors.append(f"Gemini {cand_model}: {err_str}")

                # If quota, deadline, or timeout occurred, engage 90s cooldown
                if any(w in err_str.lower() for w in ["deadline", "timeout", "504", "quota", "resourceexhausted"]):
                    _gemini_cooldown_until = time.time() + 90.0
                    _log(f"Engaging Gemini 90s cooldown; routing directly to OpenRouter free models...")
                    break
    elif gemini_key and now < _gemini_cooldown_until:
        cooldown_left = int(_gemini_cooldown_until - now)
        _log(f"Gemini in transient cooldown ({cooldown_left}s remaining). Proceeding to OpenRouter...")

    # 3. Step 2: OpenRouter Free Models Sequential Loop (max_tokens=2048, timeout=120)
    if openrouter_key and OPENAI_AVAILABLE:
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=openrouter_key,
            default_headers={
                "HTTP-Referer": "https://reakiruba.app",
                "X-Title": "SRI Autonomous Agent"
            }
        )

        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

        for idx, model_name in enumerate(OPENROUTER_FREE_MODELS, 1):
            _log(f"Attempting OpenRouter Free Model [{idx}/{len(OPENROUTER_FREE_MODELS)}]: '{model_name}' (max_tokens=2048)...")
            try:
                def _openrouter_req(m=model_name):
                    return client.chat.completions.create(
                        model=m,
                        messages=messages,
                        temperature=0.4,
                        max_tokens=2048,
                        timeout=50
                    )

                with ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(_openrouter_req)
                    response = future.result(timeout=60)

                msg = response.choices[0].message
                content = msg.content
                if not content and hasattr(msg, "reasoning") and msg.reasoning:
                    content = msg.reasoning

                if content and content.strip():
                    text = content.strip()
                    tokens = (len(prompt) + len(system_instruction) + len(text)) // 4
                    _log(f"✅ Success via OpenRouter '{model_name}' ({len(text):,} chars, ~{tokens} tokens).")
                    return {
                        "success": True,
                        "bypassed": False,
                        "text": text,
                        "model": f"OpenRouter ({model_name})",
                        "tokens": tokens,
                        "errors": errors
                    }
                else:
                    empty_err = f"OpenRouter '{model_name}' returned empty content."
                    _log(f"⚠️ {empty_err}")
                    errors.append(empty_err)
            except Exception as oe:
                err_str = str(oe)
                _log(f"⚠️ OpenRouter '{model_name}' failed: {err_str}")
                errors.append(f"{model_name}: {err_str}")

                if idx < len(OPENROUTER_FREE_MODELS):
                    next_model = OPENROUTER_FREE_MODELS[idx]
                    _log(f"↪️ Switching to next free model: '{next_model}'...")
                    time.sleep(1)

    _log("❌ All Tier 1 Cloud LLM models exhausted. Ready for Tier 2 Antigravity Handoff.")
    return {
        "success": False,
        "bypassed": False,
        "reason": "All Tier 1 models exhausted",
        "text": "",
        "model": "None (Exhausted)",
        "tokens": 0,
        "errors": errors
    }

