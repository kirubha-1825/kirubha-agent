import asyncio
import base64
from datetime import datetime
import html
import io
import json
import re
import streamlit as st
import streamlit.components.v1 as components

SRI_COMPANION_SYSTEM_PROMPT = (
    "You are SRI, a brilliant, warm, and completely open-ended General AI Companion for Kirubha (just like Gemini or ChatGPT). "
    "You have ZERO topic restrictions: freely answer any question across general knowledge, science, world events, technology, "
    "daily life, creative writing, mathematics, or brainstorming — and write clean, complete, production-ready code in any language "
    "(Python, JavaScript/TypeScript, HTML/CSS, React, Flutter/Dart, SQL, etc.) whenever asked. "
    "Never restrict yourself to hackathons or workspace builds unless Kirubha explicitly brings them up.\n"
    "REAL-TIME DATA & LIVE ACCESS (CRITICAL): Your backend includes an active Real-Time Retrieval Engine (Live News RSS, "
    "Technology Updates feeds, Wikipedia, Web Search, and Google Search Grounding). When live retrieved context or current date/time "
    "is supplied, answer current-events, news, tech updates, and live factual queries directly and confidently using that fresh data. "
    "NEVER claim 'I do not have real-time access', 'I cannot browse the internet', or 'my knowledge cutoff is...' — simply use the "
    "live retrieved details naturally.\n"
    "LINK POLICY (STRICT): NEVER output reference links, download links, external links, or bare domain URLs unsolicited or automatically. "
    "ONLY output valid https:// links when Kirubhakaran explicitly asks for a link, URL, website, tool download, book link, or resource location. "
    "Otherwise, converse naturally like a helpful AI companion without appending any URLs, citations, or link lists.\n"
    "NATURAL CONVERSATION FLOW (CRITICAL): Converse fluidly like a sharp, warm human companion — skip stiff AI openers "
    "(never start with 'Certainly!', 'Sure, here is...', or robotic templates), avoid numbered lists during casual voice chat, "
    "and carry conversational context naturally across turns.\n"
    "LANGUAGE RULE (TAMIL & ENGLISH): Match Kirubha's language naturally and fluently. "
    "When Kirubha speaks or writes in Tamil (தமிழ் or Tanglish), understand accurately and reply naturally in conversational Tamil script "
    "(தமிழ், using natural English technical terms where helpful). When Kirubha writes or speaks in English, reply naturally in clear English "
    "(unless Tamil is requested). Also support Hindi, Telugu, Malayalam, and Kannada fluently."
)

_TTS_AUDIO_CACHE: dict[str, str] = {}
_TTS_CACHE_MAX = 96
_EDGE_TTS_CHECKED = False
_EDGE_TTS_MODULE = None
_INSTANT_GREETING_TURN = 0

_VALID_URL_RE = re.compile(
    r"^https?://(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}(?::\d{2,5})?(?:[/?#][^\s<>\"')]*)?$",
    re.IGNORECASE,
)
_BARE_DOMAIN_URL_RE = re.compile(
    r"(?<![@/\w.])(?:[a-z0-9-]+\.)+"
    r"(?:"
    r"(?:com|org|net|edu|gov|info|xyz|cloud)(?:/[^\s<>\"')]*|\b)"
    r"|(?:io|dev|ai|app|co|me|in|ly|be|gl)/[^\s<>\"')]+"
    r")",
    re.IGNORECASE,
)
_BLOCKED_PLACEHOLDER_DOMAINS = (
    "example.com", "example.org", "example.net", "yourdomain", "your-site",
    "yoursite", "localhost", "127.0.0.1", "placeholder", "test.com",
)


def is_valid_external_url(url: str) -> bool:
    """Return True only when url is a syntactically valid, non-placeholder http(s) external link."""
    u = (url or "").strip().rstrip(".,;:!?)\"'")
    if not u or not _VALID_URL_RE.match(u):
        return False
    low = u.lower()
    if any(bad in low for bad in _BLOCKED_PLACEHOLDER_DOMAINS):
        return False
    if "vertexaisearch.cloud.google.com/grounding-api-redirect" in low:
        return False
    return True


def _strip_invalid_or_placeholder_urls(text: str) -> str:
    """Keep valid http(s) links when links are allowed, removing malformed or placeholder URLs."""
    if not text:
        return text

    def _check_raw(match: re.Match) -> str:
        raw = match.group(0)
        trimmed = raw.rstrip(".,;:!?)")
        if is_valid_external_url(trimmed):
            return raw
        return ""

    cleaned = re.sub(r"(?:https?|ftp)://\S+", _check_raw, text, flags=re.IGNORECASE)
    cleaned = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", lambda m: m.group(0) if is_valid_external_url(m.group(2)) else m.group(1), cleaned)
    return re.sub(r"[ \t]{2,}", " ", cleaned).strip()


def user_explicitly_requested_link(user_query: str) -> bool:
    """Return True ONLY when Kirubhakaran explicitly asks for links, URLs, websites, tool downloads, book links, or resource locations."""
    q = (user_query or "").strip().lower()
    if not q:
        return False

    # Explicit opt-out or pure code/UI building prompts must NOT trigger external links unless a link is also requested
    if any(neg in q for neg in ("no link", "no links", "without link", "without links", "don't include link", "do not include link", "லிங்க் வேண்டாம்")):
        return False

    is_building_ui = bool(re.search(r"\b(build|create|design|code|make|develop|generate|style)\s+(a\s+|an\s+|the\s+)?(website|webpage|web\s*app|ui|landing\s*page)\b", q))
    is_concept_only = bool(re.search(r"\b(what is|explain|how does|meaning of)\s+(a\s+|an\s+|the\s+)?(url|link|hyperlink|linked\s+list|website|download)\b", q))

    explicit_phrases = (
        "where to find", "where can i find", "where do i find",
        "where to get", "where can i get", "where do i get",
        "where to buy", "where can i buy", "where do i buy",
        "where to download", "where can i download", "where do i download",
        "where to read", "where can i read", "where do i read",
        "how to download", "tool download", "download tool", "software download", "app download",
        "resource location", "resource url", "share source", "source url", "source link",
        "reference link", "reference links", "download link", "download links", "direct link", "direct download",
        "external link", "external links", "official site", "official website", "official download",
        "download page", "resource link", "resource links", "book link", "pdf link", "github link",
        "repo link", "website link", "buy online", "link please", "links please",
        "give link", "give links", "send link", "send links", "share link", "share links",
        "provide link", "provide links", "include link", "include links", "with links", "any link", "any links",
        "லிங்க்", "லிங்குகள்", "இணைப்பு", "இணையதளம்", "வெப்சைட்", "டவுன்லோட்", "பதிவிறக்கம்",
        "எங்கே கிடைக்கும்", "எங்கு கிடைக்கும்", "எங்கே தேடுவது", "எங்கே வாங்க", "எங்கு வாங்கலாம்", "எங்கு படிப்பது",
    )
    if any(p in q for p in explicit_phrases):
        return True

    if is_building_ui or is_concept_only:
        return False

    if re.search(
        r"\b(give|send|share|provide|get|find|fetch|drop|include|need|want|looking\s+for)\b"
        r"(?:\s+\w+){0,4}\s+\b(link|links|url|urls|website|websites|download\s+page|hyperlink|hyperlinks)\b",
        q,
    ):
        return True

    if re.search(r"\b(link|links|url|urls|download)\s+(?:for|to|of)\b", q):
        return True

    return False


