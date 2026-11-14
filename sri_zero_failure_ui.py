import streamlit as st
import streamlit.components.v1 as components
import json
import re
import asyncio
import base64
import io


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
    text = re.sub(r"[*_`#~\[\](){}<>|\\]", " ", text)
    text = re.sub(r"['\"]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _detect_neural_voice(text: str) -> str:
    if re.search(r"[\u0B80-\u0BFF]", text):
        return "ta-IN-PallaviNeural"
    if re.search(r"[\u0900-\u097F]", text):
        return "hi-IN-SwaraNeural"
    if re.search(r"[\u0C00-\u0C7F]", text):
        return "te-IN-ShrutiNeural"
    if re.search(r"[\u0D00-\u0D7F]", text):
        return "ml-IN-SobhanaNeural"
    return "en-IN-NeerjaNeural"


def _generate_edge_tts_base64(text: str) -> str:
    cleaned = _clean_text_for_speech(text)
    if not cleaned:
        return ""
    try:
        import importlib
        edge_tts = importlib.import_module("edge_tts")

        voice = _detect_neural_voice(cleaned)

        async def _synthesize():
            communicate = edge_tts.Communicate(cleaned, voice, rate="+2%", pitch="+0Hz")
            audio_stream = io.BytesIO()
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_stream.write(chunk["data"])
            return base64.b64encode(audio_stream.getvalue()).decode("utf-8")

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as pool:
                    return pool.submit(lambda: asyncio.run(_synthesize())).result(
                        timeout=6
                    )
            return loop.run_until_complete(_synthesize())
        except RuntimeError:
            return asyncio.run(_synthesize())
    except Exception:
        return ""


def _build_research_cards_html(reply_text: str, existing_html: str) -> str:
    if not reply_text:
        return (
            existing_html
            or "<div style='color:#9CA3AF;padding:24px;text-align:center;'>Live Workspace & Research Ready</div>"
        )
    lines = [ln.strip() for ln in reply_text.split("\n") if ln.strip()]
    cards_html = f"""
    <div style="font-family:'Inter',sans-serif;color:#F4F4F5;padding:6px;">
      <div style="background:linear-gradient(135deg,rgba(245,158,11,0.16),rgba(16,185,129,0.08));border:1px solid rgba(245,158,11,0.45);border-radius:14px;padding:14px;margin-bottom:12px;">
        <div style="font-size:11px;color:#F59E0B;font-weight:700;text-transform:uppercase;letter-spacing:0.6px;margin-bottom:6px;">✦ SRI Multi-Dimensional Research & Action Brief</div>
        <div style="font-size:13.5px;line-height:1.55;color:#FFFFFF;">{reply_text}</div>
      </div>
    """
    if len(lines) > 1:
        cards_html += "<div style='display:flex;flex-direction:column;gap:8px;margin-bottom:14px;'>"
        for idx, item in enumerate(lines[:5], 1):
            cards_html += f"""
            <div style="background:#0E1117;border:1px solid #222630;border-left:3px solid #F59E0B;border-radius:10px;padding:10px 12px;font-size:12.5px;color:#E5E7EB;">
              <strong style="color:#F59E0B;">Topic {idx}:</strong> {item}
            </div>
            """
        cards_html += "</div>"
    if existing_html:
        cards_html += f"<div style='margin-top:12px;border-top:1px solid #1E222B;padding-top:12px;'>{existing_html}</div>"
    cards_html += "</div>"
    return cards_html


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
        overflow: clip !important;
    }
    [data-testid="stToolbar"], [data-testid="stDecoration"], #MainMenu, footer,
    [data-testid="stHeader"], [data-testid="stToastContainer"], [data-testid="stToast"] {
        display: none !important;
    }
    .block-container {
        padding: 0 !important;
        margin: 0 !important;
        max-width: 100vw !important;
    }
        overflow: visible !important;
    [data-testid="stSidebar"] {
        background-color: #090B0E !important;
        border-left: 1px solid rgba(245, 158, 11, 0.35) !important;
        z-index: 99999 !important;
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

    latest_assistant_reply = voice_reply_text or ""
    if not latest_assistant_reply and chat_history:
        for msg in reversed(chat_history):
            if isinstance(msg, dict) and msg.get("role") in ("assistant", "ai", "sri"):
                latest_assistant_reply = str(msg.get("content", ""))
                break
            elif isinstance(msg, dict) and "agent" in msg:
                latest_assistant_reply = str(msg.get("agent", ""))
                break

    last_spoken_key = "_sri_last_spoken_text"
    should_speak = False
    audio_b64 = ""
    cleaned_reply = _clean_text_for_speech(latest_assistant_reply)

    if cleaned_reply and st.session_state.get(last_spoken_key) != cleaned_reply:
        st.session_state[last_spoken_key] = cleaned_reply
        should_speak = True
        audio_b64 = _generate_edge_tts_base64(cleaned_reply)

    rich_preview = _build_research_cards_html(
        latest_assistant_reply, generated_preview_html
    )

    state_payload = json.dumps(
        {
            "agentStatus": agent_status,
            "activeTasks": active_tasks,
            "completed": completed_tasks,
            "failed": failed_tasks,
            "workspaceFile": workspace_file,
            "code": generated_code
            or "<!-- SRI AI Workspace Ready -->\n<div class='card'>Waiting for prompt...</div>",
            "previewHtml": rich_preview,
            "messages": chat_history[-10:],
            "shouldSpeak": should_speak,
            "spokenText": cleaned_reply,
            "audioBase64": audio_b64,
            "historyLog": history_log or st.session_state.get("history_log", []),
        }
    )

    html_template = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Playfair+Display:wght@600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
  * {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
    -webkit-tap-highlight-color: transparent !important;
    outline: none !important;
    user-select: none;
  }
  html, body {
    background: #060709;
    color: #F4F4F5;
    font-family: 'Inter', sans-serif;
    width: 100vw;
    height: 100dvh;
    overflow: hidden;
    display: flex;
    flex-direction: column;
  }

  /* Top Header */
  .topbar {
    height: 52px;
    padding: 0 16px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-shrink: 0;
  }
  .brand {
    font-family: 'Playfair Display', serif;
    font-size: 22px;
    font-weight: 700;
    color: #F5E6C8;
  }
  .brand span { color: #F59E0B; }
  .right-controls { display: flex; align-items: center; gap: 8px; }

  .lang-pill {
    background: #111318;
    border: 1px solid rgba(245, 158, 11, 0.45);
    border-radius: 999px;
    padding: 4px 10px;
    font-size: 11px;
    color: #F59E0B;
    font-weight: 600;
    cursor: pointer;
  }
  .status-pill {
    background: #0B1312;
    border: 1px solid rgba(16, 185, 129, 0.35);
    border-radius: 999px;
    padding: 4px 10px;
    font-size: 11px;
    color: #34D399;
    display: flex;
    align-items: center;
    gap: 5px;
    font-weight: 500;
  }
  .dot-green {
    width: 6px; height: 6px; border-radius: 50%;
    background: #10B981; box-shadow: 0 0 8px #10B981;
  }
  .gear-btn {
    width: 34px; height: 34px;
    background: #111318;
    border: 1px solid #242832;
    color: #9CA3AF;
    border-radius: 50%;
    font-size: 15px;
    cursor: pointer;
    display: flex; align-items: center; justify-content: center;
  }

  /* Sub-header */
  .welcome-row {
    padding: 2px 16px 6px 16px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-shrink: 0;
  }
  .welcome-sub { color: #D97706; font-size: 12px; font-weight: 500; }
  .welcome-name { color: #FFFFFF; font-size: 22px; font-weight: 700; letter-spacing: -0.3px; }
  .latest-btn {
    background: rgba(245, 158, 11, 0.08);
    border: 1px solid rgba(245, 158, 11, 0.4);
    color: #D97706;
    border-radius: 999px;
    padding: 6px 14px;
    font-size: 11.5px;
    font-weight: 500;
    cursor: pointer;
  }

  /* Main Grid */
  .main-grid {
    flex: 1;
    display: grid;
    grid-template-columns: 270px 1fr 390px;
    gap: 18px;
    padding: 6px 20px;
    overflow: hidden;
    min-height: 0;
  }
  .left-col { display: flex; flex-direction: column; justify-content: space-between; }
  /* center-col: scrollable so inline-card stacks naturally below the orb */
  .center-col {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: flex-start;
    overflow-y: auto;
    overflow-x: hidden;
    min-height: 0;
    scrollbar-width: none;
  }
  .center-col::-webkit-scrollbar { display: none; }
  .stat-row {
    display: flex; justify-content: space-between; padding: 10px 0;
    border-bottom: 1px solid #181B22; font-size: 13.5px; color: #9CA3AF;
  }
  .gold-val { color: #F59E0B; font-weight: 600; }

  .orb-wrap {
    flex: 0 0 auto;
    width: 100%;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-height: 0;
  }
  canvas#sriOrb {
    width: 100%;
    height: 205px;
    cursor: pointer;
  }
  .orb-hint {
    font-size: 12px;
    color: #71717A;
    margin-top: 4px;
    text-align: center;
    padding: 0 12px;
  }
  .orb-hint.listening { color: #F59E0B; font-weight: 600; }
  .orb-hint.speaking { color: #10B981; font-weight: 600; }

  /* Action Pills */
  .pills-row {
    display: flex;
    flex-direction: row;
    flex-wrap: nowrap;
    gap: 8px;
    width: 100%;
    overflow-x: auto;
    padding: 4px 0;
    justify-content: center;
    scrollbar-width: none;
  }
  .pills-row::-webkit-scrollbar { display: none; }
  .pill-btn {
    flex: 0 0 auto;
    background: #0C0E12;
    border: 1px solid #222630;
    color: #D4D4D8;
    border-radius: 999px;
    padding: 6px 13px;
    font-size: 11.5px;
    cursor: pointer;
    white-space: nowrap;
  }
  .pill-btn:first-child {
    border-color: rgba(245, 158, 11, 0.55);
    color: #F59E0B;
  }

  /* Chat Bar (Mic -> Text -> Manual Send) */
  .chat-bar {
    width: 100%;
    background: #0C0E12;
    border: 1px solid #222630;
    border-radius: 999px;
    display: flex;
    align-items: center;
    padding: 4px 6px 4px 16px;
    gap: 8px;
    margin-top: 6px;
  }
  .chat-bar input {
    flex: 1;
    background: transparent;
    border: none;
    color: #FFF;
    font-size: 13.5px;
    user-select: text;
  }
  .wave-dots {
    display: none;
    align-items: center;
    gap: 3px;
    padding: 0 6px;
  }
  .wave-dots.active { display: flex; }
  .wave-dots span {
    width: 3px; height: 10px;
    background: #F59E0B; border-radius: 2px;
    animation: waveBounce 0.7s infinite ease-in-out;
  }
  .wave-dots span:nth-child(2) { animation-delay: 0.1s; height: 15px; }
  .wave-dots span:nth-child(3) { animation-delay: 0.2s; height: 8px; }
  .wave-dots span:nth-child(4) { animation-delay: 0.3s; height: 14px; }
  .wave-dots span:nth-child(5) { animation-delay: 0.4s; height: 9px; }
  @keyframes waveBounce {
    0%, 100% { transform: scaleY(0.5); opacity: 0.5; }
    50% { transform: scaleY(1.3); opacity: 1; }
  }

  .mic-inline {
    background: transparent;
    border: none;
    color: #9CA3AF;
    font-size: 16px;
    cursor: pointer;
    padding: 4px 6px;
  }
  .mic-inline.active { color: #F59E0B; }
  .send-circle {
    width: 32px; height: 32px;
    border-radius: 50%;
    background: #F59E0B;
    color: #060709;
    border: none;
    font-weight: 700;
    font-size: 14px;
    cursor: pointer;
    display: flex; align-items: center; justify-content: center;
  }

  /* Right Glass Panel (Research & Preview Page) */
  .right-col {
    background: #0A0C10;
    border: 1px solid rgba(245, 158, 11, 0.3);
    border-radius: 20px;
    padding: 14px;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    position: relative;
  }
  .seg-tabs {
    display: flex;
    background: #060709;
    border: 1px solid #1E222B;
    border-radius: 999px;
    padding: 3px;
    margin-bottom: 10px;
  }
  .seg-tab {
    flex: 1; text-align: center; padding: 6px 10px;
    border-radius: 999px; font-size: 12.5px; color: #9CA3AF;
    cursor: pointer;
  }
  .seg-tab.active {
    background: #141821; border: 1px solid #F59E0B; color: #FFF; font-weight: 600;
  }
  .workspace-pane {
    flex: 1; background: #060709; border: 1px solid #181B22;
    border-radius: 12px; overflow: auto; padding: 12px;
    padding-bottom: 72px;
    font-family: 'JetBrains Mono', monospace; font-size: 12px; color: #E5E7EB;
    user-select: text;
  }

  /* Floating Bottom Round Voice Orb inside Project/Research View */
  .floating-voice-dock {
    position: absolute;
    bottom: 14px;
    left: 16px;
    right: 16px;
    background: rgba(12, 14, 18, 0.94);
    border: 1px solid rgba(245, 158, 11, 0.55);
    border-radius: 999px;
    padding: 6px 12px 6px 8px;
    display: flex;
    align-items: center;
    gap: 10px;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.75);
    z-index: 50;
  }
  .mini-orb-btn {
    width: 40px;
    height: 40px;
    border-radius: 50%;
    background: radial-gradient(circle at 35% 35%, #FDE68A, #F59E0B 60%, #92400E);
    border: 2px solid #FEF3C7;
    box-shadow: 0 0 14px rgba(245, 158, 11, 0.65);
    cursor: pointer;
    flex-shrink: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 16px;
    animation: miniPulse 2s infinite ease-in-out;
  }
  .mini-orb-btn.speaking {
    background: radial-gradient(circle at 35% 35%, #A7F3D0, #10B981 60%, #065F46);
    border-color: #D1FAE5;
    box-shadow: 0 0 18px rgba(16, 185, 129, 0.8);
  }
  @keyframes miniPulse {
    0%, 100% { transform: scale(1); }
    50% { transform: scale(1.07); }
  }
  .dock-caption {
    flex: 1;
    font-size: 11.5px;
    color: #E5E7EB;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  /* Bottom 2-Pill Switcher */
  .mob-nav { display: none; }

  @media (max-width: 900px) {
    .main-grid {
      display: flex;
      flex-direction: column;
      padding: 2px 16px 4px 16px;
      max-width: 480px;
      margin: 0 auto;
      width: 100%;
      /* Ensure children stack naturally — no overflow clip that cuts content */
      overflow: visible;
      min-height: 0;
    }

    /* slide-inline-card: render in normal document flow,
       below the orb section, never overlapping the header */
    .slide-inline-card {
      position: relative !important;
      top: auto !important;
      left: auto !important;
      transform: none !important;
      margin-top: 10px;
      margin-bottom: 20px;
      width: 100%;
      box-sizing: border-box;
      z-index: 1;
      /* Smooth fade-in so the card feels native, not jarring */
      animation: cardSlideIn 0.25s ease-out both;
    }
    @keyframes cardSlideIn {
      from { opacity: 0; transform: translateY(8px); }
      to   { opacity: 1; transform: translateY(0);   }
    }

    .left-col { display: none !important; }
    .pills-row { justify-content: flex-start; }
    .right-col { display: none; flex: 1; }
    body.show-project .center-col { display: none; }
    body.show-project .right-col { display: flex; }

    /* center-col: allow it to grow to natural height on mobile */
    .center-col {
      justify-content: flex-start;
      overflow: visible;
    }
    .orb-wrap {
      flex: 0 0 auto;
    }

    .mob-nav {
      display: flex;
      justify-content: center;
      align-items: center;
      gap: 12px;
      padding: 8px 16px 64px 16px;
      flex-shrink: 0;
    }
    .mob-pill {
      padding: 9px 18px;
      border-radius: 999px;
      font-size: 12.5px;
      font-weight: 600;
      cursor: pointer;
      border: 1px solid #222630;
      background: #0C0E12;
      color: #9CA3AF;
      display: flex;
      align-items: center;
      gap: 6px;
    }
    .mob-pill.active {
      background: #F59E0B;
      color: #060709;
      border-color: #F59E0B;
    }
  }
</style>
</head>
<body>
  <div class="topbar">
    <div class="brand">SRI AI<span>.</span></div>
    <div class="right-controls">
      <button class="lang-pill" id="langBtn" onclick="cycleVoiceLang()">🌐 தமிழ் / EN</button>
      <div class="status-pill"><span class="dot-green"></span> 24/7 Active</div>
      <button class="gear-btn" onclick="openBackendSettings()">⚙️</button>
    </div>
  </div>

  <div class="welcome-row">
    <div>
      <div class="welcome-sub">Welcome</div>
      <div class="welcome-name">Kirubha</div>
    </div>
    <button class="latest-btn" onclick="setMobilePage('project')">Latest Work →</button>
  </div>

  <div class="main-grid">
    <div class="left-col">
      <div>
        <div style="font-family:'Playfair Display',serif;font-size:26px;color:#FFF;margin-bottom:14px;">Agent Live</div>
        <div class="stat-row"><span>Agent Status</span><span class="gold-val" id="stAgent">● SRI (Ready)</span></div>
        <div class="stat-row"><span>Active Tasks</span><span class="gold-val" id="stActive">0</span></div>
        <div class="stat-row"><span>Completed</span><span class="gold-val" id="stComp">0</span></div>
        <div class="stat-row"><span>Failed</span><span class="gold-val" id="stFail">0</span></div>
      </div>
      <div style="font-size:12px;color:#71717A;">Environment: <span style="color:#E5E7EB;">Streamlit Cloud workspace/</span></div>
    </div>

    <div class="center-col">
      <div class="orb-wrap">
        <canvas id="sriOrb" onclick="handleOrbTap()"></canvas>
        <div class="orb-hint" id="orbHint">Tap the golden sphere to talk with SRI in any language</div>
      </div>

      <div style="width:100%;">
        <div class="pills-row">
          <button class="pill-btn" onclick="sendToPython('Build Student Dashboard')">Student Dashboard</button>
          <button class="pill-btn" onclick="sendToPython('Build SaaS Auth')">SaaS Auth</button>
          <button class="pill-btn" onclick="sendToPython('Build Kanban Board')">Kanban Board</button>
          <button class="pill-btn" onclick="sendToPython('Refine login.html')">Refine login.html</button>
        </div>
        <div class="chat-bar">
          <input id="promptInput" type="text" placeholder="Message SRI (or tap mic to dictate task)..." onkeydown="if(event.key==='Enter') submitPrompt()">
          <div class="wave-dots" id="waveDots"><span></span><span></span><span></span><span></span><span></span></div>
          <button class="mic-inline" id="inlineMicBtn" onclick="startInlineDictation()" title="Voice to Text (Wait for Send)">🎙️</button>
          <button class="send-circle" onclick="submitPrompt()" title="Send Task">➤</button>
        </div>
      </div>
    </div>

    <div class="right-col">
      <div class="seg-tabs">
        <div class="seg-tab active" id="tabPreview" onclick="switchTab('preview')">Research & Preview</div>
        <div class="seg-tab" id="tabCode" onclick="switchTab('code')">Code</div>
        <div class="seg-tab" id="tabHistory" onclick="switchTab('history')">History</div>
      </div>
      <div style="font-size:11px;color:#71717A;margin-bottom:8px;font-family:'JetBrains Mono',monospace;" id="fileLabel">workspace/login.html</div>
      <div class="workspace-pane" id="panePreview"></div>
      <pre class="workspace-pane" id="paneCode" style="display:none;white-space:pre-wrap;"></pre>
      <div class="workspace-pane" id="paneHistory" style="display:none;overflow-y:auto;"></div>

      <!-- Bottom Round Floating Voice Orb on Research/Project Page -->
      <div class="floating-voice-dock" onclick="handleOrbTap()">
        <div class="mini-orb-btn" id="miniOrbBtn">🎙️</div>
        <div class="dock-caption" id="dockCaption">Tap round orb to discuss these topics with SRI...</div>
      </div>
    </div>
  </div>

  <div class="mob-nav">
    <div class="mob-pill active" id="navHub" onclick="setMobilePage('hub')">✦ Agent Hub</div>
    <div class="mob-pill" id="navProj" onclick="setMobilePage('project')">👁️ Project View</div>
  </div>

  <audio id="sriNeuralAudio" style="display:none;"></audio>

<script>
  const STATE = __STATE_PAYLOAD__;
  document.getElementById('stAgent').textContent = '● ' + STATE.agentStatus;
  document.getElementById('stActive').textContent = STATE.activeTasks;
  document.getElementById('stComp').textContent = STATE.completed;
  document.getElementById('stFail').textContent = STATE.failed;
  document.getElementById('fileLabel').textContent = STATE.workspaceFile;
  document.getElementById('panePreview').innerHTML = STATE.previewHtml;
  document.getElementById('paneCode').textContent = STATE.code;

  const histList = STATE.historyLog || [];

  // Type → accent colour map
  const TYPE_COLOR = { task: '#F59E0B', chat: '#10B981', voice: '#60A5FA', research: '#A78BFA' };
  const TYPE_ICON  = { task: '🛠️', chat: '💬', voice: '🎙️', research: '🔬' };

  function buildHistoryHtml(list) {
    if (!list || list.length === 0) {
      return '<div style="color:#71717A;padding:24px;text-align:center;font-size:12px;">📭 No history recorded yet.</div>';
    }
    return list.map(item => {
      const type  = item.type  || 'task';
      const color = TYPE_COLOR[type] || '#F59E0B';
      const icon  = TYPE_ICON[type]  || '📌';
      const badge = type.toUpperCase();
      const ts    = item.timestamp || item.iso || '';
      const task  = (item.task    || 'Prompt').replace(/</g,'&lt;').replace(/>/g,'&gt;');
      const det   = (item.details || '').replace(/</g,'&lt;').replace(/>/g,'&gt;');
      const shortDet = det.length > 200 ? det.slice(0, 197) + '…' : det;
      return `
        <div style="background:#0E1117;border:1px solid #1E222B;
            border-left:3px solid ${color};border-radius:10px;
            padding:10px 12px;margin-bottom:8px;">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:5px;">
            <span style="font-size:9px;color:${color};font-weight:700;
                letter-spacing:0.5px;text-transform:uppercase;">${icon} ${badge}</span>
            <span style="font-size:9px;color:#71717A;">⏱️ ${ts}</span>
          </div>
          <div style="font-weight:600;color:${color};font-size:12px;
              margin-bottom:4px;line-height:1.4;">${task}</div>
          <div style="color:#D1D5DB;font-size:11px;line-height:1.5;">${shortDet}</div>
        </div>`;
    }).join('');
  }

  // Render history panel (newest first — list arrives newest-first from Python)
  document.getElementById('paneHistory').innerHTML = buildHistoryHtml(histList);

  // Live client-side search inside the History pane
  (function setupHistSearch() {
    const pane = document.getElementById('paneHistory');
    // Inject a search bar above the pane entries
    const searchBar = document.createElement('div');
    searchBar.style.cssText = 'margin-bottom:8px;';
    searchBar.innerHTML = `
      <input id="histSearchInput" type="text" placeholder="🔍 Search history…"
        style="width:100%;background:#0C0E12;border:1px solid #222630;border-radius:8px;
               padding:6px 10px;color:#FFF;font-size:11.5px;outline:none;"
        oninput="filterHistory(this.value)">`;
    pane.parentNode.insertBefore(searchBar, pane);
  })();

  function filterHistory(q) {
    const lower = q.toLowerCase().trim();
    const filtered = !lower ? histList
      : histList.filter(e =>
          ((e.task||'')+(e.details||'')).toLowerCase().includes(lower));
    document.getElementById('paneHistory').innerHTML = buildHistoryHtml(filtered);
  }

  const LANG_MODES = [
    { code: 'ta-IN', label: '🌐 தமிழ்' },
    { code: 'en-IN', label: '🌐 English' },
    { code: 'hi-IN', label: '🌐 हिन्दी' }
  ];
  let langIdx = parseInt(localStorage.getItem('sri_lang_idx') || '0', 10);
  if (isNaN(langIdx) || langIdx >= LANG_MODES.length) langIdx = 0;

  function updateLangUI() {
    document.getElementById('langBtn').textContent = LANG_MODES[langIdx].label;
  }
  updateLangUI();

  function cycleVoiceLang() {
    langIdx = (langIdx + 1) % LANG_MODES.length;
    localStorage.setItem('sri_lang_idx', String(langIdx));
    updateLangUI();
    document.getElementById('orbHint').textContent = 'Language: ' + LANG_MODES[langIdx].label + ' — Tap sphere to speak';
  }

  function switchTab(mode) {
    document.getElementById('tabPreview').classList.toggle('active', mode === 'preview');
    document.getElementById('tabCode').classList.toggle('active', mode === 'code');
    document.getElementById('tabHistory').classList.toggle('active', mode === 'history');
    document.getElementById('panePreview').style.display = mode === 'preview' ? 'block' : 'none';
    document.getElementById('paneCode').style.display = mode === 'code' ? 'block' : 'none';
    document.getElementById('paneHistory').style.display = mode === 'history' ? 'block' : 'none';
  }

  function setMobilePage(page) {
    const isProj = page === 'project';
    document.body.classList.toggle('show-project', isProj);
    document.getElementById('navHub').classList.toggle('active', !isProj);
    document.getElementById('navProj').classList.toggle('active', isProj);
  }

  function openBackendSettings() {
    // On mobile/desktop: switch to Project View and open the History tab
    // so the user immediately sees the persistent history panel.
    setMobilePage('project');
    switchTab('history');
    // Also try to open the Streamlit sidebar (Control Drawer) for full settings
    try {
      const parentDoc = window.parent.document;
      const btn = parentDoc.querySelector('[data-testid="collapsedControl"] button, [data-testid="collapsedControl"], [data-testid="stSidebarCollapseButton"] button');
      if (btn) { btn.click(); }
    } catch (e) {}
  }

  function submitPrompt() {
    const inputEl = document.getElementById('promptInput');
    const val = inputEl.value.trim();
    if (!val) return;
    stopAllVoiceRecognition();
    sendToPython(val);
  }

  function sendToPython(command) {
    stopAllVoiceRecognition();
    try {
      const parentDoc = window.parent.document;
      const bridgeInput = parentDoc.querySelector('input[aria-label="sri_hidden_bridge"], input[placeholder="sri_hidden_bridge"], input[aria-label="sri_bridge_input"]');
      if (bridgeInput) {
        const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
        nativeSetter.call(bridgeInput, command);
        bridgeInput.dispatchEvent(new Event('input', { bubbles: true }));
        bridgeInput.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true }));
        return;
      }
    } catch (e) {}
    const url = new URL(window.parent.location.href);
    url.searchParams.set('sri_cmd', command);
    url.searchParams.set('ts', Date.now());
    window.parent.history.replaceState({}, '', url);
    window.parent.location.reload();
  }

  let activeRec = null;
  let isListening = false;
  let isSpeaking = false;

  function stopAllVoiceRecognition() {
    if (activeRec) {
      try { activeRec.onend = null; activeRec.abort(); } catch (e) {}
      activeRec = null;
    }
    isListening = false;
    document.getElementById('waveDots').classList.remove('active');
    document.getElementById('inlineMicBtn').classList.remove('active');
    document.getElementById('orbHint').classList.remove('listening');
  }

  // 1. BOTTOM CHAT MIC: Converts Speech -> Text inside Input Box ONLY. Waits for user to tap Send (➤)!
  function startInlineDictation() {
    if (isSpeaking) stopSpeaking();
    if (isListening) {
      stopAllVoiceRecognition();
      document.getElementById('orbHint').textContent = 'Dictation paused — tap ➤ Send when ready';
      return;
    }
    startSpeechEngine(false);
  }

  // 2. CENTER ORB / FLOATING BOTTOM ORB: Live Two-Way Agent Conversation!
  function handleOrbTap() {
    if (isSpeaking) {
      stopSpeaking();
      return;
    }
    if (isListening) {
      stopAllVoiceRecognition();
      document.getElementById('orbHint').textContent = 'Tap the golden sphere to talk with SRI';
      return;
    }
    startSpeechEngine(true);
  }

  function startSpeechEngine(autoSubmitOnFinal) {
    const hint = document.getElementById('orbHint');
    const dockCap = document.getElementById('dockCaption');
    const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRec) {
      hint.textContent = 'Voice API unavailable — type below';
      document.getElementById('promptInput').focus();
      return;
    }

    stopAllVoiceRecognition();
    const rec = new SpeechRec();
    activeRec = rec;
    rec.lang = LANG_MODES[langIdx].code;
    rec.continuous = !autoSubmitOnFinal;
    rec.interimResults = true;
    rec.maxAlternatives = 1;

    isListening = true;
    if (autoSubmitOnFinal) {
      hint.textContent = 'Listening (' + LANG_MODES[langIdx].label + ')... Speak to SRI Agent';
      dockCap.textContent = 'Listening... Speak your next question';
    } else {
      hint.textContent = 'Dictating into chat box (' + LANG_MODES[langIdx].label + ')... Tap ➤ to send';
    }
    hint.classList.add('listening');
    document.getElementById('waveDots').classList.add('active');
    document.getElementById('inlineMicBtn').classList.add('active');

    let finalTranscript = document.getElementById('promptInput').value
      ? document.getElementById('promptInput').value + ' '
      : '';
    if (autoSubmitOnFinal) finalTranscript = '';

    rec.onresult = (e) => {
      if (isSpeaking) return;
      let interim = '';
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const txt = e.results[i][0].transcript;
        if (e.results[i].isFinal) {
          finalTranscript += txt + ' ';
        } else {
          interim += txt;
        }
      }
      const combined = (finalTranscript + interim).trim();
      document.getElementById('promptInput').value = combined;

      // Only auto-submit if triggered from the Live Agent Orb (NOT from the inline chat mic)
      if (autoSubmitOnFinal && finalTranscript.trim()) {
        const toSend = finalTranscript.trim();
        stopAllVoiceRecognition();
        hint.textContent = 'SRI is analyzing & preparing page...';
        dockCap.textContent = 'SRI is analyzing: ' + toSend;
        sendToPython(toSend);
      }
    };

    rec.onerror = () => {
      stopAllVoiceRecognition();
    };

    rec.onend = () => {
      const val = document.getElementById('promptInput').value.trim();
      const wasListening = isListening;
      stopAllVoiceRecognition();
      if (autoSubmitOnFinal && wasListening && val) {
        hint.textContent = 'SRI is analyzing & preparing page...';
        sendToPython(val);
      } else if (!autoSubmitOnFinal && val) {
        hint.textContent = 'Dictation complete. Tap ➤ Send to execute task.';
      }
    };

    rec.start();
  }

  function stopSpeaking() {
    const audioEl = document.getElementById('sriNeuralAudio');
    if (audioEl) { audioEl.pause(); audioEl.currentTime = 0; }
    if (window.speechSynthesis) window.speechSynthesis.cancel();
    isSpeaking = false;
    document.getElementById('orbHint').classList.remove('speaking');
    document.getElementById('miniOrbBtn').classList.remove('speaking');
    document.getElementById('dockCaption').textContent = 'Tap round orb to ask follow-up...';
  }

  function playAgentVoiceReply(text, audioB64) {
    if (!text) return;
    stopAllVoiceRecognition();
    isSpeaking = true;

    // Automatically open the inline card in Project View on mobile
    if (window.innerWidth < 900) {
      setMobilePage('project');
    }

    const hint = document.getElementById('orbHint');
    const miniOrb = document.getElementById('miniOrbBtn');
    const dockCap = document.getElementById('dockCaption');

    hint.classList.remove('listening');
    hint.classList.add('speaking');
    hint.textContent = 'SRI: ' + text;
    miniOrb.classList.add('speaking');
    dockCap.textContent = '🔊 SRI: ' + text;

    const onFinishSpeaking = () => {
      isSpeaking = false;
      hint.classList.remove('speaking');
      miniOrb.classList.remove('speaking');
      hint.textContent = 'Tap the golden sphere to reply';
      dockCap.textContent = 'Tap round orb below to continue talking...';
      setTimeout(() => {
        if (!isSpeaking) startSpeechEngine(true);
      }, 450);
    };

    if (audioB64 && audioB64.length > 100) {
      const audioEl = document.getElementById('sriNeuralAudio');
      audioEl.src = 'data:audio/mp3;base64,' + audioB64;
      audioEl.onended = onFinishSpeaking;
      audioEl.onerror = () => speakBrowserFallback(text, onFinishSpeaking);
      audioEl.play().catch(() => speakBrowserFallback(text, onFinishSpeaking));
      return;
    }
    speakBrowserFallback(text, onFinishSpeaking);
  }

  function speakBrowserFallback(text, onDone) {
    if (!window.speechSynthesis) { onDone(); return; }
    window.speechSynthesis.cancel();
    const utter = new SpeechSynthesisUtterance(text);
    if (/[\u0b80-\u0bff]/.test(text)) utter.lang = 'ta-IN';
    else if (/[\u0900-\u097f]/.test(text)) utter.lang = 'hi-IN';
    else utter.lang = 'en-IN';
    utter.rate = 1.0;
    utter.onend = onDone;
    utter.onerror = onDone;
    window.speechSynthesis.speak(utter);
  }

  if (STATE.shouldSpeak && STATE.spokenText) {
    setTimeout(() => {
      playAgentVoiceReply(STATE.spokenText, STATE.audioBase64);
    }, 150);
  }

  // 3D Golden Sphere & 17 Sine Waves
  const canvas = document.getElementById('sriOrb');
  const ctx = canvas.getContext('2d');
  const dpr = window.devicePixelRatio || 1;
  let t = 0;

  const pts = Array.from({length: 1100}, () => {
    const u = Math.random(), v = Math.random();
    const th = 2 * Math.PI * u, ph = Math.acos(2 * v - 1);
    return { th, ph, s: Math.random() * 1.45 + 0.35 };
  });

  function renderOrb() {
    const W = canvas.clientWidth || 380;
    const H = 205;
    if (canvas.width !== W * dpr) {
      canvas.width = W * dpr; canvas.height = H * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }
    ctx.clearRect(0, 0, W, H);
    const isMob = window.innerWidth < 900;
    const R = isMob ? 56 : 80;
    const cx = W / 2, cy = H / 2;
    t += (isListening || isSpeaking) ? 0.045 : 0.015;

    const glowColor = isSpeaking
      ? 'rgba(16, 185, 129, 0.45)'
      : (isListening ? 'rgba(251, 191, 36, 0.52)' : 'rgba(245, 158, 11, 0.34)');

    const g = ctx.createRadialGradient(cx, cy, 8, cx, cy, R * 1.65);
    g.addColorStop(0, glowColor);
    g.addColorStop(1, 'rgba(6,7,9,0)');
    ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);

    for (let i = 0; i < 17; i++) {
      ctx.beginPath();
      const phase = i * 0.22;
      for (let x = 0; x <= W; x += 2) {
        const edgeFade = Math.sin((x / W) * Math.PI);
        const amp = (isListening || isSpeaking) ? (30 + i * 1.7) : (20 + i * 1.3);
        const y = cy + Math.sin(x * 0.018 + t * 1.3 + phase) * amp * edgeFade;
        if (x === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
      }
      const alpha = 0.06 + (i / 17) * 0.25;
      ctx.strokeStyle = isSpeaking
        ? `rgba(52, 211, 153, ${alpha})`
        : `rgba(245, 158, 11, ${alpha})`;
      ctx.lineWidth = 1.05;
      ctx.stroke();
    }

    pts.forEach(p => {
      const th = p.th + t * 0.45;
      const rad = R * (0.9 + (p.s * 0.06));
      const x3 = rad * Math.sin(p.ph) * Math.cos(th);
      const y3 = rad * Math.cos(p.ph);
      const z3 = rad * Math.sin(p.ph) * Math.sin(th);
      const a = (z3 + R) / (2 * R);
      ctx.beginPath(); ctx.arc(cx + x3, cy + y3, p.s, 0, Math.PI * 2);
      ctx.fillStyle = isSpeaking
        ? `rgba(52, 211, 153, ${0.16 + a * 0.84})`
        : `rgba(251, 191, 36, ${0.16 + a * 0.84})`;
      ctx.fill();
    });

    const sp = ctx.createRadialGradient(cx - R*0.35, cy - R*0.35, 2, cx - R*0.35, cy - R*0.35, R*0.42);
    sp.addColorStop(0, 'rgba(255,251,235,0.88)');
    sp.addColorStop(1, 'rgba(245,158,11,0)');
    ctx.fillStyle = sp; ctx.beginPath(); ctx.arc(cx - R*0.35, cy - R*0.35, R*0.42, 0, Math.PI*2); ctx.fill();

    ctx.save(); ctx.translate(cx, cy); ctx.rotate(-0.42);
    ctx.beginPath(); ctx.ellipse(0, 0, R * 1.38, R * 0.52, 0, 0, Math.PI * 2);
    ctx.strokeStyle = isSpeaking ? 'rgba(110, 231, 183, 0.6)' : 'rgba(253, 230, 138, 0.55)';
    ctx.lineWidth = 1.2; ctx.stroke();
    ctx.restore();

    requestAnimationFrame(renderOrb);
  }
  renderOrb();
</script>
</body>
</html>""".replace("__STATE_PAYLOAD__", state_payload)

    components.html(html_template, height=900, scrolling=False)
