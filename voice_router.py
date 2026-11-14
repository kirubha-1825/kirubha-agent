"""
voice_router.py - High-Precision Multilingual Voice & Command Router.
Parses Tamil, Tanglish, and English voice/text commands to detect:
1. force_antigravity: Explicit routing to Google Antigravity Agent
2. use_stitch_ai: Frontend UI/UX Design integration via Stitch AI
3. clean_task_prompt: Extracted semantic task instructions
4. project_folder: Safe slugified workspace target
"""

import re
import os
from typing import Dict, Any, List

# Patterns triggering explicit Google Antigravity Agent handoff
ANTIGRAVITY_TRIGGERS = [
    # Tamil phrases
    r"ஆன்டி\s*கிராவிட்டி\s*(?:உள்ள\s*போய்\s*செய்|ல\s*பண்ணு|போய்\s*செய்|செய்|இயக்கு)",
    r"ஆண்ட்ராய்டு(?:ல|ில்)?\s*(?:போய்\s*செய்|செய்|ரன்\s*பண்ணு)",
    r"ஆன்டி\s*கிராவிட்டி",
    r"ஆன்டிகிராவிட்டி",
    r"ஆண்டிகிராவிட்டி",
    r"ஆண்டிகிரேவிட்டி",
    r"ஆன்ட்ராய்டு",
    r"ஆண்ட்ராய்டு",
    # English & Tanglish phrases
    r"\buse\s+antigravity\b",
    r"\bantigravity[- ]?(?:ல\s*பண்ணு|இல்\s*செய்|workspace)\b",
    r"\bhand(?:ing)?\s*off\s*to\s*antigravity\b",
    r"\broute\s*to\s*antigravity\b",
    r"\brun\s*(?:in|on|with)\s*antigravity\b",
    r"\bforce\s*antigravity\b",
    r"\bantigravity\b",
    r"\bandroid\s*antigravity\b"
]

# Patterns triggering Stitch AI UI / Frontend design synthesis
STITCH_AI_TRIGGERS = [
    # Tamil phrases
    r"சுவிட்ச்\s*ஏஐ",
    r"சுவிட்ச்",
    r"ஸ்டிட்ச்\s*ஏஐ",
    r"ஸ்டிட்ச்",
    r"ஸ்டிச்",
    r"டிசைன்",
    r"வடிவமைப்பு",
    r"முன்பக்கம்",
    r"பக்கம்",
    r"முகப்பு",
    # English & Tanglish phrases
    r"\bstitch\s*ai\b",
    r"\bstitch\b",
    r"\bfrontend\b",
    r"\bfront-end\b",
    r"\bui\b",
    r"\bux\b",
    r"\bui/ux\b",
    r"\bdesign\b",
    r"\blanding\s*page\b",
    r"\bweb\s*page\b",
    r"\binterface\b",
    r"\bcomponent\b"
]

# Trigger phrases to strip out when extracting the pure task requirement
STRIP_COMMAND_PREFIXES = [
    r"^(?:ப்ளீஸ்|தயவுசெய்து|ஸ்ரீ|sri|hey\s*sri|please)\s*",
    r"^(?:ஆன்டி\s*கிராவிட்டி\s*(?:உள்ள\s*போய்\s*செய்|ல\s*பண்ணு|போய்\s*செய்|செய்)\s*(?:மற்றும்|அப்புறம்)?\s*)",
    r"^(?:ஆண்ட்ராய்டுல\s*போய்\s*செய்\s*)",
    r"^(?:use\s+antigravity\s*(?:to|and)?\s*)",
    r"^(?:run\s*in\s*antigravity\s*(?:to|and)?\s*)",
    r"^(?:using\s*stitch\s*ai\s*(?:to|and)?\s*)",
    r"^(?:சுவிட்ச்\s*ஏஐ\s*(?:வச்சு|பயன்படுத்தி)?\s*)",
    r"^(?:ஸ்டிட்ச்\s*ஏஐ\s*(?:வச்சு|பயன்படுத்தி)?\s*)"
]


def detect_antigravity_intent(raw_text: str) -> tuple[bool, List[str]]:
    """Detects whether voice/text explicitly commands Antigravity execution."""
    if not raw_text:
        return False, []
    
    text_lower = raw_text.lower().strip()
    matched = []
    for pattern in ANTIGRAVITY_TRIGGERS:
        if re.search(pattern, text_lower, re.IGNORECASE):
            matched.append(pattern)
            
    return len(matched) > 0, matched