def sanitize_unsolicited_links(reply_text: str, user_query: str = "") -> str:
    """Strip any unsolicited URLs, bare domains, HTML anchors, Markdown links, or reference headings unless explicitly requested."""
    if not reply_text:
        return reply_text
    if user_explicitly_requested_link(user_query):
        return _strip_invalid_or_placeholder_urls(reply_text)
    cleaned = re.sub(r"<a\b[^>]*>(.*?)</a>", r"\1", reply_text, flags=re.IGNORECASE | re.DOTALL)
    cleaned = re.sub(r"<(?:https?|ftp)://[^>]+>|<www\.[^>]+>", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\[([^\]]+)\]\((?:https?://|ftp://|www\.)[^)\s]+\)", r"\1", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(
        r"\[([^\]]+)\]\([a-z0-9.-]+\.(?:com|org|net|io|dev|edu|gov|in|ai|app|co|me|pdf)(?:/[^)\s]*)?\)",
        r"\1",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"(?m)^\s*\[[^\]]+\]:\s*\S+.*$", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"(?:https?|ftp)://\S+|www\.\S+", "", cleaned, flags=re.IGNORECASE)
    cleaned = _BARE_DOMAIN_URL_RE.sub("", cleaned)
    cleaned = re.sub(
        r"(?im)^[\t >*-]*(?:(?:references|sources|resources|downloads)|(?:reference|references|download|downloads|source|sources|useful|official|external)?\s*links?)\s*:\s*$",
        "",
        cleaned,
    )
    cleaned = re.sub(r"\(\s*\)|\[\s*\]", "", cleaned)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r"\s+([.,!?])", r"\1", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _sanitize_html_unsolicited_links(html_str: str, user_query: str = "") -> str:
    """Strip unsolicited anchor tags and raw URLs from pre-built HTML fragments without mangling layout markup."""
    if not html_str or user_explicitly_requested_link(user_query):
        return html_str
    cleaned = re.sub(r"<a\b[^>]*>(.*?)</a>", r"<span>\1</span>", html_str, flags=re.IGNORECASE | re.DOTALL)
    cleaned = re.sub(r"(?:https?|ftp)://[^\s<\"']+|www\.[^\s<\"']+", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip()


def get_open_ended_companion_prompt(
    user_query: str = "",
    mode: str = "chat",
    preferred_lang: str = "ta-IN",
) -> str:
    """Return an unrestricted, Gemini/ChatGPT-style bilingual companion system instruction for SRI."""
    tone = (
        "VOICE MODE: Speak naturally and directly like a real human conversation — crisp, warm, expressive, and fluent "
        "(usually 1 to 3 natural sentences, plain spoken text with zero markdown or bullet lists)."
        if mode == "voice"
        else "CHAT MODE: Converse dynamically and naturally like a helpful AI companion — give direct, accurate answers, clear code, or lively brainstorming without rigid templates."
    )
    link_note = (
        "EXPLICIT RESOURCE LINK REQUEST: Kirubhakaran explicitly asked for a link, download, or resource location — "
        "provide only verified, valid https:// links directly relevant to his request (never placeholder or broken URLs)."
        if user_explicitly_requested_link(user_query)
        else "NO LINKS ALLOWED: Kirubhakaran did NOT ask for links. Do NOT include any URLs, bare domain names, reference links, citations, or download links — converse naturally."
    )
    now_str = datetime.now().strftime("%A, %B %d, %Y %I:%M %p")
    lang_hint = f"\nCurrent live date/time: {now_str}\nActive voice recognition locale: {preferred_lang}."
    extra = f"\nLatest user message: {user_query.strip()}" if user_query and user_query.strip() else ""
    return f"{SRI_COMPANION_SYSTEM_PROMPT}\n{tone}\n{link_note}{lang_hint}{extra}"


def get_tamil_fallback_message(err: Exception | str | None = None) -> str:
    """Friendly Tamil fallback message for AI quota limits or API errors."""
    msg = str(err or "").lower()
    if any(k in msg for k in ("429", "quota", "resource_exhausted", "exhausted", "rate limit", "too many requests")):
        return (
            "மன்னிக்கவும் கிருபா! இப்போது AI பயன்பாட்டு வரம்பு (Quota Limit) நிரம்பிவிட்டது "
            "அல்லது அதிக கோரிக்கைகள் உள்ளன. சில வினாடிகள் கழித்து மீண்டும் முயற்சிக்கவும்!"
        )
    if any(k in msg for k in ("timeout", "deadline", "504", "503", "502", "connection", "network", "unreachable")):
        return (
            "மன்னிக்கவும் கிருபா! AI சேவையகத்துடன் இணைப்பதில் தற்காலிக தாமதம் ஏற்பட்டுள்ளது. "
            "கொஞ்சம் கழித்து மீண்டும் பேசுங்கள்!"
        )
    if any(k in msg for k in ("401", "403", "api_key", "api key", "unauthorized", "permission", "no api keys")):
        return (
            "மன்னிக்கவும் கிருபா! AI சேவை இணைப்பில் (API Key / Service) சிறிய சிக்கல் உள்ளது. "
            "அமைப்புகளைச் சரிபார்த்து மீண்டும் முயற்சிக்கவும்."
        )
    return (
        "மன்னிக்கவும் கிருபா! தற்போது AI பதில் உருவாக்குவதில் சிறிய தொழில்நுட்பச் சிக்கல் ஏற்பட்டுள்ளது. "
        "சில வினாடிகளில் மீண்டும் முயற்சிக்கவும்!"
    )


def try_instant_voice_reply(user_query: str, preferred_lang: str = "ta-IN") -> str | None:
    """Ultra-fast local fast-path for pure 1-word greetings with natural non-repetitive variation (<1ms)."""
    global _INSTANT_GREETING_TURN
    q = re.sub(r"[!?.🙏😊✨]+$", "", (user_query or "").strip().lower()).strip()
    if not q or len(q.split()) > 2:
        return None
    is_tamil = bool(re.search(r"[\u0B80-\u0BFF]", q)) or preferred_lang == "ta-IN"
    tamil_pings = {"வணக்கம்", "ஹலோ", "ஹாய்"}
    english_pings = {"hi", "hello", "hey", "hi sri", "hello sri", "hey sri"}
    if q in tamil_pings:
        _INSTANT_GREETING_TURN += 1
        variants = (
            "வணக்கம் கிருபா! சொல்லுங்க, என்ன விஷயம்?",
            "ஹாய் கிருபா! நான் கேட்கிறேன், பேசலாம் வாங்க.",
            "வணக்கம் கிருபா! இன்னைக்கு என்ன பிளான்?",
        )
        return variants[_INSTANT_GREETING_TURN % len(variants)]
    if q in english_pings:
        _INSTANT_GREETING_TURN += 1
        if is_tamil and "sri" in q:
            variants = (
                "சொல்லுங்க கிருபா, நான் இங்கே தான் இருக்கேன்!",
                "ஹாய் கிருபா! பேசலாம், என்ன கேட்கணும்?",
            )
            return variants[_INSTANT_GREETING_TURN % len(variants)]
        variants = (
            "Hey Kirubha! What's on your mind?",
            "Hi Kirubha, I'm listening — go ahead!",
            "Hey there! Ready whenever you are.",
        )
        return variants[_INSTANT_GREETING_TURN % len(variants)]
    return None


def _clean_text_for_speech(text: str) -> str:
    if not text:
        return ""
    replacements = {
        "I'm": "I am",
        "i'm": "I am",
        "what's": "what is",
        "What's": "What is",
        "let's": "let us",
        "Let's": "Let us",
        "don't": "do not",
        "Don't": "Do not",
        "can't": "cannot",
        "Can't": "Cannot",
        "won't": "will not",
        "Won't": "Will not",
        "it's": "it is",
        "It's": "It is",
        "that's": "that is",
        "That's": "That is",
        "you're": "you are",
        "You're": "You are",
        "we're": "we are",
        "We're": "We are",
        "they're": "they are",
        "They're": "They are",
        "I've": "I have",
        "I'll": "I will",
        "I'd": "I would",
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    text = re.sub(r"^SRI:\s*", "", text.strip(), flags=re.IGNORECASE)
    text = re.sub(r"[\*_`#~\[\](){}<>|\\]", " ", text)
    text = re.sub(r"['\"]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _detect_neural_voice(text: str, preferred_lang: str = "ta-IN") -> str:
    if re.search(r"[\u0B80-\u0BFF]", text):
        return "ta-IN-PallaviNeural"
    if re.search(r"[\u0900-\u097F]", text):
        return "hi-IN-SwaraNeural"
    if re.search(r"[\u0C00-\u0C7F]", text):
        return "te-IN-ShrutiNeural"
    if re.search(r"[\u0D00-\u0D7F]", text):
        return "ml-IN-SobhanaNeural"
    if re.search(r"[\u0C80-\u0CFF]", text):
        return "kn-IN-SapnaNeural"
    if preferred_lang == "ta-IN" and re.search(r"[a-zA-Z]", text) is None:
        return "ta-IN-PallaviNeural"
    return "en-IN-NeerjaNeural"


def _generate_edge_tts_base64(text: str, preferred_lang: str = "ta-IN") -> str:
    global _EDGE_TTS_CHECKED, _EDGE_TTS_MODULE
    cleaned = _clean_text_for_speech(text)
    if not cleaned:
        return ""
    voice = _detect_neural_voice(cleaned, preferred_lang=preferred_lang)
    cache_key = f"{voice}:{cleaned}"
    if cache_key in _TTS_AUDIO_CACHE:
        return _TTS_AUDIO_CACHE[cache_key]

    try:
        if not _EDGE_TTS_CHECKED:
            import importlib
            _EDGE_TTS_CHECKED = True
            try:
                _EDGE_TTS_MODULE = importlib.import_module("edge_tts")
            except Exception:
                _EDGE_TTS_MODULE = None
        edge_tts = _EDGE_TTS_MODULE
        if edge_tts is None:
            return ""

        async def _synthesize():
            communicate = edge_tts.Communicate(cleaned, voice, rate="+10%", pitch="+0Hz")
            audio_stream = io.BytesIO()
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_stream.write(chunk["data"])
            return base64.b64encode(audio_stream.getvalue()).decode("utf-8")

        result_b64 = ""
        try:
            asyncio.get_running_loop()
            has_running_loop = True
        except RuntimeError:
            has_running_loop = False

        if has_running_loop:
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                result_b64 = pool.submit(
                    lambda: asyncio.run(asyncio.wait_for(_synthesize(), timeout=0.95))
                ).result(timeout=1.15)
        else:
            result_b64 = asyncio.run(asyncio.wait_for(_synthesize(), timeout=0.95))

        if result_b64:
            if len(_TTS_AUDIO_CACHE) >= _TTS_CACHE_MAX:
                _TTS_AUDIO_CACHE.pop(next(iter(_TTS_AUDIO_CACHE)))
            _TTS_AUDIO_CACHE[cache_key] = result_b64
        return result_b64
    except Exception:
        return ""


def _build_companion_insights_html(
    reply_text: str,
    last_user_query: str = "",
    is_research: bool = False,
) -> str:
    if not reply_text:
        return (
            "<div style='font-family:Inter,-apple-system,BlinkMacSystemFont,sans-serif;color:#9CA3AF;padding:24px;text-align:center;font-size:13px;line-height:1.6;'>"
            "<div style='color:#F59E0B;font-weight:700;font-size:12px;letter-spacing:0.6px;text-transform:uppercase;margin-bottom:8px;'>✦ SRI Research &amp; Insights</div>"
            "Speak through the 3D Golden Orb or ask in chat about any research topic, news, analysis, or comparison — results render right here."
            "</div>"
        )
    safe_reply = sanitize_unsolicited_links(reply_text, last_user_query)
    escaped_reply = html.escape(safe_reply)
    escaped_query = html.escape(last_user_query.strip()) if last_user_query and last_user_query.strip() else ""
    lines = [html.escape(ln.strip()) for ln in safe_reply.split("\n") if ln.strip()]
    badge_title = "✦ SRI Research Findings" if is_research else "✦ SRI Research &amp; Insights"
    query_block = (
        f"<div style='font-size:12px;color:#FBBF24;font-weight:600;margin-bottom:8px;padding-bottom:6px;border-bottom:1px solid rgba(245,158,11,0.2);'>Query: {escaped_query}</div>"
        if escaped_query
        else ""
    )
    cards_html = f"""
    <div style="font-family:'Inter',-apple-system,BlinkMacSystemFont,sans-serif;color:#F4F4F5;padding:4px;">
        <div style="background:linear-gradient(135deg,rgba(245,158,11,0.12),rgba(16,185,129,0.06));border:1px solid rgba(245,158,11,0.38);border-radius:14px;padding:14px;margin-bottom:12px;">
            <div style="display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:8px;">
                <span style="font-size:11px;color:#F59E0B;font-weight:700;text-transform:uppercase;letter-spacing:0.6px;">{badge_title}</span>
                <span style="font-size:10.5px;color:#10B981;font-weight:600;">● Live Brief</span>
            </div>
            {query_block}
            <div style="font-size:13.5px;line-height:1.62;color:#FFFFFF;white-space:pre-wrap;">{escaped_reply}</div>
        </div>
    """
    if len(lines) > 1:
        cards_html += "<div style='display:flex;flex-direction:column;gap:8px;margin-bottom:8px;'>"
        for idx, item in enumerate(lines[:6], 1):
            cards_html += f"""
            <div style="background:#0E1117;border:1px solid #222630;border-radius:10px;padding:10px 12px;font-size:12.5px;color:#E5E7EB;line-height:1.55;">
                <strong style="color:#F59E0B;">Finding {idx}:</strong> {item}
            </div>
            """
        cards_html += "</div>"
    cards_html += "</div>"
    return cards_html


def _normalize_chat_messages(chat_history: list) -> list:
    normalized = []
    for msg in chat_history[-12:]:
        if not isinstance(msg, dict):
            continue
        if "user" in msg or "agent" in msg:
            u_text = str(msg.get("user", "")).strip()
            a_text = str(msg.get("agent", "")).strip()
            if u_text:
                normalized.append({"role": "user", "content": u_text})
            if a_text:
                normalized.append({"role": "assistant", "content": a_text})
        else:
            role_raw = str(msg.get("role", "assistant")).lower()
            role = "user" if role_raw == "user" else "assistant"
            content = str(msg.get("content", "")).strip()
            if content:
                normalized.append({"role": role, "content": content})
    return normalized[-10:]


def _infer_auto_navigation(
    last_user_query: str,
    reply_text: str,
    workspace_file: str,
    preview_html: str,
    explicit_page: str = "",
    explicit_tab: str = "",
) -> tuple[str, str]:
    """Infer target mobile page ('hub' | 'research' | 'project' | '') and tab ('preview' | 'code' | '')."""
    if explicit_page in ("hub", "research", "project"):
        resolved_tab = explicit_tab if explicit_tab in ("preview", "code") else ("preview" if explicit_page == "project" else "")
        return explicit_page, resolved_tab

    u_low = (last_user_query or "").lower()
    r_low = (reply_text or "").lower()

    code_kw = ("source code", "show code", "open code", "code tab", "code view", "கோடு காட்டு", "கோட் காட்டு", "சோர்ஸ் கோடு")
    preview_kw = (
        "preview", "open preview", "show preview", "latest work", "open project", "show project",
        "build ui", "create ui", "ui design", "login.html", "dashboard ui", "generate ui",
        "ப்ரிவியூ", "பிரிவியூ", "ui உருவாக்கு", "டிசைன் காட்டு", "ப்ராஜெக்ட்", "preview screen",
    )
    coding_exclusions = (
        "write code", "write python", "python code", "javascript code", "fix bug", "debug",
        "syntax error", "event listener", "event loop", "event handler", "dom event",
        "binary search", "linear search", "search tree", "find index", "find element", "regex",
    )
    research_kw = (
        "research", "open research", "research page", "insights", "insight", "investigate", "deep dive",
        "live news", "world news", "latest news", "breaking news", "tech news", "technology news",
        "tech updates", "technology updates", "ai news", "ai updates", "latest updates", "recent updates",
        "live updates", "headlines", "current affairs", "what's new", "whats new", "news",
        "weather today", "weather in", "analyze", "analysis", "compare", "case study",
        "literature review", "fact check", "market trends", "trends in", "study about", "study on",
        "information about", "info about", "details about", "explain about", "tell me about",
        "summarize", "summary of", "search web", "search about", "search for", "look up",
        "where to find", "where to buy",
        "ரிசர்ச்", "ஆராய்ச்சி", "செய்தி", "செய்திகள்", "நியூஸ்", "டெக் நியூஸ்", "புதிய தொழில்நுட்பம்",
        "வானிலை", "தேடு", "தகவல்", "விளக்கு", "பற்றி சொல்லு", "பற்றி கூறு", "அனலைஸ்", "ஒப்பீடு",
    )
    hub_kw = ("go home", "back to hub", "open hub", "main screen", "home page", "ஹப்", "முகப்பு", "திரும்பு", "ஹோம்")

    if any(k in u_low for k in hub_kw):
        return "hub", ""

    has_explicit_research = any(k in u_low for k in ("research", "insights", "tech news", "tech updates", "ai news", "ரிசர்ச்", "ஆராய்ச்சி", "செய்தி", "நியூஸ்"))
    is_coding_only = any(ex in u_low for ex in coding_exclusions) and not has_explicit_research

    if not is_coding_only and (
        "workspace/research.html" in workspace_file.lower()
        or any(k in u_low for k in research_kw)
        or ("preview screen" in r_low and "research" in u_low)
    ):
        if any(k in u_low for k in code_kw) and "research.html" not in workspace_file.lower():
            return "project", "code"
        return "research", ""

    if any(k in u_low for k in code_kw) or any(k in r_low for k in ("source code tab", "code tab", "opening code")):
        return "project", "code"

    is_full_html_preview = bool(re.search(r"<!doctype|<html", preview_html or "", re.IGNORECASE))
    if any(k in u_low for k in preview_kw) or bool(re.search(r"\b(open|show|build|create)\s+(a\s+)?ui\b", u_low)) or (
        is_full_html_preview and any(w in u_low for w in ("open preview", "show preview", "build ui", "create ui", "ui உருவாக்கு", "பிரிவியூ"))
    ):
        return "project", "preview"

    return "", ""


def render_sri_zero_failure_ui(
    agent_status="SRI (Ready)",
    active_tasks=0,
    completed_tasks=0,
    failed_tasks=0,
    workspace_file="workspace/login.html",
    generated_code="",
    generated_preview_html="",
    chat_history=None,
    voice_reply_text="",
    history_log=None,
    **kwargs,
):
    if chat_history is None:
        chat_history = []

    st.markdown(
        """
        <style>
        html, body, [data-testid="stAppViewContainer"], [data-testid="stApp"], .main {
            background-color: #060709 !important;
            margin: 0 !important;
            padding: 0 !important;
            overflow: hidden !important;
        }
        [data-testid="stToolbar"], [data-testid="stDecoration"], #MainMenu, footer,
        [data-testid="stToastContainer"], [data-testid="stToast"] {
            display: none !important;
        }
        [data-testid="stHeader"] {
            background: transparent !important;
            height: 0 !important;
            min-height: 0 !important;
            border: none !important;
            overflow: visible !important;
            pointer-events: none !important;
            z-index: 999998 !important;
        }
        [data-testid="stHeader"] button,
        [data-testid="stExpandSidebarButton"],
        [data-testid="stSidebarCollapsedControl"],
        [data-testid="collapsedControl"] {
            pointer-events: auto !important;
            opacity: 0.01 !important;
        }
        .block-container {
            padding: 0 !important;
            margin: 0 !important;
            max-width: 100vw !important;
        }
        [data-testid="stSidebar"] {
            background-color: #090B0E !important;
            border-right: 1px solid rgba(245, 158, 11, 0.35) !important;
            border-left: 1px solid rgba(245, 158, 11, 0.35) !important;
            z-index: 999999 !important;
            box-shadow: 0 0 36px rgba(0, 0, 0, 0.85) !important;
        }
        [data-testid="stSidebar"][data-sri-drawer-open="true"] {
            display: flex !important;
            visibility: visible !important;
            transform: translateX(0px) !important;
            margin-left: 0px !important;
            width: min(360px, 88vw) !important;
            min-width: 300px !important;
            max-width: 92vw !important;
            opacity: 1 !important;
            pointer-events: auto !important;
        }
        iframe {
            display: block !important;
            border: none !important;
            width: 100vw !important;
            height: 100dvh !important;
            margin: 0 !important;
            padding: 0 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    try:
        normalized_messages = _normalize_chat_messages(chat_history)
        prev_user_msg = ""
        for m in normalized_messages:
            if m.get("role") == "user":
                prev_user_msg = m.get("content", "")
            elif m.get("role") == "assistant" and m.get("content"):
                m["content"] = sanitize_unsolicited_links(m["content"], prev_user_msg)
    except Exception:
        normalized_messages = []

    last_user_query = ""
    for msg in reversed(normalized_messages):
        if msg.get("role") == "user" and msg.get("content"):
            last_user_query = msg["content"]
            break

    latest_assistant_reply = voice_reply_text or ""
    if not latest_assistant_reply:
        for msg in reversed(normalized_messages):
            if msg.get("role") == "assistant" and msg.get("content"):
                latest_assistant_reply = msg["content"]
                break

    latest_assistant_reply = sanitize_unsolicited_links(latest_assistant_reply, last_user_query)

    last_spoken_key = "_sri_last_spoken_turn"
    should_speak = False
    audio_b64 = ""
    cleaned_reply = _clean_text_for_speech(latest_assistant_reply)
    voice_lang = str(kwargs.get("voice_lang") or "ta-IN").strip() or "ta-IN"
    raw_turn_id = str(kwargs.get("voice_turn_id") or "").strip()
    turn_id = raw_turn_id or (f"{len(normalized_messages)}:{hash(cleaned_reply)}" if cleaned_reply else "")

    if cleaned_reply and turn_id and st.session_state.get(last_spoken_key) != turn_id:
        st.session_state[last_spoken_key] = turn_id
        should_speak = True
        if not kwargs.get("skip_tts"):
            try:
                audio_b64 = _generate_edge_tts_base64(cleaned_reply, preferred_lang=voice_lang)
            except Exception:
                audio_b64 = ""

    explicit_page = str(kwargs.get("active_page") or kwargs.get("target_page") or "").strip().lower()
    explicit_tab = str(kwargs.get("active_tab") or kwargs.get("target_tab") or "").strip().lower()
    raw_research_html = str(kwargs.get("research_html") or "").strip()

    preview_only_html = (
        generated_preview_html
        or "<div style='color:#9CA3AF;padding:24px;text-align:center;font-family:Inter,sans-serif;font-size:13px;line-height:1.5;'>Live Preview Ready — Ask SRI anything or build a module to inspect it here.</div>"
    )

    try:
        target_page, target_tab = _infer_auto_navigation(
            last_user_query=last_user_query,
            reply_text=latest_assistant_reply,
            workspace_file=workspace_file,
            preview_html=preview_only_html,
            explicit_page=explicit_page,
            explicit_tab=explicit_tab,
        )
    except Exception:
        target_page, target_tab = "", ""

    if raw_research_html:
        insights_html = _sanitize_html_unsolicited_links(raw_research_html, last_user_query)
    else:
        insights_html = _build_companion_insights_html(
            latest_assistant_reply,
            last_user_query=last_user_query,
            is_research=(target_page == "research"),
        )

    try:
        state_payload = json.dumps(
            {
                "agentStatus": agent_status,
                "activeTasks": active_tasks,
                "completed": completed_tasks,
                "failed": failed_tasks,
                "workspaceFile": workspace_file,
                "code": generated_code
                or "<!-- SRI AI Workspace Ready -->\n<div class='card'>Waiting for prompt...</div>",
                "insightsHtml": insights_html,
                "previewHtml": preview_only_html,
                "messages": normalized_messages,
                "lastUserQuery": last_user_query,
                "targetPage": target_page,
                "targetTab": target_tab,
                "shouldSpeak": should_speak,
                "spokenText": cleaned_reply,
                "turnId": turn_id,
                "audioBase64": audio_b64,
                "historyLog": history_log or st.session_state.get("history_log", []),
                "allTasksCompleted": bool((kwargs.get("whatsapp_alert_status") or {}).get("all_completed", False)),
                "whatsappAlertSummary": kwargs.get("whatsapp_alert_status") or {},
                "workspaceFiles": kwargs.get("workspace_files_data") or [],
                "trackerTasks": kwargs.get("tracker_tasks_data") or [],
            },
            default=str,
        ).replace("</", "<\\/")
    except Exception as payload_err:
        fallback_msg = get_tamil_fallback_message(payload_err)
        state_payload = json.dumps(
            {
                "agentStatus": agent_status,
                "activeTasks": active_tasks,
                "completed": completed_tasks,
                "failed": failed_tasks,
                "workspaceFile": workspace_file,
                "code": "",
                "insightsHtml": _build_companion_insights_html(fallback_msg),
                "previewHtml": preview_only_html,
                "messages": normalized_messages,
                "lastUserQuery": last_user_query,
                "targetPage": "",
                "targetTab": "",
                "shouldSpeak": False,
                "spokenText": fallback_msg,
                "turnId": turn_id,
                "audioBase64": "",
                "historyLog": [],
            },
            default=str,
        ).replace("</", "<\\/")

    html_template = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Playfair+Display:wght@600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
    * {
        box-sizing: border-box;
        margin: 0;
        padding: 0;
        -webkit-tap-highlight-color: transparent !important;
        outline: none !important;
    }

    html, body {
        background: #0b0b0b;
        color: #F4F4F5;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        width: 100%;
        height: 100%;
        overflow: hidden;
    }

    /* Stable Mobile App Shell — Zero absolute overlap or viewport jumps */
    .app-shell {
        width: 100%;
        height: 100dvh;
        display: flex;
        flex-direction: column;
        overflow: hidden;
        background: #0b0b0b;
    }

    /* 1. Fixed Top Header */
    .app-header {
        flex-shrink: 0;
        background: #0b0b0b;
        width: 100%;
    }

    .header-inner {
        max-width: 520px;
        margin: 0 auto;
        padding: 12px 18px 4px 18px;
        display: flex;
        flex-direction: column;
        gap: 10px;
    }

    .topbar {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 8px;
    }

    .brand {
        font-family: 'Playfair Display', Georgia, serif;
        font-size: 22px;
        font-weight: 700;
        color: #F5E6C8;
        letter-spacing: -0.02em;
        white-space: nowrap;
    }
    .brand span { color: #F59E0B; }

    .right-controls {
        display: flex;
        align-items: center;
        gap: 8px;
    }

    .status-pill {
        background: #0B1612;
        border: 1px solid rgba(16, 185, 129, 0.32);
        border-radius: 999px;
        padding: 5px 11px;
        font-size: 11px;
        color: #34D399;
        display: flex;
        align-items: center;
        gap: 6px;
        font-weight: 600;
        white-space: nowrap;
    }

    .dot-green {
        width: 6px;
        height: 6px;
        border-radius: 50%;
        background: #10B981;
    }

    .gear-btn {
        width: 34px;
        height: 34px;
        background: #13151B;
        border: 1px solid #262A35;
        color: #9CA3AF;
        border-radius: 50%;
        font-size: 14px;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
        transition: border-color 0.15s ease, color 0.15s ease;
    }
    .gear-btn:hover {
        border-color: rgba(245, 158, 11, 0.55);
        color: #F5E6C8;
    }

    .welcome-row {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 10px;
    }
    .welcome-stack {
        display: flex;
        flex-direction: column;
        gap: 1px;
    }
    .welcome-sub {
        color: #D97706;
        font-size: 11px;
        font-weight: 500;
        line-height: 1.25;
    }
    .welcome-name {
        color: #FFFFFF;
        font-size: 20px;
        font-weight: 700;
        letter-spacing: -0.02em;
        line-height: 1.15;
    }
    .latest-work-btn {
        background: #130E07;
        border: 1px solid rgba(217, 119, 6, 0.45);
        color: #F59E0B;
        border-radius: 999px;
        padding: 6px 13px;
        font-size: 11.5px;
        font-weight: 600;
        cursor: pointer;
        white-space: nowrap;
        display: inline-flex;
        align-items: center;
        gap: 5px;
    }
    .latest-work-btn:hover {
        border-color: rgba(245, 158, 11, 0.78);
        color: #FBBF24;
    }

    /* Secondary 6-Tab Top Menu Bar: Hidden on pristine Home screen, shown when off-Home */
    .top-menu-bar {
        display: none;
        align-items: center;
        gap: 10px;
        overflow-x: auto;
        scrollbar-width: none;
        padding: 4px 0 4px 0;
        border-bottom: 1px solid #1B1D24;
    }
    body.off-home .top-menu-bar {
        display: flex;
    }
    .top-menu-bar::-webkit-scrollbar { display: none; }
    .top-menu-tab {
        flex: 0 0 auto;
        background: transparent;
        border: none;
        border-bottom: 2px solid transparent;
        color: #9CA3AF;
        font-size: 11.5px;
        font-weight: 600;
        padding: 4px 4px 6px 4px;
        cursor: pointer;
        white-space: nowrap;
        transition: color 0.15s ease, border-color 0.15s ease;
    }
    .top-menu-tab:hover { color: #F4F4F5; }
    .top-menu-tab.active {
        color: #F59E0B;
        border-bottom-color: #F59E0B;
    }

    /* 2. Main Scrollable Viewport Stage */
    .main-stage {
        flex: 1;
        min-height: 0;
        width: 100%;
        max-width: 520px;
        margin: 0 auto;
        padding: 10px 0;
        display: flex;
        flex-direction: column;
        overflow: hidden;
        position: relative;
    }

    /* Smooth 6-Screen Mobile Horizontal Slide Track (Workbench, Research, Preview, Tracker, Call & Msg, Portability) */
    .pages-track {
        flex: 1;
        min-height: 0;
        width: 600%;
        display: flex;
        flex-direction: row;
        transform: translate3d(0%, 0, 0);
        transition: transform 0.25s cubic-bezier(0.22, 1, 0.36, 1);
        will-change: transform;
    }
    .pages-track.no-anim {
        transition: none !important;
    }

    .page-slide {
        width: 16.666667%;
        height: 100%;
        min-height: 0;
        flex-shrink: 0;
        padding: 0 14px;
        display: flex;
        flex-direction: column;
        overflow: hidden;
    }

    /* Workspace File Swipe Carousel inside Project View */
    .file-carousel {
        flex-shrink: 0;
        display: flex;
        align-items: center;
        gap: 6px;
        background: #060709;
        border: 1px solid #1E2028;
        border-radius: 10px;
        padding: 4px 6px;
    }
    .file-step-btn {
        background: transparent;
        border: none;
        color: #9CA3AF;
        font-size: 14px;
        font-weight: 700;
        cursor: pointer;
        padding: 2px 6px;
        border-radius: 6px;
    }
    .file-step-btn:hover { color: #F59E0B; }
    .file-pills-scroll {
        flex: 1;
        display: flex;
        align-items: center;
        gap: 6px;
        overflow-x: auto;
        scrollbar-width: none;
    }
    .file-pills-scroll::-webkit-scrollbar { display: none; }
    .file-pill {
        flex: 0 0 auto;
        background: #111318;
        border: 1px solid #222630;
        color: #9CA3AF;
        border-radius: 7px;
        padding: 3px 9px;
        font-family: 'JetBrains Mono', monospace;
        font-size: 10.5px;
        cursor: pointer;
        white-space: nowrap;
    }
    .file-pill.active {
        background: rgba(245, 158, 11, 0.14);
        border-color: rgba(245, 158, 11, 0.55);
        color: #FBBF24;
        font-weight: 600;
    }

    /* PAGE 1: COMPANION HUB — Stacked mobile column */
    .hub-view {
        flex: 1;
        min-height: 0;
        display: flex;
        flex-direction: column;
        gap: 8px;
        overflow: hidden;
    }

    .hub-view.is-idle .orb-wrap {
        flex: 1;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
    }

    .orb-wrap {
        flex-shrink: 0;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 2px 0;
    }

    canvas#sriOrb {
        width: 100%;
        height: clamp(170px, 29dvh, 240px);
        display: block;
        cursor: pointer;
    }
    .hub-view:not(.is-idle) canvas#sriOrb {
        height: clamp(128px, 21dvh, 172px);
    }

    .orb-hint {
        font-size: 12px;
        color: #9CA3AF;
        margin-top: 6px;
        text-align: center;
        padding: 0 10px;
        line-height: 1.4;
        max-width: 400px;
    }
    .orb-hint.listening { color: #F59E0B; font-weight: 600; }
    .orb-hint.thinking { color: #60A5FA; font-weight: 600; }
    .orb-hint.speaking { color: #10B981; font-weight: 600; }

    /* Scrollable Mobile Chat Thread between Orb and Input Dock */
    .hub-chat-feed {
        flex: 1;
        min-height: 64px;
        overflow-y: auto;
        overscroll-behavior: contain;
        background: #0F1013;
        border: 1px solid #1E2028;
        border-radius: 14px;
        padding: 10px;
        display: flex;
        flex-direction: column;
        gap: 8px;
    }
    .hub-chat-feed.empty {
        display: none;
    }
    .hub-chat-empty {
        margin: auto;
        text-align: center;
        font-size: 12px;
        color: #71717A;
        line-height: 1.5;
        padding: 8px;
    }
    .chat-bubble {
        max-width: 88%;
        padding: 8px 11px;
        border-radius: 12px;
        font-size: 12.5px;
        line-height: 1.48;
        white-space: pre-wrap;
        word-break: break-word;
    }
    .chat-bubble.user {
        align-self: flex-end;
        background: rgba(245, 158, 11, 0.14);
        border: 1px solid rgba(245, 158, 11, 0.35);
        color: #F4F4F5;
    }
    .chat-bubble.assistant {
        align-self: flex-start;
        background: #14161B;
        border: 1px solid #222630;
        color: #E4E4E7;
    }
    .chat-sender {
        display: block;
        font-size: 10px;
        font-weight: 700;
        margin-bottom: 2px;
        letter-spacing: 0.3px;
    }
    .chat-bubble.user .chat-sender { color: #F59E0B; }
    .chat-bubble.assistant .chat-sender { color: #34D399; }

    .hub-bottom-dock {
        flex-shrink: 0;
        width: 100%;
        display: flex;
        flex-direction: column;
        gap: 8px;
        padding-top: 2px;
    }

    .pills-row {
        display: flex;
        flex-direction: row;
        flex-wrap: nowrap;
        gap: 7px;
        width: 100%;
        overflow-x: auto;
        padding: 2px 0;
        scrollbar-width: none;
    }
    .pills-row::-webkit-scrollbar { display: none; }

    .pill-btn {
        flex: 0 0 auto;
        background: #121316;
        border: 1px solid #262830;
        color: #D4D4D8;
        border-radius: 999px;
        padding: 6px 11px;
        font-size: 11px;
        font-weight: 500;
        cursor: pointer;
        white-space: nowrap;
    }
    .pill-btn:first-child {
        background: #130E07;
        border-color: rgba(245, 158, 11, 0.72);
        color: #F5E6C8;
    }

    .chat-bar {
        width: 100%;
        background: #111215;
        border: 1px solid #26272C;
        border-radius: 999px;
        display: flex;
        align-items: center;
        padding: 5px 7px 5px 16px;
        gap: 6px;
        min-height: 46px;
        max-height: 76px;
        overflow: hidden;
        transition: border-color 0.18s ease, box-shadow 0.18s ease, background 0.18s ease;
    }
    .chat-bar:focus-within {
        border-color: rgba(245, 158, 11, 0.7);
    }
    .chat-bar.recording {
        border-color: #F59E0B;
        background: #121215;
        box-shadow: 0 0 0 2px rgba(245, 158, 11, 0.2);
    }
    .chat-bar.processing {
        border-color: #10B981;
        background: #0B1211;
        box-shadow: 0 0 0 2px rgba(16, 185, 129, 0.2);
    }
    .chat-bar textarea {
        flex: 1;
        min-width: 0;
        width: 100%;
        box-sizing: border-box;
        font-family: inherit;
        background: transparent;
        border: none;
        color: #FFFFFF;
        font-size: 13.5px;
        line-height: 19px;
        min-height: 24px;
        max-height: 58px;
        height: 24px;
        padding: 2px 0;
        resize: none;
        overflow-y: auto;
        scrollbar-width: thin;
        scrollbar-color: rgba(245, 158, 11, 0.35) transparent;
        user-select: text;
    }
    .chat-bar textarea::-webkit-scrollbar { width: 4px; }
    .chat-bar textarea::-webkit-scrollbar-thumb {
        background: rgba(245, 158, 11, 0.35);
        border-radius: 99px;
    }
    .chat-bar textarea::placeholder { color: #71717A; }

    /* Interactive Audio Wave + Processing Loader inside Chat Bar */
    .chat-wave-loader {
        display: none;
        align-items: center;
        gap: 6px;
        padding: 3px 8px;
        border-radius: 999px;
        background: rgba(245, 158, 11, 0.1);
        border: 1px solid rgba(245, 158, 11, 0.3);
        flex-shrink: 0;
    }
    .chat-wave-loader.active { display: flex; }
    .chat-wave-loader.processing {
        background: rgba(16, 185, 129, 0.12);
        border-color: rgba(16, 185, 129, 0.35);
    }

    .wave-dots {
        display: flex;
        align-items: center;
        gap: 2.5px;
        height: 16px;
    }
    .chat-wave-loader.processing .wave-dots { display: none; }
    .wave-dots span {
        width: 2.5px;
        height: 8px;
        background: #F59E0B;
        border-radius: 99px;
        animation: waveBounce 0.75s infinite ease-in-out;
    }
    .wave-dots span:nth-child(1) { animation-delay: 0.00s; height: 7px; }
    .wave-dots span:nth-child(2) { animation-delay: 0.10s; height: 13px; }
    .wave-dots span:nth-child(3) { animation-delay: 0.20s; height: 16px; }
    .wave-dots span:nth-child(4) { animation-delay: 0.30s; height: 10px; }
    .wave-dots span:nth-child(5) { animation-delay: 0.40s; height: 15px; }
    .wave-dots span:nth-child(6) { animation-delay: 0.50s; height: 11px; }
    .wave-dots span:nth-child(7) { animation-delay: 0.60s; height: 8px; }
    @keyframes waveBounce {
        0%, 100% { transform: scaleY(0.42); opacity: 0.55; }
        50% { transform: scaleY(1.25); opacity: 1; }
    }

    .chat-mic-spinner {
        display: none;
        width: 13px;
        height: 13px;
        border-radius: 50%;
        border: 2px solid rgba(16, 185, 129, 0.25);
        border-top-color: #10B981;
        animation: spinMic 0.7s linear infinite;
    }
    .chat-wave-loader.processing .chat-mic-spinner { display: block; }
    @keyframes spinMic {
        to { transform: rotate(360deg); }
    }

    .chat-mic-status {
        font-size: 10.5px;
        font-weight: 600;
        color: #FBBF24;
        white-space: nowrap;
        letter-spacing: 0.2px;
    }
    .chat-wave-loader.processing .chat-mic-status { color: #34D399; }

    .mic-inline {
        background: transparent;
        border: 1px solid transparent;
        color: #9CA3AF;
        font-size: 16px;
        cursor: pointer;
        width: 34px;
        height: 34px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
        transition: all 0.15s ease;
    }
    .mic-inline.active {
        color: #F59E0B;
        background: rgba(245, 158, 11, 0.18);
        border-color: rgba(245, 158, 11, 0.7);
        animation: micRingPulse 1.3s infinite ease-out;
    }
    @keyframes micRingPulse {
        0% { box-shadow: 0 0 0 0 rgba(245, 158, 11, 0.45); }
        70% { box-shadow: 0 0 0 7px rgba(245, 158, 11, 0); }
        100% { box-shadow: 0 0 0 0 rgba(245, 158, 11, 0); }
    }

    .send-circle {
        width: 34px;
        height: 34px;
        border-radius: 50%;
        background: #F59E0B;
        color: #060709;
        border: none;
        font-weight: 700;
        font-size: 14px;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
    }

    /* PAGES 2 & 3: INNER CARDS — Clean flex column inside slide track */
    .inner-page {
        display: flex;
        flex: 1;
        min-height: 0;
        background: #0A0C10;
        border: 1px solid rgba(245, 158, 11, 0.28);
        border-radius: 16px;
        padding: 12px;
        flex-direction: column;
        gap: 8px;
        overflow: hidden;
    }

    .page-header-title {
        flex-shrink: 0;
        font-size: 13px;
        font-weight: 700;
        color: #F59E0B;
        display: flex;
        align-items: center;
        justify-content: space-between;
    }

    .seg-tabs {
        flex-shrink: 0;
        display: flex;
        background: #060709;
        border: 1px solid #1E222B;
        border-radius: 999px;
        padding: 3px;
    }
    .seg-tab {
        flex: 1;
        text-align: center;
        padding: 6px 10px;
        border-radius: 999px;
        font-size: 12px;
        color: #9CA3AF;
        cursor: pointer;
    }
    .seg-tab.active {
        background: #141821;
        border: 1px solid #F59E0B;
        color: #FFFFFF;
        font-weight: 600;
    }

    .file-label {
        flex-shrink: 0;
        font-size: 11px;
        color: #9CA3AF;
        font-family: 'JetBrains Mono', monospace;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }

    .workspace-pane {
        flex: 1;
        min-height: 0;
        background: #060709;
        border: 1px solid #181B22;
        border-radius: 12px;
        overflow-y: auto;
        overscroll-behavior: contain;
        padding: 12px;
        font-family: 'JetBrains Mono', monospace;
        font-size: 12px;
        color: #E5E7EB;
        user-select: text;
    }
    #paneResearch {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    .research-chat-thread {
        flex-shrink: 0;
        max-height: 44%;
        overflow-y: auto;
        overscroll-behavior: contain;
        background: #0b0b0b;
        border: 1px solid #1E2028;
        border-radius: 12px;
        padding: 10px;
        display: flex;
        flex-direction: column;
        gap: 8px;
    }
    .research-chat-thread.empty {
        display: none;
    }

    /* Smooth Horizontal Swipe Track inside Project View (Preview <-> Code) */
    .project-tabs-viewport {
        flex: 1;
        min-height: 0;
        width: 100%;
        position: relative;
        overflow: hidden;
        border-radius: 12px;
        border: 1px solid #181B22;
        background: #060709;
    }
    .project-tabs-track {
        width: 200%;
        height: 100%;
        display: flex;
        flex-direction: row;
        transform: translate3d(0%, 0, 0);
        transition: transform 0.28s cubic-bezier(0.22, 1, 0.36, 1);
        will-change: transform;
    }
    .project-tabs-track.no-anim {
        transition: none !important;
    }
    .project-tab-slide {
        width: 50%;
        height: 100%;
        min-height: 0;
        flex-shrink: 0;
        display: flex;
        flex-direction: column;
        overflow: hidden;
    }
    .swipe-edge-handle {
        position: absolute;
        top: 0;
        bottom: 0;
        width: 16px;
        z-index: 20;
        cursor: grab;
        touch-action: pan-y;
    }
    .swipe-edge-handle.left { left: 0; }
    .swipe-edge-handle.right { right: 0; }
    .project-swipe-bar {
        flex-shrink: 0;
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 8px;
        font-size: 11px;
        color: #9CA3AF;
        padding: 2px 4px;
        user-select: none;
    }
    .project-swipe-btn {
        background: transparent;
        border: none;
        color: #D4D4D8;
        font-size: 11px;
        font-weight: 500;
        cursor: pointer;
        padding: 2px 4px;
    }
    .project-swipe-btn:hover { color: #F59E0B; }

    .preview-pane-wrap {
        flex: 1;
        min-height: 0;
        background: #060709;
        display: flex;
        flex-direction: column;
        overflow: hidden;
    }

    .preview-frame {
        flex: 1;
        width: 100%;
        height: 100%;
        min-height: 0;
        border: none;
        border-radius: 8px;
        background: #060709;
    }

    /* Dedicated Mini-Orb Voice Footer inside inner pages */
    .inner-voice-footer {
        flex-shrink: 0;
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 6px 10px;
        background: #0E1117;
        border: 1px solid #1E222B;
        border-radius: 999px;
    }

    .mini-orb-btn {
        width: 38px;
        height: 38px;
        border-radius: 50%;
        background: radial-gradient(circle at 35% 35%, #FDE68A, #F59E0B 60%, #92400E);
        border: 1.5px solid #FEF3C7;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 16px;
        flex-shrink: 0;
        transition: transform 0.15s ease;
    }
    .mini-orb-btn.listening {
        transform: scale(1.06);
        box-shadow: 0 0 16px rgba(245, 158, 11, 0.75);
    }
    .mini-orb-btn.speaking {
        background: radial-gradient(circle at 35% 35%, #A7F3D0, #10B981 60%, #065F46);
        border-color: #D1FAE5;
        box-shadow: 0 0 16px rgba(16, 185, 129, 0.75);
    }

    .mini-orb-status {
        flex: 1;
        min-width: 0;
        font-size: 11.5px;
        color: #D4D4D8;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }

    /* Persistent Bottom Round Animated Voice Call Indicator (Walkie-Talkie Mode) */
    .voice-call-dock {
        display: none;
        flex-shrink: 0;
        width: 100%;
        padding: 4px 12px 6px 12px;
        justify-content: center;
        align-items: center;
        background: transparent;
        z-index: 40;
    }
    .voice-call-dock.active {
        display: flex;
    }
    .voice-call-pill {
        display: flex;
        align-items: center;
        gap: 10px;
        background: rgba(14, 17, 23, 0.96);
        border: 1px solid rgba(245, 158, 11, 0.55);
        border-radius: 999px;
        padding: 5px 10px 5px 6px;
        box-shadow: 0 6px 24px rgba(0, 0, 0, 0.55), 0 0 18px rgba(245, 158, 11, 0.18);
        max-width: min(440px, calc(100vw - 24px));
        cursor: pointer;
    }
    .voice-call-dock.speaking .voice-call-pill {
        border-color: rgba(16, 185, 129, 0.65);
        box-shadow: 0 6px 24px rgba(0, 0, 0, 0.55), 0 0 18px rgba(16, 185, 129, 0.22);
    }
    .voice-call-dock.thinking .voice-call-pill {
        border-color: rgba(96, 165, 250, 0.65);
        box-shadow: 0 6px 24px rgba(0, 0, 0, 0.55), 0 0 18px rgba(96, 165, 250, 0.2);
    }
    .voice-call-round-orb {
        position: relative;
        width: 38px;
        height: 38px;
        border-radius: 50%;
        flex-shrink: 0;
        display: flex;
        align-items: center;
        justify-content: center;
        background: radial-gradient(circle at 35% 35%, #FDE68A, #F59E0B 62%, #92400E);
        border: 1.5px solid #FEF3C7;
        color: #060709;
        font-size: 15px;
        font-weight: 700;
        animation: callOrbBreathe 1.4s infinite ease-in-out;
    }
    .voice-call-round-orb::before,
    .voice-call-round-orb::after {
        content: "";
        position: absolute;
        inset: -4px;
        border-radius: 50%;
        border: 1.5px solid rgba(245, 158, 11, 0.65);
        animation: callSonarRing 1.6s infinite ease-out;
        pointer-events: none;
    }
    .voice-call-round-orb::after {
        animation-delay: 0.75s;
    }
    .voice-call-dock.speaking .voice-call-round-orb {
        background: radial-gradient(circle at 35% 35%, #A7F3D0, #10B981 62%, #065F46);
        border-color: #D1FAE5;
    }
    .voice-call-dock.speaking .voice-call-round-orb::before,
    .voice-call-dock.speaking .voice-call-round-orb::after {
        border-color: rgba(16, 185, 129, 0.7);
    }
    .voice-call-dock.thinking .voice-call-round-orb {
        background: radial-gradient(circle at 35% 35%, #BFDBFE, #3B82F6 62%, #1E3A8A);
        border-color: #DBEAFE;
    }
    .voice-call-dock.thinking .voice-call-round-orb::before,
    .voice-call-dock.thinking .voice-call-round-orb::after {
        border-color: rgba(96, 165, 250, 0.7);
    }
    @keyframes callOrbBreathe {
        0%, 100% { transform: scale(0.95); }
        50% { transform: scale(1.06); }
    }
    @keyframes callSonarRing {
        0% { transform: scale(0.92); opacity: 0.85; }
        100% { transform: scale(1.55); opacity: 0; }
    }
    .voice-call-meta {
        display: flex;
        flex-direction: column;
        min-width: 0;
        flex: 1;
    }
    .voice-call-state {
        font-size: 11px;
        font-weight: 700;
        color: #FBBF24;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        max-width: 220px;
    }
    .voice-call-dock.speaking .voice-call-state { color: #34D399; }
    .voice-call-dock.thinking .voice-call-state { color: #93C5FD; }
    .voice-call-sub {
        font-size: 10px;
        color: #9CA3AF;
        white-space: nowrap;
    }
    .voice-call-end {
        width: 24px;
        height: 24px;
        border-radius: 50%;
        background: rgba(239, 68, 68, 0.16);
        border: 1px solid rgba(239, 68, 68, 0.45);
        color: #FCA5A5;
        font-size: 11px;
        font-weight: 700;
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
    }

    /* 3. Bottom Navigation Bar */
    .mob-nav {
        flex-shrink: 0;
        width: 100%;
        background: #0b0b0b;
        padding: 4px 14px max(12px, env(safe-area-inset-bottom)) 14px;
    }

    .mob-nav-inner {
        max-width: 520px;
        margin: 0 auto;
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 10px;
    }

    .mob-pill {
        padding: 8px 18px;
        border-radius: 999px;
        font-size: 12px;
        font-weight: 600;
        cursor: pointer;
        border: 1px solid #26272E;
        background: #141518;
        color: #D4D4D8;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        gap: 6px;
        white-space: nowrap;
        transition: all 0.15s ease;
    }
    .mob-pill.active {
        background: #F59E0B;
        color: #0b0b0b;
        border-color: #F59E0B;
        font-weight: 700;
    }

    /* Settings Modal */
    .settings-modal-backdrop {
        display: none;
        position: fixed;
        inset: 0;
        background: rgba(0, 0, 0, 0.78);
        backdrop-filter: blur(6px);
        z-index: 9999;
        align-items: center;
        justify-content: center;
        padding: 16px;
    }
    .settings-modal-backdrop.open { display: flex; }
    .settings-modal {
        width: 100%;
        max-width: 460px;
        height: min(82dvh, 640px);
        background: #0A0C10;
        border: 1px solid rgba(245, 158, 11, 0.45);
        border-radius: 18px;
        padding: 16px;
        display: flex;
        flex-direction: column;
        gap: 10px;
    }
    .settings-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding-bottom: 10px;
        border-bottom: 1px solid #1E222B;
    }
    .settings-title { font-size: 15px; font-weight: 700; color: #F59E0B; }
    .close-settings-btn {
        background: #141821;
        border: 1px solid #242832;
        color: #E5E7EB;
        border-radius: 50%;
        width: 30px;
        height: 30px;
        cursor: pointer;
        font-size: 14px;
    }
</style>
</head>
<body>
<div class="app-shell" id="appShell">
    <header class="app-header">
        <div class="header-inner">
            <div class="topbar">
                <div class="brand" onclick="setMobilePage('hub')" style="cursor:pointer;">SRI AI<span>.</span></div>
                <div class="right-controls">
                    <div class="status-pill"><span class="dot-green"></span> 24/7 Active</div>
                    <button type="button" class="gear-btn" onclick="openBackendSettings()" title="SRI Control Drawer">⚙️</button>
                </div>
            </div>
            <div class="welcome-row">
                <div class="welcome-stack">
                    <span class="welcome-sub">Welcome</span>
                    <div class="welcome-name">Kirubha</div>
                </div>
                <button type="button" class="latest-work-btn" onclick="setMobilePage('project')">Latest Work ➔</button>
            </div>
            <!-- Swipeable 6-Tab Strip (shown off-Home cleanly; Home dashboard stays pure) -->
            <nav class="top-menu-bar" id="topMenuBar" aria-label="Workspace Tabs">
                <button type="button" class="top-menu-tab active" id="topTabHub" onclick="setMobilePage('hub')">Workbench</button>
                <button type="button" class="top-menu-tab" id="topTabResearch" onclick="setMobilePage('research')">Research</button>
                <button type="button" class="top-menu-tab" id="topTabProject" onclick="setMobilePage('project')">Preview</button>
                <button type="button" class="top-menu-tab" id="topTabTracker" onclick="setMobilePage('tracker')">Tracker</button>
                <button type="button" class="top-menu-tab" id="topTabComms" onclick="setMobilePage('comms')">Call &amp; Msg</button>
                <button type="button" class="top-menu-tab" id="topTabPortability" onclick="setMobilePage('portability')">Portability</button>
            </nav>
        </div>
    </header>

    <main class="main-stage" id="mainStage">
        <div class="pages-track" id="pagesTrack">
            <div class="page-slide">
                <!-- PAGE 1: PRISTINE SOLO COMPANION HUB (No inline chat clutter) -->
                <section class="hub-view is-idle" id="hubViewSection" aria-label="Companion Hub">
                    <div class="orb-wrap">
                        <canvas id="sriOrb" onclick="handleOrbGestureTap(event)"></canvas>
                        <div class="orb-hint" id="orbHint">Tap the golden sphere to talk with SRI in Tamil or English</div>
                    </div>

                    <div class="hub-bottom-dock">
                        <div class="pills-row">
                            <button type="button" class="pill-btn" onclick="sendChatPreset('Build a responsive Student Learning Hub dashboard UI in workspace with course streaks, assignment tracker, and interactive dark mode widgets.')">Student Dashboard</button>
                            <button type="button" class="pill-btn" onclick="sendChatPreset('Build a sleek SaaS Auth login and signup UI portal in workspace with tab switching and validation.')">SaaS Auth</button>
                            <button type="button" class="pill-btn" onclick="sendChatPreset('Build an interactive Kanban Board UI in workspace with task columns and priority filtering.')">Kanban Board</button>
                            <button type="button" class="pill-btn" onclick="sendChatPreset('Refine logic in workspace/login.html by adding password recovery, inline validation, and accessible form feedback.')">Refine logic</button>
                        </div>
                        <div class="chat-bar" id="chatBar">
                            <textarea id="promptInput" rows="1" placeholder="Message SRI..." oninput="autoResizePromptInput()" onkeydown="handlePromptKeydown(event)"></textarea>
                            <div class="chat-wave-loader" id="chatWaveLoader" aria-live="polite" style="margin-bottom:2px;">
                                <div class="wave-dots" id="waveDots"><span></span><span></span><span></span><span></span><span></span><span></span><span></span></div>
                                <div class="chat-mic-spinner" id="chatMicSpinner"></div>
                                <span class="chat-mic-status" id="chatMicStatus">Listening</span>
                            </div>
                            <button type="button" class="mic-inline" id="inlineMicBtn" onclick="toggleChatDictation()" title="Dictate Tamil/Regional/English into chat box only">🎙️</button>
                            <button type="button" class="send-circle" onclick="submitPrompt()" title="Send Message">➤</button>
                        </div>
                    </div>
                </section>
            </div>

            <div class="page-slide">
                <!-- PAGE 2: DEDICATED RESEARCH & VOICE OUTPUT -->
                <section class="inner-page" id="pageResearch" aria-label="Research and Voice Output">
                    <div class="page-header-title">
                        <span>✦ SRI Research &amp; Voice Output</span>
                        <button type="button" class="project-swipe-btn" onclick="setMobilePage('hub')" style="color:#9CA3AF;">← Hub</button>
                    </div>
                    <div class="research-chat-thread empty" id="hubChatFeed" aria-live="polite"></div>
                    <div class="workspace-pane" id="paneResearch"></div>
                    <div class="inner-voice-footer">
                        <button type="button" class="mini-orb-btn" id="miniOrbResearch" onclick="handleOrbGestureTap(event)" title="Single-Tap: Start / Back Home · Double-Tap: End Call">🎙️</button>
                        <div class="mini-orb-status" id="statusOrbResearch">Tap orb to talk with SRI</div>
                    </div>
                </section>
            </div>

            <div class="page-slide">
                <!-- PAGE 3: SWIPEABLE PREVIEW, CODE & FILES -->
                <section class="inner-page" id="pageProject" aria-label="Preview and Code">
                    <div class="seg-tabs" id="projectSegTabs">
                        <div class="seg-tab active" id="tabPreview" onclick="switchTab('preview')">Preview</div>
                        <div class="seg-tab" id="tabCode" onclick="switchTab('code')">Code</div>
                    </div>
                    <div class="file-carousel" id="projectFileStrip">
                        <button type="button" class="file-step-btn" onclick="stepWorkspaceFile(-1)" title="Previous file">‹</button>
                        <div class="file-pills-scroll" id="projectFilePills"></div>
                        <button type="button" class="file-step-btn" onclick="stepWorkspaceFile(1)" title="Next file">›</button>
                    </div>
                    <div class="file-label" id="fileLabel">workspace/login.html</div>
                    <div class="project-tabs-viewport" id="projectTabsViewport">
                        <div class="swipe-edge-handle left" id="previewSwipeLeftEdge" aria-hidden="true"></div>
                        <div class="swipe-edge-handle right" id="previewSwipeRightEdge" aria-hidden="true"></div>
                        <div class="project-tabs-track" id="projectTabsTrack">
                            <div class="project-tab-slide">
                                <div class="preview-pane-wrap" id="panePreview"></div>
                            </div>
                            <div class="project-tab-slide">
                                <pre class="workspace-pane" id="paneCode" style="border:none;border-radius:0;white-space:pre-wrap;"></pre>
                            </div>
                        </div>
                    </div>
                    <div class="project-swipe-bar" id="projectSwipeBar">
                        <button type="button" class="project-swipe-btn" id="swipePrevAction" onclick="handleProjectSwipeButton('prev')">‹ Slide to Research</button>
                        <span style="font-size:10px;color:#71717A;">Swipe ⇄ Tabs · Preview · Code</span>
                        <button type="button" class="project-swipe-btn" id="swipeNextAction" onclick="handleProjectSwipeButton('next')">Slide to Code ›</button>
                    </div>
                    <div class="inner-voice-footer">
                        <button type="button" class="mini-orb-btn" id="miniOrbProject" onclick="handleOrbGestureTap(event)" title="Single-Tap: Start / Back Home · Double-Tap: End Call">🎙️</button>
                        <div class="mini-orb-status" id="statusOrbProject">Tap orb to discuss this preview</div>
                    </div>
                </section>
            </div>

            <div class="page-slide">
                <!-- PAGE 4: TRACKER -->
                <section class="inner-page" id="pageTracker" aria-label="Task Tracker">
                    <div class="page-header-title">
                        <span>📊 Live Task &amp; Progress Tracker</span>
                        <button type="button" class="project-swipe-btn" onclick="openControlSection('Tracker')">Open Controls ⚙️</button>
                    </div>
                    <div class="workspace-pane" id="paneTracker" style="font-family:'Inter',sans-serif;"></div>
                </section>
            </div>

            <div class="page-slide">
                <!-- PAGE 5: CALL & MSG -->
                <section class="inner-page" id="pageComms" aria-label="Call and Message Bridge">
                    <div class="page-header-title">
                        <span>📲 Twilio Voice &amp; WhatsApp Bridge</span>
                        <button type="button" class="project-swipe-btn" onclick="openControlSection('Call & Msg')">Configure ⚙️</button>
                    </div>
                    <div class="workspace-pane" id="paneComms" style="font-family:'Inter',sans-serif;"></div>
                </section>
            </div>

            <div class="page-slide">
                <!-- PAGE 6: PORTABILITY -->
                <section class="inner-page" id="pagePortability" aria-label="Portability and Sandbox Config">
                    <div class="page-header-title">
                        <span>📦 Portability &amp; Runtime Config</span>
                        <button type="button" class="project-swipe-btn" onclick="openControlSection('Portability')">Workspace ⚙️</button>
                    </div>
                    <div class="workspace-pane" id="panePortability" style="font-family:'Inter',sans-serif;"></div>
                </section>
            </div>
        </div>
    </main>

    <!-- Persistent Round Animated Voice Call Indicator (Continuous Walkie-Talkie Mode) -->
    <div class="voice-call-dock" id="voiceCallDock" aria-live="polite">
        <button type="button" class="voice-call-pill" id="voiceCallPillBtn" onclick="handleOrbGestureTap(event)" title="Single-Tap: Back / Home · Double-Tap: End Voice Call">
            <span class="voice-call-round-orb" id="voiceCallRoundOrb">🎙️</span>
            <span class="voice-call-meta">
                <span class="voice-call-state" id="voiceCallState">Live Call · Listening...</span>
                <span class="voice-call-sub" id="voiceCallSub">Walkie-Talkie ON · Tap: Back/Home · 2x Tap: End</span>
            </span>
            <span class="voice-call-end" onclick="event.stopPropagation(); endVoiceCall('Voice call disconnected');" title="End Call">✕</span>
        </button>
    </div>

    <!-- Bottom Navigation -->
    <nav class="mob-nav" aria-label="Primary Mobile Navigation">
        <div class="mob-nav-inner">
            <button type="button" class="mob-pill active" id="navHub" onclick="setMobilePage('hub')">✦ Agent Hub</button>
            <button type="button" class="mob-pill" id="navProj" onclick="setMobilePage('project')">👁️ Project View <span style="color:#F59E0B;">•</span></button>
        </div>
    </nav>
</div>

<!-- Settings & Activity History Modal -->
<div class="settings-modal-backdrop" id="settingsModal">
    <div class="settings-modal">
        <div class="settings-header">
            <div class="settings-title">⚙️ Settings &amp; Activity History</div>
            <button type="button" class="close-settings-btn" onclick="closeSettingsModal()">✕</button>
        </div>
        <div style="display:flex;gap:8px;font-size:11px;color:#9CA3AF;justify-content:space-between;background:#060709;padding:8px 12px;border-radius:10px;border:1px solid #181B22;">
            <span>Status: <strong style="color:#F59E0B;" id="stAgent">Ready</strong></span>
            <span>Active: <strong style="color:#F59E0B;" id="stActive">0</strong></span>
            <span>Done: <strong style="color:#10B981;" id="stComp">0</strong></span>
            <span>Failed: <strong style="color:#EF4444;" id="stFail">0</strong></span>
        </div>
        <input id="histSearchInput" type="text" placeholder="🔍 Search saved history..."
            style="width:100%;background:#060709;border:1px solid #222630;border-radius:8px;padding:8px 10px;color:#FFF;font-size:12px;"
            oninput="filterHistory(this.value)">
        <div class="workspace-pane" id="paneHistory"></div>
    </div>
</div>

<audio id="sriNeuralAudio" style="display:none;"></audio>

<script>
    const STATE = __STATE_PAYLOAD__;

    // Shared Voice & Mic Engine State (Hoisted to top of script to eliminate any TDZ / undefined variable crashes)
    const CALL_ACTIVE_KEY = 'sri_voice_call_active';
    let micSwitchTimer = null;
    let dictationRestartTimer = null;
    let orbRestartTimer = null;
    let orbUtteranceCommitTimer = null;
    let orbThinkingSafetyTimer = null;
    let promptResizeRaf = null;
    let dictationRec = null;
    let dictationSessionId = 0;
    let dictationCarryPrefix = '';
    let isDictating = false;

    let orbRec = null;
    let orbSessionId = 0;
    let orbCarryBuffer = '';
    let isVoiceCallActive = sessionStorage.getItem(CALL_ACTIVE_KEY) === '1';
    let isOrbListening = false;
    let isOrbThinking = false;
    let isOrbSpeaking = false;
    let speechCooldownUntil = 0;
    let cachedVoices = [];

    function loadCachedVoices() {
        try {
            if (window.speechSynthesis && window.speechSynthesis.getVoices) {
                const list = window.speechSynthesis.getVoices();
                if (list && list.length > 0) cachedVoices = list;
            }
        } catch (e) {}
    }
    loadCachedVoices();
    try {
        if (window.speechSynthesis && 'onvoiceschanged' in window.speechSynthesis) {
            window.speechSynthesis.onvoiceschanged = loadCachedVoices;
        }
    } catch (e) {}

    document.getElementById('stAgent').textContent = STATE.agentStatus;
    document.getElementById('stActive').textContent = STATE.activeTasks;
    document.getElementById('stComp').textContent = STATE.completed;
    document.getElementById('stFail').textContent = STATE.failed;
    document.getElementById('fileLabel').textContent = STATE.workspaceFile;
    document.getElementById('paneResearch').innerHTML = STATE.insightsHtml;
    document.getElementById('paneCode').textContent = STATE.code;

    // Render Voice & Chat Thread inside Dedicated Research Page (Home remains 100% uncluttered)
    const chatFeed = document.getElementById('hubChatFeed');
    const chatMsgs = Array.isArray(STATE.messages) ? STATE.messages : [];
    if (chatMsgs.length === 0) {
        chatFeed.innerHTML = '';
        chatFeed.classList.add('empty');
    } else {
        chatFeed.classList.remove('empty');
        chatFeed.innerHTML = chatMsgs.map(m => {
            const role = m.role === 'user' ? 'user' : 'assistant';
            const label = role === 'user' ? 'Kirubha' : 'SRI';
            const safe = String(m.content || '')
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;');
            return `<div class="chat-bubble ${role}"><span class="chat-sender">${label}</span>${safe}</div>`;
        }).join('');
        chatFeed.scrollTop = chatFeed.scrollHeight;
    }

    // Render full HTML preview inside a sandboxed iframe OR scrollable card container cleanly
    function renderPreviewAndCode(previewStr, codeStr, fileLabelStr) {
        const fileLbl = document.getElementById('fileLabel');
        if (fileLbl && fileLabelStr) fileLbl.textContent = fileLabelStr;
        const codeEl = document.getElementById('paneCode');
        if (codeEl) codeEl.textContent = codeStr || '';
        const previewContainer = document.getElementById('panePreview');
        if (!previewContainer) return;
        const str = String(previewStr || '');
        if (/<!doctype|<html/i.test(str)) {
            previewContainer.style.padding = '0';
            previewContainer.style.overflow = 'hidden';
            const frame = document.createElement('iframe');
            frame.className = 'preview-frame';
            frame.setAttribute('sandbox', 'allow-scripts allow-forms');
            frame.srcdoc = str;
            previewContainer.innerHTML = '';
            previewContainer.appendChild(frame);
        } else {
            previewContainer.style.padding = '12px';
            previewContainer.style.overflowY = 'auto';
            previewContainer.innerHTML = str;
        }
    }
    renderPreviewAndCode(STATE.previewHtml, STATE.code, STATE.workspaceFile);

    // Swipeable Workspace Files List
    const wsFilesList = Array.isArray(STATE.workspaceFiles) ? STATE.workspaceFiles : [];
    let activeWsFileIdx = Math.max(0, wsFilesList.findIndex(f => f.path === STATE.workspaceFile));

    function renderWorkspaceFilePills() {
        const strip = document.getElementById('projectFileStrip');
        const wrap = document.getElementById('projectFilePills');
        if (!strip || !wrap) return;
        if (!wsFilesList.length) {
            strip.style.display = 'none';
            return;
        }
        strip.style.display = 'flex';
        wrap.innerHTML = wsFilesList.map((f, idx) => {
            const cls = idx === activeWsFileIdx ? 'file-pill active' : 'file-pill';
            const safeShort = String(f.short || f.path || '').replace(/</g, '&lt;').replace(/>/g, '&gt;');
            return `<button type="button" class="${cls}" onclick="selectWorkspaceFileIdx(${idx})">${safeShort}</button>`;
        }).join('');
        const activeBtn = wrap.querySelector('.file-pill.active');
        if (activeBtn && activeBtn.scrollIntoView) {
            activeBtn.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' });
        }
    }

    function selectWorkspaceFileIdx(idx) {
        if (!wsFilesList.length) return;
        activeWsFileIdx = ((idx % wsFilesList.length) + wsFilesList.length) % wsFilesList.length;
        const item = wsFilesList[activeWsFileIdx];
        if (item) {
            renderPreviewAndCode(item.content, item.content, item.path);
            renderWorkspaceFilePills();
        }
    }

    function stepWorkspaceFile(delta) {
        selectWorkspaceFileIdx(activeWsFileIdx + delta);
    }
    renderWorkspaceFilePills();

    // Render Tracker, Comms & Portability Swipe Views cleanly from STATE
    (function renderSecondarySwipeViews() {
        const trackerEl = document.getElementById('paneTracker');
        const trTasks = Array.isArray(STATE.trackerTasks) ? STATE.trackerTasks : [];
        if (trackerEl) {
            const statsBar = `<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-bottom:12px;">
                <div style="background:#0E1117;border:1px solid #1E222B;border-radius:10px;padding:10px;"><div style="font-size:10px;color:#9CA3AF;">Status</div><div style="font-size:13px;font-weight:700;color:#F59E0B;margin-top:2px;">${STATE.agentStatus}</div></div>
                <div style="background:#0E1117;border:1px solid #1E222B;border-radius:10px;padding:10px;"><div style="font-size:10px;color:#9CA3AF;">Active</div><div style="font-size:13px;font-weight:700;color:#60A5FA;margin-top:2px;">${STATE.activeTasks}</div></div>
                <div style="background:#0E1117;border:1px solid #1E222B;border-radius:10px;padding:10px;"><div style="font-size:10px;color:#9CA3AF;">Completed</div><div style="font-size:13px;font-weight:700;color:#10B981;margin-top:2px;">${STATE.completed}</div></div>
            </div>`;
            const listHtml = trTasks.length
                ? trTasks.map(t => `<div style="background:#0E1117;border:1px solid #1E222B;border-radius:10px;padding:10px;margin-bottom:8px;">
                    <div style="display:flex;justify-content:space-between;font-size:11px;margin-bottom:4px;">
                        <span style="color:#F4F4F5;font-weight:600;">${String(t.title || '').replace(/</g,'&lt;')}</span>
                        <span style="color:${t.status === 'COMPLETED' ? '#10B981' : '#F59E0B'};font-weight:700;">${t.status} · ${t.progress || 100}%</span>
                    </div>
                    ${t.file ? `<div style="font-family:'JetBrains Mono',monospace;font-size:10px;color:#9CA3AF;">workspace/${String(t.file).replace(/</g,'&lt;')}</div>` : ''}
                </div>`).join('')
                : '<div style="color:#71717A;font-size:12px;text-align:center;padding:20px;">No background tasks tracked yet. Swipe back or use Quick Chips to dispatch a build.</div>';
            trackerEl.innerHTML = statsBar + listHtml;
        }
        const commsEl = document.getElementById('paneComms');
        if (commsEl) {
            const wa = STATE.whatsappAlertSummary || {};
            commsEl.innerHTML = `
                <div style="background:#0E1117;border:1px solid rgba(16,185,129,0.3);border-radius:12px;padding:14px;margin-bottom:10px;">
                    <div style="font-size:12px;font-weight:700;color:#34D399;margin-bottom:4px;">Twilio Voice Call &amp; Automated WhatsApp Bridge</div>
                    <div style="font-size:11.5px;color:#D4D4D8;line-height:1.5;">100% Hackathon Completion WhatsApp Alert: <strong>${STATE.allTasksCompleted ? 'All Tasks Completed (Triggered)' : 'Monitoring Pending Tasks'}</strong></div>
                    ${wa.message ? `<div style="font-size:11px;color:#9CA3AF;margin-top:6px;">${String(wa.message).replace(/</g,'&lt;')}</div>` : ''}
                </div>
                <button type="button" onclick="openControlSection('Call & Msg')" style="width:100%;padding:10px;border-radius:10px;background:#F59E0B;color:#0b0b0b;font-weight:700;font-size:12px;border:none;cursor:pointer;">Open Twilio Call &amp; WhatsApp Panel</button>`;
        }
        const portEl = document.getElementById('panePortability');
        if (portEl) {
            portEl.innerHTML = `
                <div style="background:#0E1117;border:1px solid #1E222B;border-radius:12px;padding:14px;margin-bottom:10px;font-size:12px;line-height:1.6;">
                    <div style="display:flex;justify-content:space-between;border-bottom:1px solid #1E222B;padding-bottom:6px;margin-bottom:6px;"><span style="color:#9CA3AF;">Workspace Active File</span><span style="color:#F59E0B;font-family:'JetBrains Mono',monospace;">${String(STATE.workspaceFile).replace(/</g,'&lt;')}</span></div>
                    <div style="display:flex;justify-content:space-between;border-bottom:1px solid #1E222B;padding-bottom:6px;margin-bottom:6px;"><span style="color:#9CA3AF;">Workspace Modules</span><span style="color:#E4E4E7;">${wsFilesList.length} files synced</span></div>
                    <div style="display:flex;justify-content:space-between;"><span style="color:#9CA3AF;">Sandbox Guard</span><span style="color:#34D399;">Enforced (workspace/ &amp; outputs/)</span></div>
                </div>
                <button type="button" onclick="openControlSection('Portability')" style="width:100%;padding:10px;border-radius:10px;background:#14161D;border:1px solid rgba(245,158,11,0.45);color:#F5E6C8;font-weight:600;font-size:12px;cursor:pointer;">Open Safe Auto-Code Editor &amp; Uploads</button>`;
        }
    })();

    const histList = STATE.historyLog || [];
    const TYPE_COLOR = { task: '#F59E0B', chat: '#10B981', voice: '#60A5FA', research: '#A78BFA', whatsapp_alert: '#22C55E' };
    const TYPE_ICON = { task: '🛠️', chat: '💬', voice: '🎙️', research: '✦', whatsapp_alert: '📲' };

    function buildHistoryHtml(list) {
        if (!list || list.length === 0) {
            return '<div style="color:#71717A;padding:24px;text-align:center;font-size:12px;">📭 No history recorded yet.</div>';
        }
        return list.map(item => {
            const type = item.type || 'task';
            const color = TYPE_COLOR[type] || '#F59E0B';
            const icon = TYPE_ICON[type] || '📌';
            const badge = type.toUpperCase();
            const ts = item.timestamp || item.iso || '';
            const task = (item.task || 'Prompt').replace(/</g,'&lt;').replace(/>/g,'&gt;');
            const det = (item.details || '').replace(/</g,'&lt;').replace(/>/g,'&gt;');
            const shortDet = det.length > 220 ? det.slice(0, 217) + '…' : det;
            return `
            <div style="background:#0E1117;border:1px solid #1E222B;border-radius:10px;padding:10px 12px;margin-bottom:8px;">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:5px;">
                    <span style="font-size:9.5px;color:${color};font-weight:700;letter-spacing:0.5px;">${icon} ${badge}</span>
                    <span style="font-size:9.5px;color:#71717A;">⏱️ ${ts}</span>
                </div>
                <div style="font-weight:600;color:${color};font-size:12px;margin-bottom:4px;line-height:1.4;">${task}</div>
                <div style="color:#D1D5DB;font-size:11px;line-height:1.5;">${shortDet}</div>
            </div>`;
        }).join('');
    }
    document.getElementById('paneHistory').innerHTML = buildHistoryHtml(histList);

    function filterHistory(q) {
        const lower = q.toLowerCase().trim();
        const filtered = !lower ? histList : histList.filter(e => ((e.task||'')+(e.details||'')).toLowerCase().includes(lower));
        document.getElementById('paneHistory').innerHTML = buildHistoryHtml(filtered);
    }

    const LANG_MODES = [
        { code: 'ta-IN', short: 'தமிழ்', label: '🌐 தமிழ் (ta-IN)' },
        { code: 'en-IN', short: 'English', label: '🌐 English (en-IN)' },
        { code: 'hi-IN', short: 'हिन्दी', label: '🌐 हिन्दी (hi-IN)' },
        { code: 'te-IN', short: 'తెలుగు', label: '🌐 తెలుగు (te-IN)' },
        { code: 'ml-IN', short: 'മലയാളം', label: '🌐 മലയാളം (ml-IN)' },
        { code: 'kn-IN', short: 'ಕನ್ನಡ', label: '🌐 ಕನ್ನಡ (kn-IN)' }
    ];
    let langIdx = parseInt(localStorage.getItem('sri_lang_idx') || '0', 10);
    if (isNaN(langIdx) || langIdx < 0 || langIdx >= LANG_MODES.length) langIdx = 0;

    function updateLangUI() {
        const langBtn = document.getElementById('langBtn');
        if (langBtn) langBtn.textContent = '🌐 ' + LANG_MODES[langIdx].short;
        document.documentElement.lang = LANG_MODES[langIdx].code;
    }
    updateLangUI();

    function cycleVoiceLang() {
        langIdx = (langIdx + 1) % LANG_MODES.length;
        localStorage.setItem('sri_lang_idx', String(langIdx));
        updateLangUI();
        document.getElementById('orbHint').textContent = 'Voice & AI Language: ' + LANG_MODES[langIdx].label;
        if (typeof isVoiceCallActive !== 'undefined' && isVoiceCallActive && !isOrbSpeaking && !isOrbThinking) {
            stopOrbVoice(true);
            setTimeout(startOrbContinuousListener, 80);
        }
    }

    let currentProjectTab = localStorage.getItem('sri_active_tab') === 'code' ? 'code' : 'preview';

    function switchTab(mode, instant) {
        const resolvedMode = mode === 'code' ? 'code' : 'preview';
        currentProjectTab = resolvedMode;
        document.getElementById('tabPreview').classList.toggle('active', resolvedMode === 'preview');
        document.getElementById('tabCode').classList.toggle('active', resolvedMode === 'code');
        const tabTrack = document.getElementById('projectTabsTrack');
        if (tabTrack) {
            if (instant) tabTrack.classList.add('no-anim');
            tabTrack.style.transform = resolvedMode === 'code' ? 'translate3d(-50%, 0, 0)' : 'translate3d(0%, 0, 0)';
            if (instant) {
                void tabTrack.offsetWidth;
                tabTrack.classList.remove('no-anim');
            }
        }
        const prevBtn = document.getElementById('swipePrevAction');
        const nextBtn = document.getElementById('swipeNextAction');
        if (prevBtn) prevBtn.textContent = resolvedMode === 'code' ? '‹ Slide to Preview' : '‹ Slide to Research';
        if (nextBtn) nextBtn.textContent = resolvedMode === 'preview' ? 'Slide to Code ›' : 'Slide to Tracker ›';
        localStorage.setItem('sri_active_tab', resolvedMode);
    }

    function handleProjectSwipeButton(dir) {
        if (dir === 'next') {
            if (currentProjectTab === 'preview') switchTab('code', false);
            else setMobilePage('tracker', false);
        } else {
            if (currentProjectTab === 'code') switchTab('preview', false);
            else setMobilePage('research', false);
        }
    }

    const PAGE_ORDER = ['hub', 'research', 'project', 'tracker', 'comms', 'portability'];
    let currentActivePage = localStorage.getItem('sri_active_page') || 'hub';
    let previousActivePage = localStorage.getItem('sri_prev_page') || 'hub';

    function setMobilePage(page, instant) {
        const validPage = PAGE_ORDER.includes(page) ? page : 'hub';
        if (validPage !== currentActivePage) {
            previousActivePage = currentActivePage || 'hub';
            localStorage.setItem('sri_prev_page', previousActivePage);
            currentActivePage = validPage;
        }
        const pageIdx = PAGE_ORDER.indexOf(validPage);
        const track = document.getElementById('pagesTrack');
        if (track) {
            if (instant) {
                track.classList.add('no-anim');
            }
            track.style.transform = `translate3d(-${pageIdx * (100 / PAGE_ORDER.length)}%, 0, 0)`;
            if (instant) {
                void track.offsetWidth;
                track.classList.remove('no-anim');
            }
        }

        document.body.classList.remove('off-home', 'page-research', 'page-project', 'page-tracker', 'page-comms', 'page-portability');
        if (validPage !== 'hub') document.body.classList.add('off-home', 'page-' + validPage);

        const navHubEl = document.getElementById('navHub');
        const navProjEl = document.getElementById('navProj');
        if (navHubEl) navHubEl.classList.toggle('active', validPage === 'hub');
        if (navProjEl) navProjEl.classList.toggle('active', validPage === 'project');

        const topMap = {
            hub: 'topTabHub',
            research: 'topTabResearch',
            project: 'topTabProject',
            tracker: 'topTabTracker',
            comms: 'topTabComms',
            portability: 'topTabPortability',
        };
        Object.keys(topMap).forEach((k) => {
            const btn = document.getElementById(topMap[k]);
            if (btn) {
                const isAct = validPage === k;
                btn.classList.toggle('active', isAct);
                if (isAct && btn.scrollIntoView) {
                    btn.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' });
                }
            }
        });
        localStorage.setItem('sri_active_page', validPage);
    }

    function openControlSection(sectionLabel) {
        openBackendSettings();
        try {
            const parentDoc = window.parent.document;
            const sidebar = parentDoc.querySelector('[data-testid="stSidebar"]');
            if (sidebar) {
                const kw = sectionLabel === 'Call & Msg' ? 'twilio voice call' : (sectionLabel === 'Tracker' ? 'workspaces & background' : 'safe auto-code editor');
                const expanders = sidebar.querySelectorAll('summary');
                for (const s of expanders) {
                    if ((s.textContent || '').toLowerCase().includes(kw)) {
                        const det = s.closest('details');
                        if (det && !det.hasAttribute('open')) s.click();
                        s.scrollIntoView({ behavior: 'smooth', block: 'center' });
                        break;
                    }
                }
            }
        } catch (e) {}
    }

    function navigateBackOrHome() {
        const target = (currentActivePage !== 'hub' && previousActivePage && previousActivePage !== currentActivePage)
            ? previousActivePage
            : 'hub';
        setMobilePage(target, false);
        const label = target === 'research' ? 'Research' : (target === 'project' ? 'Preview' : 'Hub');
        if (typeof isVoiceCallActive !== 'undefined' && isVoiceCallActive) {
            const hint = document.getElementById('orbHint');
            if (hint) {
                hint.classList.remove('speaking', 'thinking');
                hint.classList.add('listening');
                hint.textContent = 'Returned to ' + label + ' · Continuous call active';
            }
            updateMiniOrbsUI('listening', 'Back on ' + label + ' · Listening...');
            syncVoiceCallDockUI('listening', 'Back on ' + label + ' · Listening...');
        }
    }

    // Explicit Voice Call Stop Command Detector (English + Tamil)
    function isStopVoiceCommand(text) {
        const u = String(text || '').toLowerCase().trim();
        if (!u) return false;
        const words = u.split(/\s+/).filter(Boolean);
        const stopPhrases = [
            'stop call', 'end call', 'disconnect', 'hang up', 'cut the call',
            'stop listening', 'close call', 'bye sri', 'goodbye sri',
            'கால் நிறுத்து', 'கால் முடி', 'கால் கட்', 'பேச்சை நிறுத்து',
            'நிறுத்து', 'கட் பண்ணு', 'போதுமா'
        ];
        if (stopPhrases.some(p => u.includes(p))) return true;
        if (words.length <= 3 && /\bstop\b/i.test(u)) return true;
        return false;
    }

    // Voice & Reply Intent Detector (Tamil + Tanglish + English + Workspace context)
    function detectVoiceNavigationIntent(userText, replyText, workspaceFile) {
        const u = String(userText || '').toLowerCase();
        const r = String(replyText || '').toLowerCase();
        const f = String(workspaceFile || '').toLowerCase();

        const hubPure = [
            'go home', 'open hub', 'back to hub', 'main screen', 'show hub', 'home page', 'go back',
            'முகப்பு', 'ஹப்', 'திரும்பு', 'ஹோம்'
        ];
        if (hubPure.some(k => u.includes(k))) {
            return { page: 'hub', tab: null, pureNav: u.trim().split(/\s+/).length <= 5 };
        }

        const codeKeys = [
            'show code', 'open code', 'switch to code', 'go to code', 'source code', 'code view', 'code tab', 'code screen',
            'view code', 'inspect code', 'check code', 'கோடு காட்டு', 'கோட் காட்டு', 'சோர்ஸ் கோடு'
        ];
        const previewKeys = [
            'preview', 'open preview', 'show preview', 'preview page', 'go to preview', 'switch to preview',
            'view preview', 'preview this', 'open live preview', 'latest work', 'open project', 'show project',
            'login.html', 'dashboard ui', 'build ui', 'create ui', 'design ui', 'refine ui', 'generate ui',
            'build a website', 'create a page', 'landing page', 'web app',
            'ப்ரிவியூ', 'பிரிவியூ', 'ui உருவாக்கு', 'டிசைன் காட்டு', 'ப்ராஜெக்ட்'
        ];
        const codingExclusions = [
            'write code', 'write python', 'python code', 'javascript code', 'fix bug', 'debug',
            'syntax error', 'event listener', 'event loop', 'event handler', 'dom event',
            'binary search', 'linear search', 'search tree', 'find index', 'find element', 'regex'
        ];
        const researchKeys = [
            'research', 'open research', 'research page', 'insights', 'insight', 'search web',
            'search about', 'search for', 'look up', 'find info', 'find information',
            'investigate', 'deep dive', 'study about', 'study on', 'information about', 'info about',
            'details about', 'explain about', 'tell me about', 'summarize', 'summary of',
            'world news', 'latest news', 'live news', 'tech news', 'technology news',
            'tech updates', 'technology updates', 'ai news', 'ai updates', 'latest updates',
            'recent updates', 'live updates', 'headlines', 'current affairs', "what's new", 'whats new',
            'news', 'breaking news', 'weather today', 'weather in',
            'analyze', 'analysis', 'compare', 'case study', 'literature review', 'fact check',
            'market trends', 'trends in', 'brainstorm',
            'ரிசர்ச்', 'ஆராய்ச்சி', 'தேடு', 'செய்தி', 'செய்திகள்', 'நியூஸ்', 'டெக் நியூஸ்',
            'புதிய தொழில்நுட்பம்', 'வானிலை', 'தகவல்', 'விளக்கு', 'பற்றி சொல்லு', 'பற்றி கூறு', 'அனலைஸ்', 'ஒப்பீடு'
        ];

        const pureNavPhrases = [
            'open ', 'show ', 'go to ', 'switch to ', 'navigate to ', 'view ', 'move to ', 'take me to ', 'check ', 'pull up ',
            'காட்டு', 'திற', 'போ', 'மாத்து'
        ];
        const isShortCmd = u.trim().length > 0 && u.trim().split(/\s+/).length <= 5;
        const looksPureNav = (
            (isShortCmd && pureNavPhrases.some(p => u.includes(p)) && !/\babout\b|\bon\b|\bfor\b|\bbuild\b|\bcreate\b/.test(u))
            || /^(preview this|open preview|show preview|switch to preview|go to preview|open research|show research|switch to research|go to research|open code|show code|switch to code|go to code)$/i.test(u.trim())
        );

        if (codeKeys.some(k => u.includes(k)) || ['code tab', 'source code tab', 'opening code'].some(k => r.includes(k))) {
            return { page: 'project', tab: 'code', pureNav: looksPureNav };
        }
        const hasExplicitResearchWord = ['research', 'insights', 'tech news', 'tech updates', 'ai news', 'ரிசர்ச்', 'ஆராய்ச்சி', 'செய்தி', 'நியூஸ்'].some(k => u.includes(k));
        const isCodingOnly = codingExclusions.some(ex => u.includes(ex)) && !hasExplicitResearchWord;
        if (!isCodingOnly && (f.includes('research.html') || researchKeys.some(k => u.includes(k)))) {
            return { page: 'research', tab: null, pureNav: looksPureNav };
        }
        if (previewKeys.some(k => u.includes(k)) || /\b(open|show|build|create|design)\s+(a\s+|an\s+|the\s+)?(ui|preview|website|webpage|dashboard)\b/.test(u) || r.includes('preview screen')) {
            return { page: 'project', tab: 'preview', pureNav: looksPureNav };
        }
        return { page: null, tab: null, pureNav: false };
    }

    function showOptimisticResearchLoading(queryText) {
        const pane = document.getElementById('paneResearch');
        if (!pane) return;
        const safeQ = String(queryText || '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');
        pane.innerHTML = `
            <div style="font-family:'Inter',-apple-system,BlinkMacSystemFont,sans-serif;color:#F4F4F5;padding:4px;">
                <div style="background:linear-gradient(135deg,rgba(245,158,11,0.14),rgba(16,185,129,0.06));border:1px solid rgba(245,158,11,0.42);border-radius:14px;padding:16px;margin-bottom:12px;">
                    <div style="display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:10px;">
                        <span style="font-size:11px;color:#F59E0B;font-weight:700;text-transform:uppercase;letter-spacing:0.6px;">✦ SRI Research Engine</span>
                        <span style="font-size:11px;color:#34D399;font-weight:600;">● Researching Live...</span>
                    </div>
                    <div style="font-size:14px;font-weight:600;color:#FFFFFF;margin-bottom:8px;">&ldquo;${safeQ}&rdquo;</div>
                    <div style="font-size:12.5px;color:#CBD5E1;line-height:1.55;">Gathering verified findings and preparing structured insights right here...</div>
                </div>
            </div>
        `;
    }

    function applySeamlessVoiceNavigation(page, tab) {
        if (page) {
            setMobilePage(page, false);
        }
        if (tab === 'code' || tab === 'preview') {
            switchTab(tab);
        }
        if (typeof isVoiceCallActive !== 'undefined' && isVoiceCallActive && !isOrbSpeaking && !isOrbThinking) {
            const label = page === 'research'
                ? 'Research'
                : (page === 'project' ? (tab === 'code' ? 'Code' : 'Preview') : 'Hub');
            updateMiniOrbsUI('listening', label + ' · Continuous Mic Active');
            syncVoiceCallDockUI('listening', label + ' · Continuous Mic Active');
        }
    }

    // Restore saved screen cleanly first, then apply automatic voice/reply slide transition if a new turn routed
    const initialSavedPage = localStorage.getItem('sri_active_page') || 'hub';
    const initialSavedTab = localStorage.getItem('sri_active_tab') === 'code' ? 'code' : 'preview';
    setMobilePage(initialSavedPage, true);
    switchTab(initialSavedTab, true);

    const pendingVoicePage = sessionStorage.getItem('sri_pending_voice_page');
    const pendingVoiceTab = sessionStorage.getItem('sri_pending_voice_tab');
    const navTurnKey = STATE.turnId
        ? String(STATE.turnId)
        : `${STATE.lastUserQuery || ''}||${STATE.spokenText || ''}||${STATE.targetPage || ''}`;
    const alreadyRoutedKey = sessionStorage.getItem('sri_last_routed_key');

    if (pendingVoicePage) {
        sessionStorage.removeItem('sri_pending_voice_page');
        sessionStorage.removeItem('sri_pending_voice_tab');
        if (navTurnKey && navTurnKey !== '||||') {
            sessionStorage.setItem('sri_last_routed_key', navTurnKey);
        }
        const effectivePage = STATE.targetPage || pendingVoicePage;
        const effectiveTab = STATE.targetTab || pendingVoiceTab;
        applySeamlessVoiceNavigation(effectivePage, effectiveTab);
    } else if (navTurnKey && navTurnKey !== '||||' && navTurnKey !== alreadyRoutedKey) {
        const autoIntent = detectVoiceNavigationIntent(STATE.lastUserQuery, STATE.spokenText, STATE.workspaceFile);
        const resolvedPage = STATE.targetPage || autoIntent.page;
        const resolvedTab = STATE.targetTab || autoIntent.tab;
        if (resolvedPage) {
            sessionStorage.setItem('sri_last_routed_key', navTurnKey);
            applySeamlessVoiceNavigation(resolvedPage, resolvedTab);
        }
    }

    const DRAWER_OPEN_KEY = 'sri_control_drawer_open';

    function getDrawerStorage() {
        try {
            if (window.parent && window.parent.sessionStorage) return window.parent.sessionStorage;
        } catch (e) {}
        return sessionStorage;
    }

    function setDrawerOpenPref(isOpen) {
        try { getDrawerStorage().setItem(DRAWER_OPEN_KEY, isOpen ? '1' : '0'); } catch (e) {}
        try { sessionStorage.setItem(DRAWER_OPEN_KEY, isOpen ? '1' : '0'); } catch (e) {}
    }

    function isDrawerOpenPref() {
        try {
            const pVal = getDrawerStorage().getItem(DRAWER_OPEN_KEY);
            if (pVal !== null) return pVal === '1';
        } catch (e) {}
        try { return sessionStorage.getItem(DRAWER_OPEN_KEY) === '1'; } catch (e) { return false; }
    }

    function findStreamlitExpandBtn(parentDoc) {
        const selectors = [
            '[data-testid="stExpandSidebarButton"] button',
            '[data-testid="stExpandSidebarButton"]',
            '[data-testid="stSidebarCollapsedControl"] button',
            '[data-testid="collapsedControl"] button',
            '[data-testid="collapsedControl"]',
            'button[aria-label*="open sidebar" i]',
            'button[aria-label*="expand sidebar" i]',
            'button[title*="open sidebar" i]',
        ];
        for (const sel of selectors) {
            const el = parentDoc.querySelector(sel);
            if (el) return el;
        }
        return null;
    }

    function bindSidebarCollapsePersistence(parentDoc, sidebar) {
        try {
            const pWin = window.parent || window;
            if (!pWin.__sriDrawerCloseBound) {
                pWin.__sriDrawerCloseBound = true;
                parentDoc.addEventListener('click', (ev) => {
                    const target = ev.target && ev.target.closest
                        ? ev.target.closest('[data-testid="stSidebarCollapseButton"], [data-testid="stSidebarNavCollapseButton"], button[aria-label*="close sidebar" i], button[aria-label*="collapse sidebar" i]')
                        : null;
                    if (target) {
                        setDrawerOpenPref(false);
                        const sb = parentDoc.querySelector('[data-testid="stSidebar"]');
                        if (sb) sb.removeAttribute('data-sri-drawer-open');
                    }
                }, true);
            }
            if (!pWin.__sriDrawerObserver && typeof MutationObserver !== 'undefined') {
                pWin.__sriDrawerObserver = new MutationObserver(() => {
                    if (!isDrawerOpenPref()) return;
                    const sb = parentDoc.querySelector('[data-testid="stSidebar"]');
                    if (sb && sb.getAttribute('data-sri-drawer-open') !== 'true') {
                        sb.setAttribute('data-sri-drawer-open', 'true');
                        sb.setAttribute('aria-expanded', 'true');
                    }
                });
                pWin.__sriDrawerObserver.observe(parentDoc.body || parentDoc.documentElement, {
                    childList: true,
                    subtree: true,
                    attributes: true,
                    attributeFilter: ['aria-expanded'],
                });
            }
        } catch (e) {}
    }

    function applyControlDrawerOpen(shouldClickExpand) {
        try {
            const parentDoc = window.parent.document;
            const sidebar = parentDoc.querySelector('[data-testid="stSidebar"]');
            if (!sidebar) return false;
            bindSidebarCollapsePersistence(parentDoc, sidebar);
            const rect = sidebar.getBoundingClientRect ? sidebar.getBoundingClientRect() : { width: 0 };
            const wasCollapsed = sidebar.getAttribute('aria-expanded') === 'false' || !rect || rect.width < 40;
            if (shouldClickExpand && wasCollapsed) {
                const expandBtn = findStreamlitExpandBtn(parentDoc);
                if (expandBtn) expandBtn.click();
            }
            sidebar.setAttribute('data-sri-drawer-open', 'true');
            sidebar.setAttribute('aria-expanded', 'true');
            return true;
        } catch (e) {
            return false;
        }
    }

    function openBackendSettings() {
        setDrawerOpenPref(true);
        const openedDrawer = applyControlDrawerOpen(true);
        if (!openedDrawer) {
            document.getElementById('settingsModal').classList.add('open');
        }
    }

    function closeSettingsModal() {
        document.getElementById('settingsModal').classList.remove('open');
    }

    if (isDrawerOpenPref()) {
        applyControlDrawerOpen(true);
        setTimeout(() => { if (isDrawerOpenPref()) applyControlDrawerOpen(false); }, 180);
    }

    // Auto-expanding fixed-height textarea (max 58px / 3 lines, then vertical scroll)
    function autoResizePromptInput() {
        const el = document.getElementById('promptInput');
        if (!el) return;
        const MAX_H = 58;
        el.style.height = 'auto';
        const nextH = Math.min(MAX_H, Math.max(24, el.scrollHeight));
        el.style.height = nextH + 'px';
        el.style.overflowY = el.scrollHeight > MAX_H ? 'auto' : 'hidden';
    }

    function schedulePromptResize() {
        if (typeof requestAnimationFrame !== 'function') {
            autoResizePromptInput();
            return;
        }
        if (promptResizeRaf) return;
        promptResizeRaf = requestAnimationFrame(() => {
            promptResizeRaf = null;
            autoResizePromptInput();
        });
    }

    function handlePromptKeydown(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            submitPrompt();
        }
    }

    function appendOptimisticMessage(role, content) {
        if (!content) return;
        const feed = document.getElementById('hubChatFeed');
        if (!feed) return;
        feed.classList.remove('empty');
        const emptyEl = feed.querySelector('.hub-chat-empty');
        if (emptyEl) emptyEl.remove();
        const safe = String(content)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');
        const label = role === 'user' ? 'Kirubha' : 'SRI';
        const bubble = document.createElement('div');
        bubble.className = 'chat-bubble ' + role;
        bubble.innerHTML = `<span class="chat-sender">${label}</span>${safe}`;
        feed.appendChild(bubble);
        feed.scrollTop = feed.scrollHeight;
    }

    function triggerInstantNavigationForPrompt(promptText) {
        const intent = detectVoiceNavigationIntent(promptText, '', STATE.workspaceFile);
        const resolvedPage = intent && intent.page ? intent.page : 'research';
        const resolvedTab = intent ? intent.tab : null;
        sessionStorage.setItem('sri_pending_voice_page', resolvedPage);
        if (resolvedTab) {
            sessionStorage.setItem('sri_pending_voice_tab', resolvedTab);
        } else {
            sessionStorage.removeItem('sri_pending_voice_tab');
        }
        applySeamlessVoiceNavigation(resolvedPage, resolvedTab);
        if (resolvedPage === 'research' && !(intent && intent.pureNav)) {
            showOptimisticResearchLoading(promptText);
        }
        return intent;
    }

    // Bottom Chat Bar Submit -> Routes output cleanly to Research or Preview so Home stays uncluttered
    function submitPrompt() {
        const inputEl = document.getElementById('promptInput');
        const val = inputEl.value.trim();
        if (!val) return;
        stopChatDictation(false);
        inputEl.value = '';
        inputEl.scrollTop = 0;
        autoResizePromptInput();
        appendOptimisticMessage('user', val);
        const chatIntent = triggerInstantNavigationForPrompt(val);
        if (chatIntent && chatIntent.pureNav && chatIntent.page) {
            return;
        }
        sendToPython(val, 'chat');
    }

    function sendChatPreset(promptText) {
        stopChatDictation(false);
        appendOptimisticMessage('user', promptText);
        const chatIntent = triggerInstantNavigationForPrompt(promptText);
        if (chatIntent && chatIntent.pureNav && chatIntent.page) {
            return;
        }
        sendToPython(promptText, 'chat');
    }

    function sendToPython(command, channel) {
        const cleanCommand = String(command || '').trim();
        if (!cleanCommand) return;
        const resolvedChannel = channel || 'chat';
        stopChatDictation(false);
        if (resolvedChannel === 'orb') {
            stopOrbVoice(true);
        }
        if (orbThinkingSafetyTimer) {
            clearTimeout(orbThinkingSafetyTimer);
            orbThinkingSafetyTimer = null;
        }
        const activeLangCode = (LANG_MODES[langIdx] && LANG_MODES[langIdx].code) || 'ta-IN';
        const wirePayload = `__SRI_META__${JSON.stringify({ channel: resolvedChannel, lang: activeLangCode })}__${cleanCommand}`;
        if (resolvedChannel === 'orb') {
            isOrbThinking = true;
            const hint = document.getElementById('orbHint');
            if (hint) {
                hint.classList.remove('listening', 'speaking');
                hint.classList.add('thinking');
                hint.textContent = 'SRI is thinking...';
            }
            updateMiniOrbsUI('idle', 'SRI is thinking...');
            syncVoiceCallDockUI('thinking', 'SRI is thinking...');
            orbThinkingSafetyTimer = setTimeout(() => {
                if (isOrbThinking) {
                    isOrbThinking = false;
                    if (isVoiceCallActive && !isOrbSpeaking && !isOrbListening) {
                        syncVoiceCallDockUI('listening', 'Ready — Speak again...');
                        startOrbContinuousListener();
                    }
                }
            }, 15000);
        }
        sessionStorage.setItem('sri_input_channel', resolvedChannel);
        try {
            const parentWin = window.parent || window;
            const parentDoc = parentWin.document;
            const bridgeInput = parentDoc.querySelector('input[aria-label="sri_hidden_bridge"], input[placeholder="sri_hidden_bridge"], input[aria-label="sri_bridge_input"]');
            if (bridgeInput) {
                const inputProto = (parentWin.HTMLInputElement || window.HTMLInputElement).prototype;
                const setter = Object.getOwnPropertyDescriptor(inputProto, 'value')?.set;
                if (setter) {
                    setter.call(bridgeInput, wirePayload);
                } else {
                    bridgeInput.value = wirePayload;
                }
                bridgeInput.dispatchEvent(new Event('input', { bubbles: true }));
                bridgeInput.dispatchEvent(new Event('change', { bubbles: true }));
                bridgeInput.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true }));
                return;
            }
        } catch (e) {}
        try {
            const url = new URL((window.parent || window).location.href);
            url.searchParams.set('sri_cmd', wirePayload);
            url.searchParams.set('ts', String(Date.now()));
            (window.parent || window).history.replaceState({}, '', url);
            (window.parent || window).location.reload();
        } catch (reloadErr) {
            isOrbThinking = false;
        }
    }

    function clearMicSwitchTimer() {
        if (micSwitchTimer) {
            clearTimeout(micSwitchTimer);
            micSwitchTimer = null;
        }
    }

    function clearDictationRestartTimer() {
        if (dictationRestartTimer) {
            clearTimeout(dictationRestartTimer);
            dictationRestartTimer = null;
        }
    }

    function clearOrbRestartTimer() {
        if (orbRestartTimer) {
            clearTimeout(orbRestartTimer);
            orbRestartTimer = null;
        }
        if (orbUtteranceCommitTimer) {
            clearTimeout(orbUtteranceCommitTimer);
            orbUtteranceCommitTimer = null;
        }
    }

    function pickBestTranscript(resultAltList, preferredLangCode) {
        if (!resultAltList || resultAltList.length === 0) return '';
        if (preferredLangCode === 'ta-IN' && resultAltList.length > 1) {
            for (let j = 0; j < resultAltList.length; j++) {
                const candidate = String(resultAltList[j].transcript || '').trim();
                if (/[\u0B80-\u0BFF]/.test(candidate)) {
                    return candidate;
                }
            }
        }
        return String(resultAltList[0].transcript || '').trim();
    }

    function syncVoiceCallDockUI(mode, statusText) {
        const dock = document.getElementById('voiceCallDock');
        const stateEl = document.getElementById('voiceCallState');
        const subEl = document.getElementById('voiceCallSub');
        const iconEl = document.getElementById('voiceCallRoundOrb');
        if (!dock || !stateEl || !subEl || !iconEl) return;

        if (!isVoiceCallActive) {
            dock.classList.remove('active', 'speaking', 'thinking');
            return;
        }

        const activeLang = LANG_MODES[langIdx] || LANG_MODES[0];
        dock.classList.add('active');
        dock.classList.remove('speaking', 'thinking');

        if (mode === 'speaking') {
            dock.classList.add('speaking');
            iconEl.textContent = '🔊';
            stateEl.textContent = statusText || 'SRI Speaking...';
            subEl.textContent = 'Tap: Back/Home · Double-Tap: End Call';
        } else if (mode === 'thinking') {
            dock.classList.add('thinking');
            iconEl.textContent = '✦';
            stateEl.textContent = statusText || 'SRI Thinking...';
            subEl.textContent = 'Continuous Call (' + activeLang.short + ') · Double-Tap: End';
        } else {
            iconEl.textContent = '🎙️';
            stateEl.textContent = statusText || ('Live Call (' + activeLang.short + ') · Listening...');
            subEl.textContent = 'Walkie-Talkie ON · Tap: Back/Home · 2x Tap: End';
        }
    }

    function updateMiniOrbsUI(state, text) {
        ['Research', 'Project'].forEach(suffix => {
            const btn = document.getElementById('miniOrb' + suffix);
            const st = document.getElementById('statusOrb' + suffix);
            if (!btn || !st) return;
            btn.classList.remove('listening', 'speaking');
            if (state === 'listening') btn.classList.add('listening');
            if (state === 'speaking') btn.classList.add('speaking');
            if (text) st.textContent = text;
        });
    }

    // Engine A UI Helpers (Strictly scoped to bottom chat bar)
    let dictationFinishTimer = null;
    function setChatBarMicVisual(state, label) {
        const bar = document.getElementById('chatBar');
        const loader = document.getElementById('chatWaveLoader');
        const statusEl = document.getElementById('chatMicStatus');
        const btn = document.getElementById('inlineMicBtn');
        if (dictationFinishTimer) {
            clearTimeout(dictationFinishTimer);
            dictationFinishTimer = null;
        }
        bar.classList.remove('recording', 'processing');
        loader.classList.remove('active', 'processing');
        btn.classList.remove('active');

        if (state === 'recording') {
            bar.classList.add('recording');
            loader.classList.add('active');
            btn.classList.add('active');
            statusEl.textContent = label || ('🎙️ ' + LANG_MODES[langIdx].short);
        } else if (state === 'processing') {
            bar.classList.add('processing');
            loader.classList.add('active', 'processing');
            statusEl.textContent = label || 'Processing...';
        }
    }

    // Engine A Stop: Only resets bottom chat dictation controls
    function stopChatDictation(showProcessingFlash) {
        clearDictationRestartTimer();
        dictationSessionId += 1;
        dictationCarryPrefix = '';
        if (dictationRec) {
            try {
                dictationRec.onresult = null;
                dictationRec.onerror = null;
                dictationRec.onend = null;
                dictationRec.abort();
            } catch (e) {}
            dictationRec = null;
        }
        const wasDictating = isDictating;
        isDictating = false;
        if (showProcessingFlash && wasDictating) {
            setChatBarMicVisual('processing', 'Ready...');
            dictationFinishTimer = setTimeout(() => {
                setChatBarMicVisual('idle', '');
            }, 320);
        } else {
            setChatBarMicVisual('idle', '');
        }
    }

    // Engine B Stop: Only resets 3D Golden Orb & mini-orb voice capture
    function stopOrbVoice(silent) {
        clearOrbRestartTimer();
        orbSessionId += 1;
        orbCarryBuffer = '';
        if (orbRec) {
            try {
                orbRec.onresult = null;
                orbRec.onerror = null;
                orbRec.onend = null;
                orbRec.abort();
            } catch (e) {}
            orbRec = null;
        }
        isOrbListening = false;
        if (!silent && !isOrbSpeaking && !isOrbThinking) {
            updateMiniOrbsUI('idle', isVoiceCallActive ? 'Live Call · Reconnecting mic...' : 'Tap orb to talk with SRI');
        }
    }

    function endVoiceCall(reasonText) {
        clearMicSwitchTimer();
        if (orbThinkingSafetyTimer) {
            clearTimeout(orbThinkingSafetyTimer);
            orbThinkingSafetyTimer = null;
        }
        isVoiceCallActive = false;
        sessionStorage.removeItem(CALL_ACTIVE_KEY);
        stopOrbVoice(true);
        stopSpeaking(false);
        const hint = document.getElementById('orbHint');
        if (hint) {
            hint.classList.remove('listening', 'thinking', 'speaking');
            hint.textContent = reasonText || 'Tap the golden sphere to start continuous voice call';
        }
        updateMiniOrbsUI('idle', 'Tap orb to start voice call');
        syncVoiceCallDockUI('idle', '');
    }

    // Engine A: Bottom Chat Dictation Mic (continuous auto-keepalive + 0ms fast interim typing)
    function toggleChatDictation() {
        clearMicSwitchTimer();
        clearDictationRestartTimer();
        // Strictly stop any active Orb call/TTS before starting chat dictation
        const orbWasRunning = isVoiceCallActive || isOrbListening || orbRec !== null || isOrbSpeaking;
        if (orbWasRunning) {
            endVoiceCall('Chat mic active — tap sphere to call SRI');
        }

        if (isDictating) {
            stopChatDictation(true);
            return;
        }

        const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
        const inputEl = document.getElementById('promptInput');
        if (!SpeechRec) {
            if (inputEl) {
                inputEl.placeholder = 'Speech API unavailable — type your message...';
                inputEl.focus();
            }
            return;
        }

        isDictating = true;
        const mySession = ++dictationSessionId;
        dictationCarryPrefix = inputEl && inputEl.value.trim() ? inputEl.value.trim() + ' ' : '';

        const launchDictationInstance = () => {
            if (!isDictating || mySession !== dictationSessionId) return;
            if (dictationRec) {
                try {
                    dictationRec.onresult = null;
                    dictationRec.onerror = null;
                    dictationRec.onend = null;
                    dictationRec.abort();
                } catch (e) {}
                dictationRec = null;
            }

            const rec = new SpeechRec();
            dictationRec = rec;
            const activeLang = LANG_MODES[langIdx] || LANG_MODES[0];
            rec.lang = activeLang.code || 'ta-IN';
            rec.continuous = true;
            rec.interimResults = true;
            rec.maxAlternatives = 3;

            setChatBarMicVisual('recording', activeLang.short);

            let latestSessionCombined = '';

            rec.onresult = (e) => {
                if (mySession !== dictationSessionId || !isDictating) return;
                let finalPart = '';
                let interimPart = '';
                const results = e && e.results ? e.results : [];
                for (let i = 0; i < results.length; i++) {
                    const item = results[i];
                    if (!item) continue;
                    const txt = pickBestTranscript(item, rec.lang);
                    if (!txt) continue;
                    if (item.isFinal) {
                        finalPart += txt + ' ';
                    } else {
                        interimPart += txt + ' ';
                    }
                }
                latestSessionCombined = (finalPart + interimPart).trim();
                if (inputEl) {
                    const nextVal = (dictationCarryPrefix + finalPart + interimPart).replace(/\s+/g, ' ').trim();
                    if (inputEl.value !== nextVal) {
                        inputEl.value = nextVal;
                        inputEl.scrollTop = inputEl.scrollHeight;
                        schedulePromptResize();
                    }
                }
            };

            rec.onerror = (err) => {
                if (mySession !== dictationSessionId) return;
                const code = err && err.error ? String(err.error) : '';
                if (code === 'not-allowed' || code === 'service-not-allowed') {
                    stopChatDictation(false);
                }
            };

            rec.onend = () => {
                if (mySession !== dictationSessionId) return;
                dictationRec = null;
                if (!isDictating) return;
                if (latestSessionCombined) {
                    dictationCarryPrefix = (dictationCarryPrefix + latestSessionCombined + ' ').replace(/\s+/g, ' ');
                }
                // Keep chat dictation continuously active across browser silence timeouts until user stops
                dictationRestartTimer = setTimeout(launchDictationInstance, 50);
            };

            try {
                rec.start();
            } catch (err) {
                stopChatDictation(false);
            }
        };

        if (orbWasRunning) {
            micSwitchTimer = setTimeout(launchDictationInstance, 70);
        } else {
            launchDictationInstance();
        }
    }

    // Engine B: Continuous Non-Stop Walkie-Talkie Voice Call Listener (No early single-word cut-off)
    function startOrbContinuousListener(carryText) {
        clearOrbRestartTimer();
        if (!isVoiceCallActive || isOrbSpeaking || isOrbThinking) return;

        const hint = document.getElementById('orbHint');
        const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (!SpeechRec) {
            endVoiceCall('Voice API unavailable — type in the chat bar below');
            return;
        }

        const preservedCarry = typeof carryText === 'string' ? carryText.trim() : '';
        stopOrbVoice(true);
        orbCarryBuffer = preservedCarry;
        const mySession = ++orbSessionId;
        const rec = new SpeechRec();
        orbRec = rec;
        isOrbListening = true;

        const activeLang = LANG_MODES[langIdx] || LANG_MODES[0];
        rec.lang = activeLang.code || 'ta-IN';
        rec.continuous = true;
        rec.interimResults = true;
        rec.maxAlternatives = 3;

        hint.classList.remove('speaking', 'thinking');
        hint.classList.add('listening');
        hint.textContent = orbCarryBuffer
            ? ('🎙️ ' + orbCarryBuffer)
            : ('Live Call (' + activeLang.label + ') — Speak continuously...');
        updateMiniOrbsUI('listening', orbCarryBuffer || ('Live Call (' + activeLang.short + ') · Listening...'));
        syncVoiceCallDockUI('listening', orbCarryBuffer ? ('🎙️ ' + orbCarryBuffer) : ('Live Call (' + activeLang.short + ') · Listening...'));

        let orbDispatched = false;
        let consumedOffset = 0;
        let latestActiveAll = orbCarryBuffer;
        let latestActiveFinal = '';

        const handleContinuousUtterance = (rawText) => {
            const toSend = (rawText || '').trim();
            if (!toSend || orbDispatched || !isVoiceCallActive) return;

            if (isStopVoiceCommand(toSend)) {
                endVoiceCall('Voice call ended');
                return;
            }

            const voiceIntent = detectVoiceNavigationIntent(toSend, '', STATE.workspaceFile);
            const effectivePage = voiceIntent.page || 'research';
            const effectiveTab = voiceIntent.tab || null;

            sessionStorage.setItem('sri_pending_voice_page', effectivePage);
            if (effectiveTab) {
                sessionStorage.setItem('sri_pending_voice_tab', effectiveTab);
            } else {
                sessionStorage.removeItem('sri_pending_voice_tab');
            }
            applySeamlessVoiceNavigation(effectivePage, effectiveTab);

            if (voiceIntent.pureNav && voiceIntent.page) {
                const pageTitle = voiceIntent.page === 'research'
                    ? 'Research'
                    : (voiceIntent.page === 'project' ? (voiceIntent.tab === 'code' ? 'Code' : 'Preview') : 'Hub');
                if (hint) hint.textContent = 'Opened ' + pageTitle + ' · Continuous call active';
                updateMiniOrbsUI('listening', 'Opened ' + pageTitle + ' · Listening...');
                syncVoiceCallDockUI('listening', 'Opened ' + pageTitle + ' · Keep speaking...');
                if (isVoiceCallActive && !isOrbListening && !isOrbSpeaking && !isOrbThinking) {
                    orbRestartTimer = setTimeout(() => startOrbContinuousListener(''), 60);
                }
                return;
            }

            if (effectivePage === 'research') {
                showOptimisticResearchLoading(toSend);
            }

            orbDispatched = true;
            orbCarryBuffer = '';
            latestActiveAll = '';
            latestActiveFinal = '';
            stopOrbVoice(true);
            if (hint) hint.classList.remove('listening');
            appendOptimisticMessage('user', toSend);
            sendToPython(toSend, 'orb');
        };

        rec.onresult = (e) => {
            if (mySession !== orbSessionId || !isVoiceCallActive || isOrbSpeaking || Date.now() < speechCooldownUntil) return;
            let finalPart = '';
            let interimPart = '';
            const results = e && e.results ? e.results : [];
            for (let i = 0; i < results.length; i++) {
                const item = results[i];
                if (!item) continue;
                const txt = pickBestTranscript(item, rec.lang);
                if (!txt) continue;
                if (item.isFinal) {
                    finalPart += txt + ' ';
                } else {
                    interimPart += txt + ' ';
                }
            }

            const basePrefix = orbCarryBuffer ? orbCarryBuffer + ' ' : '';
            const fullCombined = (basePrefix + finalPart + interimPart);
            const fullFinalOnly = (basePrefix + finalPart);
            const activeAll = fullCombined.slice(consumedOffset).trim();
            const activeFinal = fullFinalOnly.slice(consumedOffset).trim();
            const hasInterim = interimPart.trim().length > 0;

            latestActiveAll = activeAll;
            latestActiveFinal = activeFinal;

            if (orbUtteranceCommitTimer) {
                clearTimeout(orbUtteranceCommitTimer);
                orbUtteranceCommitTimer = null;
            }

            // Instant 0ms fast UI transcription update while Kirubha speaks
            if (activeAll) {
                if (hint) hint.textContent = '🎙️ ' + activeAll;
                updateMiniOrbsUI('listening', activeAll);
                syncVoiceCallDockUI('listening', '🎙️ ' + activeAll);
            }

            if (isStopVoiceCommand(activeAll)) {
                handleContinuousUtterance(activeAll);
                return;
            }

            if (activeFinal && !hasInterim) {
                const quickIntent = detectVoiceNavigationIntent(activeFinal, '', STATE.workspaceFile);
                if (quickIntent.pureNav && quickIntent.page) {
                    consumedOffset = fullFinalOnly.length;
                    latestActiveAll = '';
                    latestActiveFinal = '';
                    orbCarryBuffer = '';
                    handleContinuousUtterance(activeFinal);
                    return;
                }

                // Responsive natural pause detection: keep 1-2 word thoughts open while dispatching fluent phrases swiftly
                const wordCount = activeFinal.split(/\s+/).filter(Boolean).length;
                const pauseWindowMs = wordCount <= 2 ? 780 : 460;
                const snapshotOffset = fullFinalOnly.length;
                const snapshotText = activeFinal;
                orbUtteranceCommitTimer = setTimeout(() => {
                    orbUtteranceCommitTimer = null;
                    if (mySession !== orbSessionId || orbDispatched || !isVoiceCallActive || isOrbSpeaking) return;
                    consumedOffset = snapshotOffset;
                    latestActiveAll = '';
                    latestActiveFinal = '';
                    handleContinuousUtterance(snapshotText);
                }, pauseWindowMs);
            }
        };

        rec.onerror = (err) => {
            if (mySession !== orbSessionId || orbDispatched) return;
            const errCode = err && err.error ? String(err.error) : '';
            if (errCode === 'not-allowed' || errCode === 'service-not-allowed') {
                endVoiceCall('Mic permission blocked — allow microphone access');
                return;
            }
            if (orbUtteranceCommitTimer) {
                clearTimeout(orbUtteranceCommitTimer);
                orbUtteranceCommitTimer = null;
            }
            isOrbListening = false;
            orbRec = null;
            if (isVoiceCallActive && !isOrbSpeaking && !isOrbThinking) {
                const preserve = latestActiveAll;
                orbRestartTimer = setTimeout(() => startOrbContinuousListener(preserve), 40);
            }
        };

        const scheduleCarriedCommitIfIdle = () => {
            if (!orbCarryBuffer || orbUtteranceCommitTimer) return;
            const carryWords = orbCarryBuffer.split(/\s+/).filter(Boolean).length;
            const carryPauseMs = carryWords <= 2 ? 780 : 460;
            const carrySnapshot = orbCarryBuffer;
            orbUtteranceCommitTimer = setTimeout(() => {
                orbUtteranceCommitTimer = null;
                if (mySession !== orbSessionId || orbDispatched || !isVoiceCallActive || isOrbSpeaking) return;
                orbCarryBuffer = '';
                latestActiveAll = '';
                latestActiveFinal = '';
                handleContinuousUtterance(carrySnapshot);
            }, carryPauseMs);
        };

        rec.onend = () => {
            if (mySession !== orbSessionId || orbDispatched) return;
            if (orbUtteranceCommitTimer) {
                clearTimeout(orbUtteranceCommitTimer);
                orbUtteranceCommitTimer = null;
            }
            isOrbListening = false;
            orbRec = null;
            if (!isVoiceCallActive || isOrbSpeaking || isOrbThinking) return;

            const pending = (latestActiveFinal || latestActiveAll || '').trim();
            if (pending) {
                if (isStopVoiceCommand(pending)) {
                    endVoiceCall('Voice call ended');
                    return;
                }
                const wordCount = pending.split(/\s+/).filter(Boolean).length;
                const quickNav = detectVoiceNavigationIntent(pending, '', STATE.workspaceFile);
                if ((quickNav.pureNav && quickNav.page) || (latestActiveFinal && wordCount >= 2)) {
                    handleContinuousUtterance(pending);
                    if (quickNav.pureNav && isVoiceCallActive && !isOrbListening && !orbDispatched) {
                        orbRestartTimer = setTimeout(() => startOrbContinuousListener(''), 25);
                    }
                    return;
                }
                // Preserve brief 1-word or unfinalized fragment transparently across seamless auto-restart
                orbRestartTimer = setTimeout(() => startOrbContinuousListener(pending), 25);
                return;
            }
            orbRestartTimer = setTimeout(() => startOrbContinuousListener(''), 30);
        };

        try {
            rec.start();
            scheduleCarriedCommitIfIdle();
        } catch (err) {
            isOrbListening = false;
            orbRec = null;
            if (isVoiceCallActive) {
                orbRestartTimer = setTimeout(() => startOrbContinuousListener(orbCarryBuffer), 160);
            }
        }
    }

    // Engine B Gesture Router:
    //   - Idle: Single tap starts non-stop Walkie-Talkie call immediately
    //   - Active Call:
    //       * Double-Tap (<= 350ms) -> Ends/disconnects voice call cleanly
    //       * Single-Tap -> Navigates back to previous/home page while keeping call ON
    let orbTapTimer = null;
    let lastOrbTapAt = 0;
    const DOUBLE_TAP_MS = 350;

    function handleSingleTapDuringCall() {
        if (!isVoiceCallActive) return;
        if (isOrbSpeaking) {
            // Barge-in if SRI is currently speaking, then return to previous/home page & resume listening
            stopSpeaking(true);
            navigateBackOrHome();
            if (!isOrbListening && !isOrbThinking) {
                micSwitchTimer = setTimeout(startOrbContinuousListener, 60);
            }
            return;
        }
        navigateBackOrHome();
        if (!isOrbListening && !isOrbThinking) {
            micSwitchTimer = setTimeout(startOrbContinuousListener, 80);
        }
    }

    function handleOrbGestureTap() {
        clearMicSwitchTimer();
        const dictationWasRunning = isDictating || dictationRec !== null;
        if (dictationWasRunning) {
            stopChatDictation(false);
        }

        if (!isVoiceCallActive) {
            if (orbTapTimer) {
                clearTimeout(orbTapTimer);
                orbTapTimer = null;
            }
            lastOrbTapAt = 0;
            try {
                if (window.speechSynthesis) {
                    const prime = new SpeechSynthesisUtterance('');
                    prime.volume = 0;
                    window.speechSynthesis.speak(prime);
                }
            } catch (e) {}
            isVoiceCallActive = true;
            isOrbThinking = false;
            speechCooldownUntil = 0;
            sessionStorage.setItem(CALL_ACTIVE_KEY, '1');
            syncVoiceCallDockUI('listening', 'Starting continuous call...');
            if (dictationWasRunning) {
                micSwitchTimer = setTimeout(startOrbContinuousListener, 70);
            } else {
                startOrbContinuousListener();
            }
            return;
        }

        const now = Date.now();
        if (orbTapTimer && (now - lastOrbTapAt) <= DOUBLE_TAP_MS) {
            clearTimeout(orbTapTimer);
            orbTapTimer = null;
            lastOrbTapAt = 0;
            endVoiceCall('Voice call ended (double-tap)');
            return;
        }

        lastOrbTapAt = now;
        if (orbTapTimer) {
            clearTimeout(orbTapTimer);
        }
        orbTapTimer = setTimeout(() => {
            orbTapTimer = null;
            lastOrbTapAt = 0;
            handleSingleTapDuringCall();
        }, DOUBLE_TAP_MS);
    }

    function handleOrbTap() {
        handleOrbGestureTap();
    }

    function stopSpeaking(keepIdle) {
        const audioEl = document.getElementById('sriNeuralAudio');
        if (audioEl) {
            audioEl.onended = null;
            audioEl.onerror = null;
            if (typeof audioEl.pause === 'function') {
                audioEl.pause();
            }
            audioEl.currentTime = 0;
        }
        if (window.speechSynthesis) {
            window.speechSynthesis.cancel();
        }
        isOrbSpeaking = false;
        isOrbThinking = false;
        speechCooldownUntil = Date.now() + 220;
        document.getElementById('orbHint').classList.remove('speaking', 'thinking');
        if (!keepIdle && !isVoiceCallActive) {
            updateMiniOrbsUI('idle', 'Tap orb to talk with SRI');
        }
    }

    function playAgentVoiceReply(text, audioB64) {
        if (!text) return;
        stopChatDictation(false);
        stopOrbVoice(true);
        stopSpeaking(true);
        if (orbThinkingSafetyTimer) {
            clearTimeout(orbThinkingSafetyTimer);
            orbThinkingSafetyTimer = null;
        }
        isOrbThinking = false;
        isOrbSpeaking = true;

        try {
            const replyIntent = detectVoiceNavigationIntent(STATE.lastUserQuery, text, STATE.workspaceFile);
            const navPage = STATE.targetPage || replyIntent.page;
            const navTab = STATE.targetTab || replyIntent.tab;
            if (navPage) {
                applySeamlessVoiceNavigation(navPage, navTab);
            }
        } catch (navErr) {}

        const hint = document.getElementById('orbHint');
        if (hint) {
            hint.classList.remove('listening', 'thinking');
            hint.classList.add('speaking');
            hint.textContent = 'SRI: ' + text;
        }
        updateMiniOrbsUI('speaking', '🔊 ' + text);
        syncVoiceCallDockUI('speaking', '🔊 ' + text);

        let replyFinished = false;
        let speakWatchdog = null;
        const onFinishSpeaking = () => {
            if (replyFinished) return;
            replyFinished = true;
            if (speakWatchdog) {
                clearTimeout(speakWatchdog);
                speakWatchdog = null;
            }
            isOrbSpeaking = false;
            speechCooldownUntil = Date.now() + 60;
            if (hint) hint.classList.remove('speaking');
            if (isVoiceCallActive) {
                syncVoiceCallDockUI('listening', 'Live Call · Listening...');
                if (hint) {
                    hint.classList.add('listening');
                    hint.textContent = 'Live Call — Listening...';
                }
                orbRestartTimer = setTimeout(() => {
                    if (isVoiceCallActive && !isOrbSpeaking && !isOrbThinking) {
                        startOrbContinuousListener();
                    }
                }, 45);
            } else {
                if (hint) hint.textContent = 'Tap the golden sphere to talk with SRI in Tamil or English';
                updateMiniOrbsUI('idle', 'Tap orb to talk with SRI');
            }
        };

        // Safety watchdog ensures voice call loop never hangs if browser TTS suppresses onend
        const estDurationMs = Math.min(20000, Math.max(3800, text.length * 75));
        speakWatchdog = setTimeout(onFinishSpeaking, estDurationMs);

        if (audioB64 && audioB64.length > 100) {
            const audioEl = document.getElementById('sriNeuralAudio');
            if (audioEl) {
                audioEl.src = 'data:audio/mp3;base64,' + audioB64;
                audioEl.onended = onFinishSpeaking;
                audioEl.onerror = () => speakBrowserFallback(text, onFinishSpeaking);
                audioEl.play().catch(() => speakBrowserFallback(text, onFinishSpeaking));
                return;
            }
        }
        speakBrowserFallback(text, onFinishSpeaking);
    }

    function speakBrowserFallback(text, onDone) {
        const doneFn = typeof onDone === 'function' ? onDone : () => {};
        try {
            if (!window.speechSynthesis) { doneFn(); return; }
            try { window.speechSynthesis.cancel(); } catch (e) {}
            const utter = new SpeechSynthesisUtterance(text);
            let targetLang = (LANG_MODES[langIdx] && LANG_MODES[langIdx].code) || 'ta-IN';
            if (/[\u0B80-\u0BFF]/.test(text)) targetLang = 'ta-IN';
            else if (/[\u0900-\u097F]/.test(text)) targetLang = 'hi-IN';
            else if (/[\u0C00-\u0C7F]/.test(text)) targetLang = 'te-IN';
            else if (/[\u0D00-\u0D7F]/.test(text)) targetLang = 'ml-IN';
            else if (/[\u0C80-\u0CFF]/.test(text)) targetLang = 'kn-IN';

            utter.lang = targetLang;
            if (!cachedVoices.length) loadCachedVoices();
            const voices = cachedVoices.length
                ? cachedVoices
                : (window.speechSynthesis.getVoices ? window.speechSynthesis.getVoices() : []);
            const langPrefix = targetLang.split('-')[0].toLowerCase();
            const matchedVoice =
                voices.find((v) => v.lang && v.lang.toLowerCase() === targetLang.toLowerCase()) ||
                voices.find((v) => v.lang && v.lang.toLowerCase().startsWith(langPrefix)) ||
                (targetLang === 'ta-IN'
                    ? voices.find((v) => /tamil/i.test(v.name || ''))
                    : null);
            if (matchedVoice) {
                utter.voice = matchedVoice;
            }
            utter.rate = 1.06;
            let started = false;
            let finished = false;
            const finishOnce = () => {
                if (finished) return;
                finished = true;
                doneFn();
            };
            utter.onstart = () => { started = true; };
            utter.onend = finishOnce;
            utter.onerror = finishOnce;
            try {
                window.speechSynthesis.speak(utter);
                setTimeout(() => {
                    if (!finished && !started && !window.speechSynthesis.speaking && !window.speechSynthesis.pending) {
                        finishOnce();
                    }
                }, 420);
            } catch (e) {
                finishOnce();
            }
        } catch (ttsErr) {
            doneFn();
        }
    }

    // Only auto-speak when triggered from the Golden Orb voice channel — NEVER on chat box dictation/text submits, and NEVER loop on reload
    const lastInputChannel = sessionStorage.getItem('sri_input_channel');
    let startedPlaybackFromOrb = false;
    if (STATE.shouldSpeak && STATE.spokenText && lastInputChannel === 'orb') {
        const replyKey = String(STATE.turnId || STATE.spokenText);
        if (sessionStorage.getItem('sri_last_played_turn') !== replyKey) {
            sessionStorage.setItem('sri_last_played_turn', replyKey);
            sessionStorage.removeItem('sri_input_channel');
            startedPlaybackFromOrb = true;
            playAgentVoiceReply(STATE.spokenText, STATE.audioBase64);
        }
    } else if (lastInputChannel === 'chat') {
        sessionStorage.removeItem('sri_input_channel');
    }

    if (isVoiceCallActive) {
        syncVoiceCallDockUI(startedPlaybackFromOrb ? 'speaking' : 'listening', startedPlaybackFromOrb ? '🔊 Speaking...' : 'Live Call · Listening...');
        if (!startedPlaybackFromOrb) {
            setTimeout(startOrbContinuousListener, 50);
        }
    }

    autoResizePromptInput();

    // Universal Smooth Horizontal Touch & Pointer Swipe Navigation across ALL 6 Top Tabs, Preview/Code, & Workspace Files
    (function initHorizontalSwipeGestures() {
        const appShell = document.getElementById('appShell');
        const pagesTrack = document.getElementById('pagesTrack');
        const projViewport = document.getElementById('projectTabsViewport');
        const projTrack = document.getElementById('projectTabsTrack');
        const fileStrip = document.getElementById('projectFileStrip');

        if (fileStrip) {
            let fStart = null;
            fileStrip.addEventListener('touchstart', (e) => {
                if (e.touches.length === 1) {
                    e.stopPropagation();
                    fStart = { x: e.touches[0].clientX, y: e.touches[0].clientY };
                }
            }, { passive: true });
            fileStrip.addEventListener('touchend', (e) => {
                e.stopPropagation();
                if (!fStart || !e.changedTouches[0]) { fStart = null; return; }
                const dx = e.changedTouches[0].clientX - fStart.x;
                const dy = e.changedTouches[0].clientY - fStart.y;
                fStart = null;
                if (Math.abs(dx) >= 38 && Math.abs(dx) > Math.abs(dy) * 1.2) {
                    stepWorkspaceFile(dx < 0 ? 1 : -1);
                }
            }, { passive: true });
        }

        if (projViewport && projTrack) {
            let tabDragStart = null;
            let tabDragging = false;
            const tabOnStart = (x, y) => {
                tabDragStart = { x, y };
                tabDragging = false;
            };
            const tabOnMove = (x, y) => {
                if (!tabDragStart) return;
                const dx = x - tabDragStart.x;
                const dy = y - tabDragStart.y;
                if (!tabDragging) {
                    if (Math.abs(dy) > 20 && Math.abs(dy) > Math.abs(dx)) {
                        tabDragStart = null;
                        return;
                    }
                    if (Math.abs(dx) > 12 && Math.abs(dx) > Math.abs(dy) * 1.15) {
                        tabDragging = true;
                        projTrack.classList.add('no-anim');
                    } else {
                        return;
                    }
                }
                const base = currentProjectTab === 'code' ? -50 : 0;
                const clamped = Math.max(-130, Math.min(130, dx));
                projTrack.style.transform = `translate3d(calc(${base}% + ${clamped}px), 0, 0)`;
            };
            const tabOnEnd = (x, y) => {
                if (!tabDragStart) return;
                const dx = x - tabDragStart.x;
                const dy = y - tabDragStart.y;
                tabDragStart = null;
                projTrack.classList.remove('no-anim');
                if (tabDragging && Math.abs(dx) >= 44 && Math.abs(dx) > Math.abs(dy) * 1.15) {
                    if (dx < 0) {
                        if (currentProjectTab === 'preview') {
                            switchTab('code', false);
                        } else {
                            setMobilePage('tracker', false);
                        }
                    } else {
                        if (currentProjectTab === 'code') {
                            switchTab('preview', false);
                        } else {
                            setMobilePage('research', false);
                        }
                    }
                } else {
                    switchTab(currentProjectTab, false);
                }
                tabDragging = false;
            };

            projViewport.addEventListener('touchstart', (e) => {
                if (e.touches.length === 1) {
                    e.stopPropagation();
                    tabOnStart(e.touches[0].clientX, e.touches[0].clientY);
                }
            }, { passive: true });
            projViewport.addEventListener('touchmove', (e) => {
                if (e.touches.length === 1 && tabDragStart) {
                    e.stopPropagation();
                    tabOnMove(e.touches[0].clientX, e.touches[0].clientY);
                }
            }, { passive: true });
            projViewport.addEventListener('touchend', (e) => {
                if (e.changedTouches[0] && tabDragStart) {
                    e.stopPropagation();
                    tabOnEnd(e.changedTouches[0].clientX, e.changedTouches[0].clientY);
                }
            }, { passive: true });

            [document.getElementById('paneCode'), document.getElementById('previewSwipeLeftEdge'), document.getElementById('previewSwipeRightEdge'), document.getElementById('projectSwipeBar')].forEach((el) => {
                if (!el) return;
                el.addEventListener('mousedown', (e) => {
                    if (e.button === 0) tabOnStart(e.clientX, e.clientY);
                });
            });
            window.addEventListener('mousemove', (e) => {
                if (tabDragStart) tabOnMove(e.clientX, e.clientY);
            });
            window.addEventListener('mouseup', (e) => {
                if (tabDragStart) tabOnEnd(e.clientX, e.clientY);
            });
        }

        if (appShell && pagesTrack) {
            let pageDragStart = null;
            let pageDragging = false;
            const unitPct = 100 / PAGE_ORDER.length;
            const canSwipeShell = (tgt) => {
                if (!tgt || !tgt.closest) return true;
                if (tgt.closest('#projectTabsViewport, #projectFileStrip, textarea, input, select')) return false;
                return true;
            };
            const onShellStart = (x, y, tgt) => {
                if (!canSwipeShell(tgt)) return;
                pageDragStart = { x, y };
                pageDragging = false;
            };
            const onShellMove = (x, y) => {
                if (!pageDragStart) return;
                const dx = x - pageDragStart.x;
                const dy = y - pageDragStart.y;
                if (!pageDragging) {
                    if (Math.abs(dy) > 20 && Math.abs(dy) > Math.abs(dx)) {
                        pageDragStart = null;
                        return;
                    }
                    if (Math.abs(dx) > 14 && Math.abs(dx) > Math.abs(dy) * 1.2) {
                        pageDragging = true;
                        pagesTrack.classList.add('no-anim');
                    } else {
                        return;
                    }
                }
                const curIdx = Math.max(0, PAGE_ORDER.indexOf(currentActivePage));
                const clamped = Math.max(-140, Math.min(140, dx));
                pagesTrack.style.transform = `translate3d(calc(-${curIdx * unitPct}% + ${clamped}px), 0, 0)`;
            };
            const onShellEnd = (x, y) => {
                if (!pageDragStart) return;
                const dx = x - pageDragStart.x;
                const dy = y - pageDragStart.y;
                pageDragStart = null;
                pagesTrack.classList.remove('no-anim');
                const curIdx = Math.max(0, PAGE_ORDER.indexOf(currentActivePage));
                if (pageDragging && Math.abs(dx) >= 46 && Math.abs(dx) > Math.abs(dy) * 1.2) {
                    const nextIdx = dx < 0 ? Math.min(PAGE_ORDER.length - 1, curIdx + 1) : Math.max(0, curIdx - 1);
                    setMobilePage(PAGE_ORDER[nextIdx], false);
                } else {
                    setMobilePage(PAGE_ORDER[curIdx], false);
                }
                pageDragging = false;
            };

            appShell.addEventListener('touchstart', (e) => {
                if (e.touches.length === 1) onShellStart(e.touches[0].clientX, e.touches[0].clientY, e.target);
            }, { passive: true });
            appShell.addEventListener('touchmove', (e) => {
                if (e.touches.length === 1) onShellMove(e.touches[0].clientX, e.touches[0].clientY);
            }, { passive: true });
            appShell.addEventListener('touchend', (e) => {
                if (e.changedTouches && e.changedTouches[0]) onShellEnd(e.changedTouches[0].clientX, e.changedTouches[0].clientY);
            }, { passive: true });

            // Enable pointer drag swipe across top header nav & bottom dock on desktop too
            [document.getElementById('topMenuBar'), document.querySelector('.mob-nav')].forEach((navEl) => {
                if (!navEl) return;
                navEl.addEventListener('mousedown', (e) => {
                    if (e.button === 0) onShellStart(e.clientX, e.clientY, e.target);
                });
            });
            window.addEventListener('mousemove', (e) => {
                if (pageDragStart) onShellMove(e.clientX, e.clientY);
            });
            window.addEventListener('mouseup', (e) => {
                if (pageDragStart) onShellEnd(e.clientX, e.clientY);
            });
        }
    })();

    // 3D Golden Sphere & 17 Sine Waves (Reacts ONLY to Orb listening/thinking/speaking — isolated from chat dictation)
    const canvas = document.getElementById('sriOrb');
    const ctx = canvas ? canvas.getContext('2d') : null;
    if (!canvas || !ctx) {
        // Safe early exit if canvas is unavailable
    } else {
    const dpr = window.devicePixelRatio || 1;
    let t = 0;

    const pts = Array.from({ length: 1000 }, () => {
        const u = Math.random();
        const v = Math.random();
        const th = 2 * Math.PI * u;
        const ph = Math.acos(2 * v - 1);
        return { th, ph, s: Math.random() * 1.4 + 0.35 };
    });

    function renderOrb() {
        const W = canvas.clientWidth || 360;
        const H = canvas.clientHeight || 165;
        if (canvas.width !== Math.round(W * dpr) || canvas.height !== Math.round(H * dpr)) {
            canvas.width = Math.round(W * dpr);
            canvas.height = Math.round(H * dpr);
            ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        }
        ctx.clearRect(0, 0, W, H);

        const R = Math.min(58, Math.max(40, H * 0.31));
        const cx = W / 2;
        const cy = H / 2;
        const orbActive = isVoiceCallActive || isOrbListening || isOrbThinking || isOrbSpeaking;
        t += orbActive ? (isOrbThinking ? 0.065 : 0.045) : 0.015;

        const glowColor = isOrbSpeaking
            ? 'rgba(16, 185, 129, 0.45)'
            : (isOrbThinking
                ? 'rgba(96, 165, 250, 0.45)'
                : ((isOrbListening || isVoiceCallActive) ? 'rgba(251, 191, 36, 0.52)' : 'rgba(245, 158, 11, 0.34)'));

        const g = ctx.createRadialGradient(cx, cy, 8, cx, cy, R * 1.65);
        g.addColorStop(0, glowColor);
        g.addColorStop(1, 'rgba(6,7,9,0)');
        ctx.fillStyle = g;
        ctx.fillRect(0, 0, W, H);

        for (let i = 0; i < 17; i++) {
            ctx.beginPath();
            const phase = i * 0.22;
            for (let x = 0; x <= W; x += 2) {
                const edgeFade = Math.sin((x / W) * Math.PI);
                const amp = orbActive ? (22 + i * 1.3) : (15 + i * 1.0);
                const y = cy + Math.sin(x * 0.018 + t * 1.3 + phase) * amp * edgeFade;
                if (x === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
            }
            const alpha = 0.06 + (i / 17) * 0.25;
            ctx.strokeStyle = isOrbSpeaking
                ? `rgba(52, 211, 153, ${alpha})`
                : `rgba(245, 158, 11, ${alpha})`;
            ctx.lineWidth = 1.05;
            ctx.stroke();
        }

        pts.forEach(p => {
            const th = p.th + t * 0.45;
            const rad = R * (0.9 + p.s * 0.06);
            const x3 = rad * Math.sin(p.ph) * Math.cos(th);
            const y3 = rad * Math.cos(p.ph);
            const z3 = rad * Math.sin(p.ph) * Math.sin(th);
            const a = (z3 + R) / (2 * R);
            ctx.beginPath();
            ctx.arc(cx + x3, cy + y3, p.s, 0, Math.PI * 2);
            ctx.fillStyle = isOrbSpeaking
                ? `rgba(52, 211, 153, ${0.16 + a * 0.84})`
                : `rgba(251, 191, 36, ${0.16 + a * 0.84})`;
            ctx.fill();
        });

        const sp = ctx.createRadialGradient(cx - R * 0.35, cy - R * 0.35, 2, cx - R * 0.35, cy - R * 0.35, R * 0.42);
        sp.addColorStop(0, 'rgba(255,251,235,0.88)');
        sp.addColorStop(1, 'rgba(245,158,11,0)');
        ctx.fillStyle = sp;
        ctx.beginPath();
        ctx.arc(cx - R * 0.35, cy - R * 0.35, R * 0.42, 0, Math.PI * 2);
        ctx.fill();

        ctx.save();
        ctx.translate(cx, cy);
        ctx.rotate(-0.42);
        ctx.beginPath();
        ctx.ellipse(0, 0, R * 1.38, R * 0.52, 0, 0, Math.PI * 2);
        ctx.strokeStyle = isOrbSpeaking ? 'rgba(110, 231, 183, 0.6)' : 'rgba(253, 230, 138, 0.55)';
        ctx.lineWidth = 1.2;
        ctx.stroke();
        ctx.restore();

        requestAnimationFrame(renderOrb);
    }
    renderOrb();
    }
</script>
</body>
</html>""".replace("__STATE_PAYLOAD__", state_payload)

    components.html(html_template, height=800, scrolling=False)
