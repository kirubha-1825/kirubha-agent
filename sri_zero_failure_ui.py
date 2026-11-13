import streamlit as st
import streamlit.components.v1 as components
import json

def render_sri_zero_failure_ui(
    agent_status="SRI (Ready)",
    active_tasks=0,
    completed_tasks=0,
    failed_tasks=0,
    workspace_file="workspace/login.html",
    generated_code="",
    generated_preview_html="",
    chat_history=None
):
    """
    Zero-Failure Full-Viewport Custom HTML/JS UI Component for SRI AI.
    - Completely bypasses Streamlit's default CSS/layout conflicts (no red radio dots, no stacked mobile pills).
    - Automatically renders Mobile App View (< 900px) with 17 full-bleed golden sine-waves & 2-page switcher,
      and Desktop 3-Zone View (>= 900px) with 2-orbit microphone sphere & [ Preview | Code ] glass container.
    - Bridges user prompts, quick-action triggers, and client-side Web Speech recognition directly back to Python.
    """
    if chat_history is None:
        chat_history = []

    # Hide Streamlit's outer padding/chrome completely & ensure iframe gets microphone permissions
    st.markdown("""
    <style>
    html, body, [data-testid="stAppViewContainer"], [data-testid="stApp"], .main {
        background-color: #060709 !important;
        margin: 0 !important;
        padding: 0 !important;
        overflow: hidden !important;
    }
    [data-testid="stToolbar"], [data-testid="stDecoration"], #MainMenu, footer {
        display: none !important;
    }
    [data-testid="stHeader"] {
        background: transparent !important;
        height: 0px !important;
        overflow: visible !important;
        border: none !important;
    }
    .block-container {
        padding: 0 !important;
        margin: 0 !important;
        max-width: 100vw !important;
    }
    /* Style the Control Drawer (st.sidebar) when opened for the 7 Backend Settings */
    [data-testid="stSidebar"] {
        background-color: #090B0E !important;
        border-left: 1px solid rgba(245, 158, 11, 0.35) !important;
        z-index: 99999 !important;
    }
    [data-testid="stSidebar"] [data-testid="stExpander"] {
        background: #0D1015 !important;
        border: 1px solid #1E222B !important;
        border-radius: 12px !important;
        margin-bottom: 8px !important;
    }
    [data-testid="stSidebar"] .stButton > button {
        background: #0C0E12 !important;
        border: 1px solid #1E222B !important;
        border-radius: 999px !important;
        color: #E5E7EB !important;
    }
    [data-testid="stSidebar"] .stButton > button:hover {
        border-color: #F59E0B !important;
        color: #F59E0B !important;
    }
    iframe {
        display: block !important;
        border: none !important;
        width: 100vw !important;
        height: 100vh !important;
    }
    </style>
    <script>
    (function allowIframeMic() {
        try {
            const iframes = document.querySelectorAll('iframe');
            iframes.forEach(f => {
                f.setAttribute('allow', 'microphone; camera; speech-recognition; autoplay');
            });
        } catch(e) {}
    })();
    </script>
    """, unsafe_allow_html=True)

    state_payload = json.dumps({
        "agentStatus": agent_status,
        "activeTasks": active_tasks,
        "completed": completed_tasks,
        "failed": failed_tasks,
        "workspaceFile": workspace_file,
        "code": generated_code or "<!-- SRI AI Workspace Ready -->\n<div class='card'>Waiting for prompt...</div>",
        "previewHtml": generated_preview_html or "<div style='color:#9CA3AF;font-family:Inter,sans-serif;padding:24px;text-align:center;'>Live Preview Ready</div>",
        "messages": chat_history[-10:]
    })

    html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Playfair+Display:wght@600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
  * {{
    box-sizing: border-box;
    margin: 0;
    padding: 0;
    -webkit-tap-highlight-color: transparent !important;
    -webkit-tap-highlight-color: rgba(0,0,0,0) !important;
    outline: none !important;
  }}
  body {{
    background: #060709;
    color: #F4F4F5;
    font-family: 'Inter', sans-serif;
    width: 100vw;
    height: 100vh;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    -webkit-tap-highlight-color: transparent !important;
  }}

  /* Top Sticky Header */
  .topbar {{
    height: 58px;
    background: rgba(6, 7, 9, 0.94);
    border-bottom: 1px solid #1E222B;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 22px;
    flex-shrink: 0;
    z-index: 20;
  }}
  .brand {{
    font-family: 'Playfair Display', serif;
    font-size: 23px;
    font-weight: 700;
    color: #F5E6C8;
    letter-spacing: 0.3px;
  }}
  .brand span {{ color: #F59E0B; }}
  .status-pill {{
    background: #0C0E12;
    border: 1px solid rgba(245, 158, 11, 0.38);
    border-radius: 999px;
    padding: 5px 14px;
    font-size: 12px;
    color: #E5E7EB;
    display: flex;
    align-items: center;
    gap: 7px;
  }}
  .dot-gold {{
    width: 7px; height: 7px; border-radius: 50%;
    background: #F59E0B; box-shadow: 0 0 8px #F59E0B;
  }}
  .gear-btn {{
    background: #0C0E12;
    border: 1px solid rgba(245, 158, 11, 0.5);
    color: #F59E0B;
    border-radius: 999px;
    padding: 6px 14px;
    font-size: 12.5px;
    font-weight: 500;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 6px;
    -webkit-tap-highlight-color: transparent;
    user-select: none;
  }}
  .gear-btn:hover {{ background: #141821; }}

  /* Compact Welcome Kirubha + Latest Work → Row (Mobile prominent) */
  .welcome-bar {{
    display: none;
    align-items: center;
    justify-content: space-between;
    padding: 10px 18px 4px 18px;
    flex-shrink: 0;
    z-index: 10;
  }}
  .welcome-col {{
    display: flex;
    flex-direction: column;
    gap: 1px;
  }}
  .welcome-sub {{
    font-size: 11.5px;
    color: #D97706;
    font-weight: 600;
    letter-spacing: 0.3px;
  }}
  .welcome-name {{
    font-size: 20px;
    font-weight: 700;
    color: #FFFFFF;
    font-family: 'Inter', sans-serif;
    line-height: 1.2;
  }}
  .latest-work-btn {{
    background: #0C0E12;
    border: 1px solid rgba(245, 158, 11, 0.45);
    color: #F59E0B;
    border-radius: 999px;
    padding: 5px 14px;
    font-size: 11.5px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s;
    -webkit-tap-highlight-color: transparent;
    user-select: none;
    outline: none;
  }}
  .latest-work-btn:hover {{
    background: #141821;
    border-color: #F59E0B;
    box-shadow: 0 0 10px rgba(245, 158, 11, 0.25);
  }}

  /* Main Workspace Grid */
  .main-grid {{
    flex: 1;
    display: grid;
    grid-template-columns: 270px 1fr 390px;
    gap: 18px;
    padding: 14px 22px;
    overflow: hidden;
  }}

  /* Left Telemetry (Desktop Only) */
  .left-col {{
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    padding-right: 8px;
  }}
  .greet {{ color: #D97706; font-size: 14px; margin-bottom: 2px; }}
  .hero-title {{ font-family: 'Playfair Display', serif; font-size: 32px; color: #FFF; margin-bottom: 16px; }}
  .stat-row {{
    display: flex; justify-content: space-between; padding: 10px 0;
    border-bottom: 1px solid #181B22; font-size: 13.5px; color: #9CA3AF;
  }}
  .gold-val {{ color: #F59E0B; font-weight: 600; }}

  /* Center Orb & Action Zone */
  .center-col {{
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: space-between;
    position: relative;
    overflow: hidden;
    padding-bottom: 4px;
  }}
  .orb-wrap {{
    flex: 1;
    width: 100%;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    position: relative;
  }}
  canvas#sriOrb {{
    width: 100%;
    height: 280px;
    cursor: pointer;
    -webkit-tap-highlight-color: transparent !important;
    -webkit-tap-highlight-color: rgba(0,0,0,0) !important;
    outline: none !important;
    user-select: none !important;
    touch-action: manipulation;
  }}
  .orb-hint {{
    font-size: 12px;
    color: #71717A;
    margin-top: 4px;
    text-align: center;
    min-height: 20px;
    transition: all 0.2s;
  }}

  /* Horizontal Swipeable Action Pills */
  .pills-row {{
    display: flex;
    flex-direction: row;
    flex-wrap: nowrap;
    gap: 8px;
    width: 100%;
    overflow-x: auto;
    padding: 6px 2px;
    justify-content: center;
    scrollbar-width: none;
  }}
  .pills-row::-webkit-scrollbar {{ display: none; }}
  .pill-btn {{
    flex: 0 0 auto;
    background: #0C0E12;
    border: 1px solid rgba(245, 158, 11, 0.35);
    color: #E5E7EB;
    border-radius: 999px;
    padding: 7px 14px;
    font-size: 12px;
    cursor: pointer;
    white-space: nowrap;
    transition: 0.2s;
    -webkit-tap-highlight-color: transparent;
    user-select: none;
  }}
  .pill-btn:hover {{ border-color: #F59E0B; color: #F59E0B; }}

  /* Unified Bottom Chat Bar */
  .chat-bar {{
    width: 100%;
    background: #0C0E12;
    border: 1px solid rgba(245, 158, 11, 0.45);
    border-radius: 999px;
    display: flex;
    align-items: center;
    padding: 5px 8px 5px 16px;
    gap: 8px;
    margin-top: 6px;
  }}
  .chat-bar input {{
    flex: 1;
    background: transparent;
    border: none;
    outline: none;
    color: #FFF;
    font-size: 13.5px;
  }}
  .icon-btn {{
    width: 34px; height: 34px; border-radius: 50%;
    border: 1px solid #27272A; background: #14171F;
    color: #F59E0B; cursor: pointer; display: flex;
    align-items: center; justify-content: center; font-size: 14px;
    -webkit-tap-highlight-color: transparent;
    user-select: none;
    transition: all 0.2s;
  }}
  .send-btn {{
    background: linear-gradient(135deg, #F59E0B, #D97706);
    color: #060709; border: none; font-weight: 700;
  }}

  /* Right Glass Card ([ Preview | Code ]) */
  .right-col {{
    background: #0A0C10;
    border: 1px solid rgba(245, 158, 11, 0.3);
    border-radius: 20px;
    padding: 14px;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }}
  .seg-tabs {{
    display: flex;
    background: #060709;
    border: 1px solid #1E222B;
    border-radius: 999px;
    padding: 3px;
    margin-bottom: 10px;
  }}
  .seg-tab {{
    flex: 1; text-align: center; padding: 6px 10px;
    border-radius: 999px; font-size: 12.5px; color: #9CA3AF;
    cursor: pointer; border: 1px solid transparent;
    -webkit-tap-highlight-color: transparent;
    user-select: none;
  }}
  .seg-tab.active {{
    background: #141821; border-color: #F59E0B; color: #FFF; font-weight: 600;
  }}
  .file-tag {{ font-size: 11px; color: #71717A; margin-bottom: 8px; font-family: 'JetBrains Mono', monospace; }}
  .workspace-pane {{
    flex: 1; background: #060709; border: 1px solid #181B22;
    border-radius: 12px; overflow: auto; padding: 12px;
    font-family: 'JetBrains Mono', monospace; font-size: 12px; color: #E5E7EB;
  }}

  /* Mobile Bottom 2-Page Switcher (Hidden on Desktop) */
  .mob-nav {{ display: none; }}

  /* MOBILE RESPONSIVE (< 900px): 2-Page App View & Exact Spacing */
  @media (max-width: 900px) {{
    .topbar {{ padding: 0 14px; height: 54px; }}
    .gear-label {{ display: none; }}
    .welcome-bar {{ display: flex; }}
    body.show-project .welcome-bar {{ display: none; }}

    .main-grid {{
      display: flex;
      flex-direction: column;
      flex: 1;
      padding: 4px 14px 6px 14px;
      overflow: hidden;
    }}
    .left-col {{ display: none !important; }}
    .center-col {{
      flex: 1;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      padding-bottom: 12px;
      overflow: hidden;
    }}
    .pills-row {{
      justify-content: flex-start;
      margin-bottom: 4px;
    }}
    .right-col {{
      display: none;
      flex: 1;
      height: 100%;
    }}
    body.show-project .center-col {{ display: none; }}
    body.show-project .right-col {{ display: flex; }}

    /* Bottom 2-Page Switcher styled as rounded pills with solid gold fill */
    .mob-nav {{
      display: flex;
      align-items: center;
      justify-content: center;
      background: #0A0C10;
      border: 1px solid #1E222B;
      border-radius: 999px;
      padding: 4px;
      margin: 6px 14px 14px 14px;
      gap: 6px;
      flex-shrink: 0;
      box-shadow: 0 4px 20px rgba(0, 0, 0, 0.55);
    }}
    .mob-nav-btn {{
      flex: 1;
      text-align: center;
      padding: 8px 14px;
      border-radius: 999px;
      font-size: 12.5px;
      font-weight: 600;
      background: transparent;
      border: 1px solid transparent;
      color: #9CA3AF;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 6px;
      transition: all 0.2s ease;
      -webkit-tap-highlight-color: transparent;
      user-select: none;
      outline: none;
    }}
    .mob-nav-btn.active {{
      background: #F59E0B !important;
      color: #060709 !important;
      border: 1px solid #F59E0B !important;
      font-weight: 700 !important;
      box-shadow: 0 0 16px rgba(245, 158, 11, 0.4);
    }}
  }}

  @keyframes pulseDot {{
    0% {{ transform: scale(0.9); opacity: 0.7; }}
    100% {{ transform: scale(1.3); opacity: 1; box-shadow: 0 0 12px #F59E0B; }}
  }}
</style>
</head>
<body>
  <!-- Topbar -->
  <div class="topbar">
    <div class="brand">SRI AI<span>.</span></div>
    <div class="status-pill"><span class="dot-gold"></span> <span id="hdrStatus">98.4% Agent Active</span></div>
    <button class="gear-btn" onclick="openBackendSettings()">⚙️ <span class="gear-label">Control Drawer</span></button>
  </div>

  <!-- Mobile Welcome + Latest Work Row -->
  <div class="welcome-bar">
    <div class="welcome-col">
      <span class="welcome-sub">Welcome</span>
      <span class="welcome-name">Kirubha</span>
    </div>
    <button class="latest-work-btn" onclick="setMobilePage('project')">Latest Work →</button>
  </div>

  <div class="main-grid">
    <!-- Left Telemetry (Desktop) -->
    <div class="left-col">
      <div>
        <div class="greet">Good morning, Kirubha</div>
        <div class="hero-title">Agent Live</div>
        <div class="stat-row"><span>Agent Status</span><span class="gold-val" id="stAgent">● SRI (Ready)</span></div>
        <div class="stat-row"><span>Active Tasks</span><span class="gold-val" id="stActive">0</span></div>
        <div class="stat-row"><span>Completed</span><span class="gold-val" id="stComp">0</span></div>
        <div class="stat-row"><span>Failed</span><span class="gold-val" id="stFail">0</span></div>
      </div>
      <div style="font-size:12px;color:#71717A;">Environment: <span style="color:#E5E7EB;">Streamlit Cloud workspace/</span></div>
    </div>

    <!-- Center Orb & Unified Chat -->
    <div class="center-col">
      <div class="orb-wrap">
        <canvas id="sriOrb" onclick="startVoiceCapture()"></canvas>
        <div class="orb-hint" id="orbHint">Tap the golden sphere to talk with SRI in Tamil or English</div>
      </div>

      <div style="width:100%;">
        <div class="pills-row">
          <button class="pill-btn" onclick="sendToPython('Build Student Dashboard')">Student Dashboard</button>
          <button class="pill-btn" onclick="sendToPython('Build SaaS Auth')">SaaS Auth</button>
          <button class="pill-btn" onclick="sendToPython('Build Kanban Board')">Kanban Board</button>
          <button class="pill-btn" onclick="sendToPython('Refine login.html')">Refine login.html</button>
        </div>
        <div class="chat-bar">
          <input id="promptInput" type="text" placeholder="Ask SRI Agent a question (Tamil / English)..." onkeydown="if(event.key==='Enter') submitPrompt()">
          <button class="icon-btn" id="micBtn" onclick="startVoiceCapture()" title="Voice">🎤</button>
          <button class="icon-btn send-btn" onclick="submitPrompt()" title="Send">➤</button>
        </div>
      </div>
    </div>

    <!-- Right Workspace ([ Preview | Code ]) -->
    <div class="right-col">
      <div class="seg-tabs">
        <div class="seg-tab active" id="tabPreview" onclick="switchTab('preview')">Preview</div>
        <div class="seg-tab" id="tabCode" onclick="switchTab('code')">Code</div>
      </div>
      <div class="file-tag" id="fileLabel">workspace/login.html</div>
      <div class="workspace-pane" id="panePreview"></div>
      <pre class="workspace-pane" id="paneCode" style="display:none;white-space:pre-wrap;"></pre>
    </div>
  </div>

  <!-- Mobile 2-Page Bottom Switcher -->
  <div class="mob-nav">
    <div class="mob-nav-btn active" id="navHub" onclick="setMobilePage('hub')">✦ Agent Hub</div>
    <div class="mob-nav-btn" id="navProj" onclick="setMobilePage('project')">👁️ Project View</div>
  </div>

<script>
  const STATE = {state_payload};
  document.getElementById('stAgent').textContent = '● ' + STATE.agentStatus;
  document.getElementById('stActive').textContent = STATE.activeTasks;
  document.getElementById('stComp').textContent = STATE.completed;
  document.getElementById('stFail').textContent = STATE.failed;
  document.getElementById('fileLabel').textContent = STATE.workspaceFile;

  if (STATE.previewHtml && (STATE.previewHtml.includes('<!DOCTYPE') || STATE.previewHtml.includes('<html')) && !STATE.previewHtml.includes('<iframe')) {{
    const pIframe = document.createElement('iframe');
    pIframe.style.cssText = 'width:100%;height:100%;border:none;min-height:380px;border-radius:8px;background:#090B10;';
    pIframe.srcdoc = STATE.previewHtml;
    const pContainer = document.getElementById('panePreview');
    pContainer.innerHTML = '';
    pContainer.appendChild(pIframe);
  }} else {{
    document.getElementById('panePreview').innerHTML = STATE.previewHtml;
  }}
  document.getElementById('paneCode').textContent = STATE.code;

  function switchTab(mode) {{
    document.getElementById('tabPreview').classList.toggle('active', mode === 'preview');
    document.getElementById('tabCode').classList.toggle('active', mode === 'code');
    document.getElementById('panePreview').style.display = mode === 'preview' ? 'block' : 'none';
    document.getElementById('paneCode').style.display = mode === 'code' ? 'block' : 'none';
  }}

  function setMobilePage(page) {{
    const isProj = page === 'project';
    document.body.classList.toggle('show-project', isProj);
    document.getElementById('navHub').classList.toggle('active', !isProj);
    document.getElementById('navProj').classList.toggle('active', isProj);
  }}

  function openBackendSettings() {{
    try {{
      const doc = window.parent.document;
      const btn = doc.querySelector('[data-testid="collapsedControl"] button') ||
                  doc.querySelector('[data-testid="collapsedControl"]') ||
                  doc.querySelector('button[aria-label*="sidebar"]') ||
                  doc.querySelector('[data-testid="stSidebarCollapseButton"] button');
      if (btn) btn.click();
    }} catch(e) {{}}
  }}

  function submitPrompt() {{
    const val = document.getElementById('promptInput').value.trim();
    if (!val) return;
    sendToPython(val);
  }}

  function sendToPython(command) {{
    const url = new URL(window.parent.location.href);
    url.searchParams.set('sri_cmd', command);
    url.searchParams.set('ts', Date.now());
    window.parent.history.replaceState({{}}, '', url);
    window.parent.location.reload();
  }}

  // -------------------------------------------------------------
  // Client-Side Speech Recognition (ta-IN / en-IN, no page reload)
  // -------------------------------------------------------------
  let isListening = false;
  let recognition = null;

  try {{
    const parentIframes = window.parent.document.querySelectorAll('iframe');
    parentIframes.forEach(f => {{
      const cur = f.getAttribute('allow') || '';
      if (!cur.includes('microphone')) {{
        f.setAttribute('allow', (cur ? cur + '; ' : '') + 'microphone; camera; speech-recognition; autoplay;');
      }}
    }});
  }} catch(e) {{}}

  function initSpeechRecognition() {{
    const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRec) return null;
    const rec = new SpeechRec();
    rec.continuous = false;
    rec.interimResults = true;
    rec.maxAlternatives = 1;
    rec.lang = 'ta-IN'; // Tamil with Indian English phonetic support

    rec.onstart = () => {{
      isListening = true;
      setOrbListeningUI(true);
    }};

    rec.onresult = (event) => {{
      let interim = '';
      let finalTranscript = '';
      for (let i = event.resultIndex; i < event.results.length; ++i) {{
        if (event.results[i].isFinal) {{
          finalTranscript += event.results[i][0].transcript;
        }} else {{
          interim += event.results[i][0].transcript;
        }}
      }}
      const current = finalTranscript || interim;
      if (current) {{
        document.getElementById('promptInput').value = current;
      }}
      if (finalTranscript && finalTranscript.trim()) {{
        isListening = false;
        setOrbListeningUI(false);
        sendToPython(finalTranscript.trim());
      }}
    }};

    rec.onerror = (event) => {{
      console.warn('Speech recognition notice:', event.error);
      isListening = false;
      setOrbListeningUI(false);
      const hint = document.getElementById('orbHint');
      if (event.error === 'not-allowed') {{
        if (hint) hint.innerHTML = '<span style="color:#EF4444;">⚠️ Microphone access denied. Allow mic in browser settings.</span>';
      }} else if (event.error !== 'no-speech') {{
        if (hint) hint.innerHTML = 'Tap the golden sphere to talk with SRI in Tamil or English';
      }}
    }};

    rec.onend = () => {{
      if (isListening) {{
        isListening = false;
        setOrbListeningUI(false);
        const val = document.getElementById('promptInput').value.trim();
        if (val) {{
          sendToPython(val);
        }}
      }}
    }};

    return rec;
  }}

  function startVoiceCapture() {{
    if (isListening) {{
      if (recognition) {{
        try {{ recognition.stop(); }} catch(e) {{}}
      }}
      isListening = false;
      setOrbListeningUI(false);
      return;
    }}

    if (!recognition) {{
      recognition = initSpeechRecognition();
    }}

    if (!recognition) {{
      const hint = document.getElementById('orbHint');
      if (hint) hint.innerHTML = '<span style="color:#F59E0B;">🎙️ Speech recognition not supported on this browser. Type below.</span>';
      document.getElementById('promptInput').focus();
      return;
    }}

    try {{
      recognition.start();
    }} catch(err) {{
      try {{
        recognition.stop();
        setTimeout(() => {{
          try {{ recognition.start(); }} catch(e) {{}}
        }}, 200);
      }} catch(e) {{}}
    }}
  }}

  function setOrbListeningUI(active) {{
    const hint = document.getElementById('orbHint');
    const micBtn = document.getElementById('micBtn');
    if (active) {{
      if (hint) {{
        hint.innerHTML = '<span style="color:#F59E0B;font-weight:600;display:inline-flex;align-items:center;gap:6px;"><span class="dot-gold" style="animation:pulseDot 0.8s infinite alternate;"></span> 🎙️ ஸ்ரீ கவனித்துக் கொண்டிருக்கிறது... பேசுங்கள் / Speak now...</span>';
      }}
      if (micBtn) {{
        micBtn.style.borderColor = '#F59E0B';
        micBtn.style.boxShadow = '0 0 14px rgba(245,158,11,0.6)';
        micBtn.style.color = '#FBBF24';
      }}
    }} else {{
      if (hint) {{
        hint.innerHTML = 'Tap the golden sphere to talk with SRI in Tamil or English';
      }}
      if (micBtn) {{
        micBtn.style.borderColor = '#27272A';
        micBtn.style.boxShadow = 'none';
        micBtn.style.color = '#F59E0B';
      }}
    }}
  }}

  // -------------------------------------------------------------
  // 3D Golden Orb Canvas (Live Pulse on Voice Listening)
  // -------------------------------------------------------------
  const canvas = document.getElementById('sriOrb');
  const ctx = canvas.getContext('2d');
  const dpr = window.devicePixelRatio || 1;
  let t = 0;

  const pts = Array.from({{length: 1000}}, () => {{
    const u = Math.random(), v = Math.random();
    const th = 2 * Math.PI * u, ph = Math.acos(2 * v - 1);
    return {{ th, ph, r: 1, s: Math.random() * 1.4 + 0.35 }};
  }});

  function renderOrb() {{
    const W = canvas.clientWidth || 380;
    const H = 280;
    if (canvas.width !== W * dpr) {{
      canvas.width = W * dpr; canvas.height = H * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }}
    ctx.clearRect(0, 0, W, H);
    const isMob = window.innerWidth < 900;
    const R = isMob ? 64 : 88;
    const cx = W / 2, cy = H / 2;
    t += isListening ? 0.038 : 0.015;

    // Ambient Radial Gold Halo (Vibrant pulse when listening)
    const g = ctx.createRadialGradient(cx, cy, 8, cx, cy, R * (isListening ? 1.75 : 1.55));
    g.addColorStop(0, isListening ? 'rgba(245,158,11,0.56)' : 'rgba(245,158,11,0.34)');
    g.addColorStop(1, 'rgba(6,7,9,0)');
    ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);

    if (isMob) {{
      // Mobile: 17 Full-Bleed Golden Sine-Wave Ribbons
      for (let i = 0; i < 17; i++) {{
        ctx.beginPath();
        const phase = i * 0.22;
        for (let x = 0; x <= W; x += 2) {{
          const edgeFade = Math.sin((x / W) * Math.PI);
          const y = cy + Math.sin(x * 0.018 + t * (isListening ? 2.2 : 1.3) + phase) * (25 + i * 1.55) * edgeFade;
          if (x === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
        }}
        ctx.strokeStyle = `rgba(245, 158, 11, ${{0.06 + (i / 17) * 0.24}})`;
        ctx.lineWidth = 1.05; ctx.stroke();
      }}
    }} else {{
      // Desktop: 2 Intersecting Golden Orbits
      [-0.52, 0.52].forEach((tilt, idx) => {{
        ctx.save(); ctx.translate(cx, cy); ctx.rotate(tilt);
        ctx.beginPath(); ctx.ellipse(0, 0, R * 1.58, R * 0.62, 0, 0, Math.PI * 2);
        ctx.strokeStyle = isListening ? 'rgba(245,158,11,0.85)' : 'rgba(245,158,11,0.48)';
        ctx.lineWidth = 1.2; ctx.stroke();
        const da = t * (idx === 0 ? 1.1 : -0.9);
        ctx.beginPath(); ctx.arc(Math.cos(da)*R*1.58, Math.sin(da)*R*0.62, 2.5, 0, Math.PI*2);
        ctx.fillStyle = '#FDE68A'; ctx.fill();
        ctx.restore();
      }});
    }}

    pts.forEach(p => {{
      const th = p.th + t * (isListening ? 0.9 : 0.45);
      const rad = R * (0.9 + (p.s * 0.06));
      const x3 = rad * Math.sin(p.ph) * Math.cos(th);
      const y3 = rad * Math.cos(p.ph);
      const z3 = rad * Math.sin(p.ph) * Math.sin(th);
      const a = (z3 + R) / (2 * R);
      ctx.beginPath(); ctx.arc(cx + x3, cy + y3, p.s, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(251,191,36,${{0.16 + a * 0.84}})`; ctx.fill();
    }});

    const sp = ctx.createRadialGradient(cx - R*0.35, cy - R*0.35, 2, cx - R*0.35, cy - R*0.35, R*0.42);
    sp.addColorStop(0, 'rgba(255,251,235,0.88)'); sp.addColorStop(1, 'rgba(245,158,11,0)');
    ctx.fillStyle = sp; ctx.beginPath(); ctx.arc(cx - R*0.35, cy - R*0.35, R*0.42, 0, Math.PI*2); ctx.fill();

    if (isMob) {{
      ctx.save(); ctx.translate(cx, cy); ctx.rotate(-0.42);
      ctx.beginPath(); ctx.ellipse(0, 0, R * 1.38, R * 0.52, 0, 0, Math.PI * 2);
      ctx.strokeStyle = isListening ? 'rgba(253,230,138,0.9)' : 'rgba(253,230,138,0.55)';
      ctx.lineWidth = 1.2; ctx.stroke();
      ctx.restore();
    }} else {{
      ctx.beginPath(); ctx.arc(cx, cy, 26, 0, Math.PI * 2);
      ctx.fillStyle = 'rgba(14,14,18,0.9)'; ctx.fill();
      ctx.strokeStyle = isListening ? '#F59E0B' : 'rgba(245,158,11,0.4)'; ctx.lineWidth = 1; ctx.stroke();
      ctx.fillStyle = isListening ? '#F59E0B' : '#E5D3B3';
      ctx.beginPath(); ctx.roundRect(cx - 4.5, cy - 11, 9, 14, 4.5); ctx.fill();
      ctx.strokeStyle = isListening ? '#F59E0B' : '#E5D3B3'; ctx.lineWidth = 1.8;
      ctx.beginPath(); ctx.arc(cx, cy - 2, 8, 0.1*Math.PI, 0.9*Math.PI); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(cx, cy + 6); ctx.lineTo(cx, cy + 11); ctx.stroke();
    }}
    requestAnimationFrame(renderOrb);
  }}
  renderOrb();
</script>
</body>
</html>"""

    components.html(html_template, height=900, scrolling=False)