def detect_stitch_ai_intent(raw_text: str) -> tuple[bool, List[str]]:
    """Detects whether voice/text requests Stitch AI UI/frontend design."""
    if not raw_text:
        return False, []
        
    text_lower = raw_text.lower().strip()
    matched = []
    for pattern in STITCH_AI_TRIGGERS:
        if re.search(pattern, text_lower, re.IGNORECASE):
            matched.append(pattern)
            
    return len(matched) > 0, matched


def clean_task_prompt(raw_text: str) -> str:
    """Removes meta-commands while preserving the core task instructions."""
    if not raw_text:
        return ""
    
    cleaned = raw_text.strip()
    for pattern in STRIP_COMMAND_PREFIXES:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE).strip()
    
    # If stripping emptied the text, restore original text to avoid losing context
    if not cleaned or len(cleaned) < 3:
        cleaned = raw_text.strip()
        
    return cleaned


def extract_project_folder(text: str, default_folder: str = "") -> str:
    """Extracts a semantic, clean folder name from prompt."""
    if default_folder and default_folder.strip():
        slug = re.sub(r'[^a-zA-Z0-9_\-]', '_', default_folder.strip()).strip('_')
        return slug or "project_workspace"
        
    combined = text.lower()
    
    # Keyword based quick heuristics
    if any(k in combined for k in ["student", "மாணவர்", "school", "learning", "படிப்பு"]):
        return "student_learning_hub"
    if any(k in combined for k in ["shop", "store", "commerce", "கடை", "விலை", "product"]):
        return "ecommerce_store"
    if any(k in combined for k in ["portfolio", "resume", "பயோ", "profile"]):
        return "portfolio_showcase"
    if any(k in combined for k in ["dashboard", "analytics", "தரவு", "chart", "metrics"]):
        return "analytics_dashboard"
    if any(k in combined for k in ["chat", "messaging", "செய்தி", "bot"]):
        return "chat_interface"
        
    words = re.findall(r'[a-zA-Z0-9]+', combined)
    stopwords = {
        'build', 'create', 'a', 'an', 'the', 'in', 'with', 'and', 'for', 'to', 'of',
        'single', 'file', 'page', 'responsive', 'modern', 'sleek', 'interactive',
        'application', 'app', 'html', 'css', 'js', 'full', 'make', 'generate', 'ui',
        'design', 'use', 'antigravity', 'stitch'
    }
    meaningful = [w for w in words if w not in stopwords and len(w) > 2]
    if meaningful:
        slug = "_".join(meaningful[:3])
    else:
        slug = "workspace_project"
    return slug[:32]


def parse_voice_command(text: str, default_folder: str = "") -> Dict[str, Any]:
    """
    Main Voice & Command Router Entry Point.
    Returns parsed dictionary with:
    - force_antigravity: bool
    - use_stitch_ai: bool
    - clean_task_prompt: str
    - project_folder: str
    - tier_target: 'TIER_2_ANTIGRAVITY' or 'TIER_1_CLOUD_LLM'
    """
    raw_str = (text or "").strip()
    force_antigravity, ag_matches = detect_antigravity_intent(raw_str)
    use_stitch_ai, stitch_matches = detect_stitch_ai_intent(raw_str)
    cleaned_prompt = clean_task_prompt(raw_str)
    project_folder = extract_project_folder(cleaned_prompt or raw_str, default_folder)

    tier_target = "TIER_2_ANTIGRAVITY" if force_antigravity else "TIER_1_CLOUD_LLM"
    
    triggers = []
    if force_antigravity:
        triggers.append(f"Antigravity Triggered ({len(ag_matches)} matches)")
    if use_stitch_ai:
        triggers.append(f"Stitch AI UI Design Triggered ({len(stitch_matches)} matches)")
        
    explanation = (
        f"Routing Decision: {tier_target}. "
        f"{'User explicitly requested Antigravity execution via voice note. ' if force_antigravity else 'Defaulting to Tier 1 Cloud LLM loop. '}"
        f"{'Stitch AI UI synthesis enabled.' if use_stitch_ai else 'Standard UI synthesis.'}"
    )

    return {
        "original_text": raw_str,
        "clean_task_prompt": cleaned_prompt,
        "force_antigravity": force_antigravity,
        "use_stitch_ai": use_stitch_ai,
        "project_folder": project_folder,
        "tier_target": tier_target,
        "matched_triggers": triggers,
        "explanation": explanation
    }


# ==============================================================================
# CRYSTAL-CLEAR NATURAL VOICE SYNTHESIS & PACING CONTROLLER
# ==============================================================================

def clean_text_for_natural_speech(text: str) -> str:
    """
    Cleans and conditions text for warm, human-like voice synthesis:
    - Expands contractions into smooth phonetic pronunciations
    - Strips code symbols, markdown asterisks, hashtags, backticks, emojis
    - Eliminates robotic phrasing and duplicate punctuation
    """
    if not text:
        return ""
    replacements = {
        "I'm": "I am", "i'm": "I am",
        "what's": "what is", "What's": "What is",
        "let's": "let us", "Let's": "Let us",
        "don't": "do not", "Don't": "Do not",
        "can't": "cannot", "Can't": "Cannot",
        "won't": "will not", "Won't": "Will not",
        "it's": "it is", "It's": "It is",
        "that's": "that is", "That's": "That is",
        "you're": "you are", "You're": "You are",
        "we're": "we are", "We're": "We are",
        "they're": "they are", "They're": "They are",
        "I've": "I have", "I'll": "I will", "I'd": "I would"
    }
    cleaned = text
    for k, v in replacements.items():
        cleaned = cleaned.replace(k, v)
    cleaned = re.sub(r"^SRI:\s*", "", cleaned.strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r"[*_`#~\[\](){}<>|\\]", " ", cleaned)
    cleaned = re.sub(r"['\"]", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def detect_speech_voice_profile(text: str) -> Dict[str, str]:
    """
    Selects warm regional neural voices for crystal-clear natural synthesis:
    - Tamil: ta-IN-PallaviNeural
    - English: en-IN-NeerjaNeural
    - Hindi: hi-IN-SwaraNeural
    """
    if re.search(r"[\u0B80-\u0BFF]", text):
        return {
            "lang": "ta-IN",
            "neural_voice": "ta-IN-PallaviNeural",
            "rate": "+0%",
            "pitch": "+0Hz",
            "pacing_style": "warm_conversational"
        }
    if re.search(r"[\u0900-\u097F]", text):
        return {
            "lang": "hi-IN",
            "neural_voice": "hi-IN-SwaraNeural",
            "rate": "+0%",
            "pitch": "+0Hz",
            "pacing_style": "warm_conversational"
        }
    return {
        "lang": "en-IN",
        "neural_voice": "en-IN-NeerjaNeural",
        "rate": "+0%",
        "pitch": "+0Hz",
        "pacing_style": "warm_conversational"
    }


def format_paced_voice_response(user_query: str, raw_response: str) -> str:
    """
    Contextual Response Pacing:
    - Casual queries / Greetings: Crisp, natural 1-2 sentence replies (under 28 words).
    - Mentoring, Hackathon ideas, Project discussions: Well-paced, structured, and thoughtful explanations (up to 3 articulate sentences, max 48 words).
    """
    clean_text = clean_text_for_natural_speech(raw_response)
    if not clean_text:
        return "Hey Kirubha! சொல்லுங்க, what's our next step?"

    q_lower = (user_query or "").lower().strip()
    is_complex_or_mentor = any(k in q_lower for k in [
        "hackathon", "ஹேக்கத்தான்", "mentor", "idea", "feature", "score",
        "win", "architecture", "flutter", "logic", "how", "why", "strategy",
        "student", "design", "explain", "improve", "code"
    ])

    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', clean_text) if s.strip()]

    if is_complex_or_mentor:
        # Structured, articulate, thoughtful (up to 3 sentences, max 48 words)
        max_sentences = 3
        max_words = 48
    else:
        # Casual query (crisp, natural 1-2 sentences, max 28 words)
        max_sentences = 2
        max_words = 28

    if len(sentences) > max_sentences:
        clean_text = " ".join(sentences[:max_sentences])

    words = clean_text.split()
    if len(words) > max_words:
        clean_text = " ".join(words[:max_words]) + "."

    return clean_text

