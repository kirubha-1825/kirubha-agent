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
        height: 100dvh !important;
        height: 100vh !important;
        overflow: hidden !important;
        -webkit-tap-highlight-color: transparent !important;
        -webkit-tap-highlight-color: rgba(0,0,0,0) !important;
        outline: none !important;
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
        height: 100dvh !important;
        height: 100vh !important;
        overflow: hidden !important;
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
        height: 100dvh !important;
        height: 100vh !important;
        max-height: 100dvh !important;
        overflow: hidden !important;
        -webkit-tap-highlight-color: transparent !important;
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

    html_template = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Playfair+Display:wght@600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
  *, *::before, *::after {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
    -webkit-tap-highlight-color: transparent !important;
    -webkit-tap-highlight-color: rgba(0,0,0,0) !important;
    outline: none !important;
  }
  html, body {
    background: #060709;
    color: #F4F4F5;
    font-family: 'Inter', sans-serif;
    width: 100vw;
    height: 100dvh;
    height: 100vh;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    -webkit-user-select: none !important;
    user-select: none !important;
  }
  input, textarea {
    -webkit-user-select: text !important;
    user-select: text !important;
  }

  /* Ambient Canvas for Floating Silk Waves & Gold Dust */
  canvas#bgParticles {
    position: fixed;
    inset: 0;
    width: 100vw;
    height: 100vh;
    pointer-events: none;
    z-index: 0;
  }

  /* Top Sticky Header */
  .topbar {
    height: 56px;
    background: rgba(6, 7, 9, 0.94);
    backdrop-filter: blur(16px);
    border-bottom: 1px solid #1E222B;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 24px;
    flex-shrink: 0;
    z-index: 20;
    position: relative;
  }
  .brand {
    font-family: 'Playfair Display', serif;
    font-size: 24px;
    font-weight: 700;
    color: #F5E6C8;
    letter-spacing: 0.3px;
    display: flex;
    align-items: center;
  }
  .brand span { color: #F59E0B; }

  .topbar-center {
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .topbar-right {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .status-pill {
    background: #0C0E12;
    border: 1px solid rgba(245, 158, 11, 0.38);
    border-radius: 999px;
    padding: 5px 14px;
    font-size: 12px;
    color: #E5E7EB;
    display: flex;
    align-items: center;
    gap: 7px;
    white-space: nowrap;
  }
  .pill-green {
    border-color: rgba(16, 185, 129, 0.45) !important;
    color: #A7F3D0 !important;
    background: rgba(16, 185, 129, 0.08) !important;
  }
  .dot-gold {
    width: 7px; height: 7px; border-radius: 50%;
    background: #F59E0B; box-shadow: 0 0 8px #F59E0B;
    display: inline-block;
  }
  .dot-green {
    width: 7px; height: 7px; border-radius: 50%;
    background: #10B981; box-shadow: 0 0 8px #10B981;
    display: inline-block;
  }

  .gear-btn-circle {
    width: 36px;
    height: 36px;
    border-radius: 50%;
    background: #0C0E12;
    border: 1px solid rgba(245, 158, 11, 0.45);
    color: #F59E0B;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 15px;
    cursor: pointer;
    transition: all 0.2s;
    outline: none !important;
    -webkit-tap-highlight-color: transparent !important;
    user-select: none !important;
  }
  .gear-btn-circle:hover {
    background: #141821;
    border-color: #F59E0B;
    box-shadow: 0 0 10px rgba(245, 158, 11, 0.3);
  }

  /* Compact Welcome Kirubha + Latest Work → Row (Mobile prominent) */
  .welcome-bar {
    display: none;
    align-items: center;
    justify-content: space-between;
    padding: 10px 18px 4px 18px;
    flex-shrink: 0;
    z-index: 10;
    position: relative;
  }
  .welcome-col {
    display: flex;
    flex-direction: column;
    gap: 1px;
  }
  .welcome-sub {
    font-size: 11.5px;
    color: #D97706;
    font-weight: 600;
    letter-spacing: 0.3px;
  }
  .welcome-name {
    font-size: 22px;
    font-weight: 700;
    color: #FFFFFF;
    font-family: 'Inter', sans-serif;
    line-height: 1.2;
  }
  .latest-work-btn {
    background: #0C0E12;
    border: 1px solid rgba(245, 158, 11, 0.5);
    color: #F59E0B;
    border-radius: 999px;
    padding: 6px 15px;
    font-size: 12px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s;
    -webkit-tap-highlight-color: transparent !important;
    user-select: none !important;
    outline: none !important;
  }
  .latest-work-btn:hover {
    background: #141821;
    border-color: #F59E0B;
    box-shadow: 0 0 10px rgba(245, 158, 11, 0.3);
  }

  /* Main Workspace Grid (Desktop 3-Zone) */
  .main-grid {
    flex: 1;
    display: grid;
    grid-template-columns: 270px 1fr 390px;
    gap: 18px;
    padding: 14px 22px;
    overflow: hidden;
    position: relative;
    z-index: 1;
  }

  /* Left Telemetry (Desktop Only) */
  .left-col {
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    padding-right: 8px;
  }
  .greet { color: #D97706; font-size: 14px; margin-bottom: 2px; }
  .hero-title { font-family: 'Playfair Display', serif; font-size: 32px; color: #FFF; margin-bottom: 16px; }
  .stat-row {
    display: flex; justify-content: space-between; padding: 10px 0;
    border-bottom: 1px solid #181B22; font-size: 13.5px; color: #9CA3AF;
  }
  .gold-val { color: #F59E0B; font-weight: 600; }

  /* Center Orb & Action Zone */
  .center-col {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: space-between;
    position: relative;
    overflow: hidden;
    padding-bottom: 4px;
    z-index: 2;
  }
  .orb-wrap {
    flex: 1;
    width: 100%;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    position: relative;
  }
  canvas#sriOrb {
    width: 100%;
    height: 280px;
    cursor: pointer;
    -webkit-tap-highlight-color: transparent !important;
    -webkit-tap-highlight-color: rgba(0,0,0,0) !important;
    outline: none !important;
    user-select: none !important;
    touch-action: manipulation;
  }
  .orb-hint {
    font-size: 12px;
    color: #71717A;
    margin-top: 4px;
    text-align: center;
    min-height: 20px;
    transition: all 0.2s;
  }

  /* Horizontal Swipeable Action Pills */
  .pills-row {
    display: flex;
    flex-direction: row;
    flex-wrap: nowrap;
    gap: 8px;
    width: 100%;
    overflow-x: auto;
    padding: 6px 2px;
    justify-content: center;
    scrollbar-width: none;
    -webkit-overflow-scrolling: touch;
  }
  .pills-row::-webkit-scrollbar { display: none; }
  .pill-btn {
    flex: 0 0 auto;
    background: #0C0E12;
    border: 1px solid rgba(245, 158, 11, 0.35);
    color: #E5E7EB;
    border-radius: 999px;
    padding: 7px 15px;
    font-size: 12px;
    cursor: pointer;
    white-space: nowrap;
    transition: 0.2s;
    -webkit-tap-highlight-color: transparent !important;
    user-select: none !important;
    outline: none !important;
  }
  .pill-btn:hover { border-color: #F59E0B; color: #F59E0B; }
  .pill-btn-gold {
    border-color: #F59E0B !important;
    color: #F59E0B !important;
    background: rgba(245, 158, 11, 0.08) !important;
    box-shadow: 0 0 10px rgba(245, 158, 11, 0.15);
  }

  /* Unified Bottom Chat Bar */
  .chat-bar {
    width: 100%;
    background: #0C0E12;
    border: 1px solid rgba(245, 158, 11, 0.45);
    border-radius: 999px;
    display: flex;
    align-items: center;
    padding: 5px 8px 5px 16px;
    gap: 8px;
    margin-top: 6px;
    position: relative;
    overflow: hidden;
  }
  .chat-waveform {
    display: none;
    align-items: center;
    gap: 3px;
    height: 20px;
    padding: 0 4px;
    flex-shrink: 0;
  }
  .chat-waveform.active {
    display: flex;
  }
  .wave-bar {
    width: 3px;
    height: 6px;
    background: #F59E0B;
    border-radius: 999px;
    animation: waveBounce 0.8s ease-in-out infinite alternate;
  }
  .wave-bar:nth-child(1) { animation-delay: 0.0s; height: 8px; }
  .wave-bar:nth-child(2) { animation-delay: 0.15s; height: 16px; }
  .wave-bar:nth-child(3) { animation-delay: 0.3s; height: 22px; }
  .wave-bar:nth-child(4) { animation-delay: 0.1s; height: 14px; }
  .wave-bar:nth-child(5) { animation-delay: 0.25s; height: 20px; }
  .wave-bar:nth-child(6) { animation-delay: 0.4s; height: 12px; }
  .wave-bar:nth-child(7) { animation-delay: 0.2s; height: 18px; }
  .wave-bar:nth-child(8) { animation-delay: 0.35s; height: 10px; }
  .wave-bar:nth-child(9) { animation-delay: 0.05s; height: 14px; }

  @keyframes waveBounce {
    0% { transform: scaleY(0.3); opacity: 0.5; background: #D97706; }
    100% { transform: scaleY(1.2); opacity: 1; background: #FBBF24; box-shadow: 0 0 6px #F59E0B; }
  }

  .chat-bar input {
    flex: 1;
    background: transparent;
    border: none;
    outline: none;
    color: #FFF;
    font-size: 13.5px;
  }
  .chat-bar input::placeholder {
    color: #71717A;
  }
  .icon-btn {
    width: 34px; height: 34px; border-radius: 50%;
    border: 1px solid #27272A; background: #14171F;
    color: #F59E0B; cursor: pointer; display: flex;
    align-items: center; justify-content: center; font-size: 14px;
    -webkit-tap-highlight-color: transparent !important;
    user-select: none !important;
    transition: all 0.2s;
    outline: none !important;
    flex-shrink: 0;
  }
  .send-btn {
    background: linear-gradient(135deg, #F59E0B, #D97706);
    color: #060709; border: none; font-weight: 700;
  }
  .send-btn:hover {
    box-shadow: 0 0 12px rgba(245, 158, 11, 0.5);
  }

  /* Right Glass Card ([ Preview | Code ]) */
  .right-col {
    background: #0A0C10;
    border: 1px solid rgba(245, 158, 11, 0.3);
    border-radius: 20px;
    padding: 14px;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    z-index: 2;
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
    cursor: pointer; border: 1px solid transparent;
    -webkit-tap-highlight-color: transparent !important;
    user-select: none !important;
    outline: none !important;
  }
  .seg-tab.active {
    background: #141821; border-color: #F59E0B; color: #FFF; font-weight: 600;
  }
  .file-tag { font-size: 11px; color: #71717A; margin-bottom: 8px; font-family: 'JetBrains Mono', monospace; }
  .workspace-pane {
    flex: 1; background: #060709; border: 1px solid #181B22;
    border-radius: 12px; overflow: auto; padding: 12px;
    font-family: 'JetBrains Mono', monospace; font-size: 12px; color: #E5E7EB;
  }

  /* Mobile Bottom 2-Page Switcher (Hidden on Desktop) */
  .mob-nav { display: none; }

  /* DESKTOP / MOBILE VISIBILITY HELPERS */
  .desk-only { display: flex; }
  .mob-only { display: none; }

  /* MOBILE RESPONSIVE (< 900px): 2-Page App View & Exact Spacing */
  @media (max-width: 900px) {
    .topbar { padding: 0 14px; height: 52px; }
    .desk-only { display: none !important; }
    .mob-only { display: flex !important; }
    .welcome-bar { display: flex; }
    body.show-project .welcome-bar { display: none !important; }

    .main-grid {
      display: flex;
      flex-direction: column;
      flex: 1;
      padding: 4px 14px 6px 14px;
      overflow: hidden;
    }
    .left-col { display: none !important; }
    .center-col {
      flex: 1;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      padding-bottom: 12px;
      overflow: hidden;
    }
    .pills-row {
      justify-content: flex-start;
      margin-bottom: 4px;
    }
    .right-col {
      display: none;
      flex: 1;
      height: 100%;
    }
    body.show-project .center-col { display: none !important; }
    body.show-project .right-col { display: flex !important; }

    /* Bottom 2-Page Switcher styled as rounded pills with solid gold fill */
    .mob-nav {
      display: flex;
      align-items: center;
      justify-content: center;
      background: transparent;
      padding: 8px 16px 56px 16px;
      gap: 10px;
      flex-shrink: 0;
      z-index: 10;
    }
    .mob-nav-btn {
      flex: 1;
      text-align: center;
      padding: 9px 14px;
      border-radius: 999px;
      font-size: 12.5px;
      font-weight: 600;
      background: #0C0E12;
      border: 1px solid rgba(245, 158, 11, 0.2);
      color: #9CA3AF;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 6px;
      transition: all 0.2s ease;
      -webkit-tap-highlight-color: transparent !important;
      user-select: none !important;
      outline: none !important;
    }
    .mob-nav-btn.active {
      background: #F59E0B !important;
      color: #060709 !important;
      border: 1px solid #F59E0B !important;
      font-weight: 700 !important;
      box-shadow: 0 0 16px rgba(245, 158, 11, 0.4) !important;
    }
  }

  @keyframes pulseDot {
    0% { transform: scale(0.9); opacity: 0.7; }
    100% { transform: scale(1.3); opacity: 1; box-shadow: 0 0 12px #F59E0B; }
  }
</style>
</head>
<body>
  <!-- Ambient Floating Gold Bokeh & Silk Wave Canvas -->
  <canvas id="bgParticles"></canvas>

  <!-- Topbar -->
  <div class="topbar">
    <div class="brand">SRI AI<span>.</span></div>
    <div class="topbar-center desk-only">
      <div class="status-pill"><span class="dot-gold"></span> <span id="hdrStatus">98.4% Agent Active</span></div>
    </div>
    <div class="topbar-right">
      <div class="status-pill mob-only pill-green"><span class="dot-green"></span> 24/7 Active</div>
      <button class="gear-btn-circle" onclick="openBackendSettings()" title="Settings / Control Drawer">⚙️</button>
    </div>
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
        <div class="greet">Good evening, Kirubha</div>
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
        <canvas id="sriOrb" onclick="onOrbClick()"></canvas>
        <div class="orb-hint" id="orbHint">Tap the golden sphere to talk with SRI in Tamil or English</div>
      </div>

      <div style="width:100%;">
        <div class="pills-row">
          <button class="pill-btn pill-btn-gold" onclick="sendToPython('Build Student Dashboard')">Student Dashboard</button>
          <button class="pill-btn" onclick="sendToPython('Build SaaS Auth')">SaaS Auth</button>
          <button class="pill-btn" onclick="sendToPython('Build Kanban Board')">Kanban Board</button>
          <button class="pill-btn" onclick="sendToPython('Refine login.html')">Refine login.html</button>
        </div>
        <div class="chat-bar">
          <div id="chatWaveform" class="chat-waveform">
            <div class="wave-bar"></div>
            <div class="wave-bar"></div>
            <div class="wave-bar"></div>
            <div class="wave-bar"></div>
            <div class="wave-bar"></div>
            <div class="wave-bar"></div>
            <div class="wave-bar"></div>
            <div class="wave-bar"></div>
            <div class="wave-bar"></div>
          </div>
          <input id="promptInput" type="text" placeholder="Message SRI..." onkeydown="if(event.key==='Enter') submitPrompt()">
          <button class="icon-btn" id="micBtn" onclick="onMicClick()" title="Voice">🎤</button>
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
  const STATE = __STATE_PAYLOAD__;
  document.getElementById('stAgent').textContent = '● ' + STATE.agentStatus;
  document.getElementById('stActive').textContent = STATE.activeTasks;
  document.getElementById('stComp').textContent = STATE.completed;
  document.getElementById('stFail').textContent = STATE.failed;
  document.getElementById('fileLabel').textContent = STATE.workspaceFile;

  // Responsive Input Placeholder
  if (window.innerWidth >= 900) {
    const inp = document.getElementById('promptInput');
    if (inp) inp.placeholder = "Ask SRI Agent a question (Tamil / English)...";
  }

  if (STATE.previewHtml && (STATE.previewHtml.includes('<!DOCTYPE') || STATE.previewHtml.includes('<html')) && !STATE.previewHtml.includes('<iframe')) {
    const pIframe = document.createElement('iframe');
    pIframe.style.cssText = 'width:100%;height:100%;border:none;min-height:380px;border-radius:8px;background:#090B10;';
    pIframe.srcdoc = STATE.previewHtml;
    const pContainer = document.getElementById('panePreview');
    pContainer.innerHTML = '';
    pContainer.appendChild(pIframe);
  } else {
    document.getElementById('panePreview').innerHTML = STATE.previewHtml;
  }
  document.getElementById('paneCode').textContent = STATE.code;

  function switchTab(mode) {
    document.getElementById('tabPreview').classList.toggle('active', mode === 'preview');
    document.getElementById('tabCode').classList.toggle('active', mode === 'code');
    document.getElementById('panePreview').style.display = mode === 'preview' ? 'block' : 'none';
    document.getElementById('paneCode').style.display = mode === 'code' ? 'block' : 'none';
  }

  function setMobilePage(page) {
    const isProj = page === 'project';
    document.body.classList.toggle('show-project', isProj);
    const navHub = document.getElementById('navHub');
    const navProj = document.getElementById('navProj');
    if (navHub) navHub.classList.toggle('active', !isProj);
    if (navProj) navProj.classList.toggle('active', isProj);
  }

  function openBackendSettings() {
    try {
      const doc = window.parent.document;
      const sidebar = doc.querySelector('[data-testid="stSidebar"]') ||
                      doc.querySelector('section[data-testid="stSidebar"]');

      const isExpanded = sidebar && (
        sidebar.getAttribute('aria-expanded') === 'true' ||
        sidebar.classList.contains('stSidebar--expanded') ||
        (sidebar.offsetWidth > 60 && window.getComputedStyle(sidebar).transform === 'none')
      );

      const openBtn = doc.querySelector('[data-testid="collapsedControl"] button') ||
                      doc.querySelector('[data-testid="collapsedControl"]') ||
                      doc.querySelector('button[aria-label*="open sidebar" i]') ||
                      doc.querySelector('button[aria-label*="expand" i]');

      const closeBtn = doc.querySelector('[data-testid="stSidebarCollapseButton"] button') ||
                       doc.querySelector('[data-testid="stSidebarCollapseButton"]') ||
                       doc.querySelector('button[aria-label*="close sidebar" i]') ||
                       doc.querySelector('button[aria-label*="collapse" i]');

      if (isExpanded && closeBtn) {
        closeBtn.click();
        return;
      }
      if (openBtn) {
        openBtn.click();
        return;
      }
      if (closeBtn) {
        closeBtn.click();
        return;
      }

      const allButtons = doc.querySelectorAll('button');
      for (const b of allButtons) {
        const al = (b.getAttribute('aria-label') || '').toLowerCase();
        const tid = (b.getAttribute('data-testid') || '').toLowerCase();
        if (al.includes('sidebar') || tid.includes('sidebar') || tid.includes('collapse') || tid.includes('collapsed')) {
          b.click();
          return;
        }
      }
    } catch(e) {
      console.warn('Sidebar toggle error:', e);
    }
  }

  function submitPrompt() {
    const val = document.getElementById('promptInput').value.trim();
    if (!val) return;
    sendToPython(val);
  }

  function sendToPython(command) {
    if (!command || !command.trim()) return;
    const cleanCmd = command.trim();

    // 1. Silently update query params in parent URL history without triggering a reload
    try {
      const url = new URL(window.parent.location.href);
      url.searchParams.set('sri_cmd', cleanCmd);
      url.searchParams.set('ts', Date.now());
      window.parent.history.replaceState({}, '', url);
    } catch(e) {}

    // 2. ZERO-RELOAD STREAMLIT BRIDGE: Target the hidden st.text_input in window.parent.document
    try {
      const pDoc = window.parent.document;
      let bridgeInput = pDoc.querySelector('input[aria-label="sri_bridge_input"]');
      if (!bridgeInput) {
        const allInputs = pDoc.querySelectorAll('input[type="text"]');
        for (let inp of allInputs) {
          if (inp.getAttribute('aria-label') === 'sri_bridge_input' || (inp.id && inp.id.includes('sri_bridge_input'))) {
            bridgeInput = inp;
            break;
          }
        }
      }

      if (bridgeInput) {
        // Use React's native value setter so React state updates
        const nativeSetter = Object.getOwnPropertyDescriptor(window.parent.HTMLInputElement.prototype, 'value')?.set
          || Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set;
        if (nativeSetter) {
          nativeSetter.call(bridgeInput, cleanCmd);
        } else {
          bridgeInput.value = cleanCmd;
        }

        bridgeInput.dispatchEvent(new Event('input', { bubbles: true }));
        bridgeInput.dispatchEvent(new Event('change', { bubbles: true }));
        bridgeInput.dispatchEvent(new KeyboardEvent('keydown', { bubbles: true, cancelable: true, key: 'Enter', keyCode: 13, which: 13 }));
        bridgeInput.dispatchEvent(new KeyboardEvent('keyup', { bubbles: true, cancelable: true, key: 'Enter', keyCode: 13, which: 13 }));
        console.log('⚡ Dispatched command to Streamlit bridge in <1s:', cleanCmd);
        return;
      }
    } catch(err) {
      console.warn('Bridge input dispatch notice:', err);
    }

    // 3. Fallback only if parent access blocked or bridge element not found
    window.parent.location.reload();
  }

  // -------------------------------------------------------------
  // 8. UNIFIED CLIENT-SIDE TWO-WAY VOICE ENGINE
  // Center 3D Golden Sphere (canvas#sriOrb) & Bottom Inline Mic (#micBtn)
  // -------------------------------------------------------------
  let orbMode = 'IDLE'; // 'IDLE' | 'LISTENING' | 'PROCESSING' | 'SPEAKING'
  let isOrbListening = false;
  let inlineMicListening = false;
  let orbRecognition = null;
  let continuousVoiceLoop = sessionStorage.getItem('sri_continuous_voice') === '1';

  function onOrbClick() {
    if (continuousVoiceLoop || isOrbListening || inlineMicListening || orbMode === 'SPEAKING' || orbMode === 'PROCESSING') {
      stopAllVoiceSessions();
      return;
    }
    continuousVoiceLoop = true;
    sessionStorage.setItem('sri_continuous_voice', '1');
    startClientVoice();
  }

  function onMicClick() {
    if (inlineMicListening || isOrbListening || orbMode === 'SPEAKING' || orbMode === 'PROCESSING') {
      stopAllVoiceSessions();
      return;
    }
    startClientVoice();
  }

  function stopAllVoiceSessions() {
    continuousVoiceLoop = false;
    sessionStorage.removeItem('sri_continuous_voice');
    sessionStorage.removeItem('sri_pending_voice_reply');
    if (window.speechSynthesis) {
      try { window.speechSynthesis.cancel(); } catch(e) {}
    }
    stopListening();
    setOrbMode('IDLE');
    setInlineMicWaveformUI(false);
  }

  function stopListening() {
    isOrbListening = false;
    inlineMicListening = false;
    if (orbRecognition) {
      try { orbRecognition.abort(); } catch(e) {}
      orbRecognition = null;
    }
    setInlineMicWaveformUI(false);
  }

  function startClientVoice() {
    // 1. Never start speech recognition if speech synthesis is currently active to prevent echo self-listening
    if (window.speechSynthesis && (window.speechSynthesis.speaking || window.speechSynthesis.pending)) {
      console.warn('Speech synthesis currently active. Refusing recognition start to prevent echo.');
      return;
    }

    const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRec) {
      const hint = document.getElementById('orbHint');
      if (hint) hint.innerHTML = '<span style="color:#F59E0B;">🎙️ Speech recognition not supported on this browser. Type below.</span>';
      document.getElementById('promptInput').focus();
      return;
    }

    try {
      if (orbRecognition) {
        try { orbRecognition.abort(); } catch(e) {}
        orbRecognition = null;
      }
      orbRecognition = new SpeechRec();
      orbRecognition.continuous = false;
      orbRecognition.interimResults = true;
      orbRecognition.maxAlternatives = 1;
      orbRecognition.lang = 'en-IN'; // en-IN primary for accurate greetings/technical terms + Tamil support

      orbRecognition.onstart = () => {
        if (window.speechSynthesis && (window.speechSynthesis.speaking || window.speechSynthesis.pending)) {
          stopListening();
          setOrbMode('IDLE');
          return;
        }
        isOrbListening = true;
        inlineMicListening = true;
        setOrbMode('LISTENING');
        setInlineMicWaveformUI(true);
      };

      orbRecognition.onresult = (event) => {
        if (window.speechSynthesis && window.speechSynthesis.speaking) {
          console.warn('Ignoring speech recognition result while speaking.');
          return;
        }

        let interim = '';
        let finalTranscript = '';
        for (let i = event.resultIndex; i < event.results.length; ++i) {
          if (event.results[i].isFinal) {
            finalTranscript += event.results[i][0].transcript;
          } else {
            interim += event.results[i][0].transcript;
          }
        }
        const current = finalTranscript || interim;
        if (current) {
          document.getElementById('promptInput').value = current;
        }

        if (finalTranscript && finalTranscript.trim()) {
          stopListening();
          handleTwoWayVoiceTurn(finalTranscript.trim());
        }
      };

      orbRecognition.onerror = (event) => {
        console.warn('Speech recognition notice:', event.error);
        stopListening();
        if (!continuousVoiceLoop) {
          setOrbMode('IDLE');
        }
      };

      orbRecognition.onend = () => {
        if (isOrbListening || inlineMicListening) {
          stopListening();
          const val = document.getElementById('promptInput').value.trim();
          if (val) {
            handleTwoWayVoiceTurn(val);
          } else if (!continuousVoiceLoop) {
            setOrbMode('IDLE');
          }
        }
      };

      orbRecognition.start();
    } catch(err) {
      console.error('Failed to start voice session:', err);
      stopListening();
      setOrbMode('IDLE');
    }
  }
  window.startClientVoice = startClientVoice;

  function setInlineMicWaveformUI(active) {
    const wave = document.getElementById('chatWaveform');
    const micBtn = document.getElementById('micBtn');
    const inp = document.getElementById('promptInput');
    if (active) {
      if (wave) wave.classList.add('active');
      if (micBtn) {
        micBtn.style.borderColor = '#F59E0B';
        micBtn.style.boxShadow = '0 0 16px rgba(245,158,11,0.7)';
        micBtn.style.color = '#FBBF24';
        micBtn.style.background = '#1F1A12';
      }
      if (inp) {
        inp.placeholder = "Listening in Tamil / English...";
      }
    } else {
      if (wave) wave.classList.remove('active');
      if (micBtn) {
        micBtn.style.borderColor = '#27272A';
        micBtn.style.boxShadow = 'none';
        micBtn.style.color = '#F59E0B';
        micBtn.style.background = '#14171F';
      }
      if (inp) {
        inp.placeholder = window.innerWidth >= 900 ? "Ask SRI Agent a question (Tamil / English)..." : "Message SRI...";
      }
    }
  }

  function handleTwoWayVoiceTurn(spokenText) {
    if (!spokenText || !spokenText.trim()) {
      setOrbMode('IDLE');
      setInlineMicWaveformUI(false);
      return;
    }

    const clean = spokenText.trim();
    setOrbMode('PROCESSING');
    setInlineMicWaveformUI(false);
    sessionStorage.setItem('sri_pending_voice_reply', '1');
    sessionStorage.setItem('sri_continuous_voice', '1');
    sendToPython(clean);
  }

  function speakVoiceReply(text, onComplete) {
    if (!text || !text.trim()) {
      if (onComplete) onComplete();
      return;
    }

    // 1. CRITICAL: Explicitly abort ALL active speech recognition instances before speech starts to prevent echo self-listening
    stopListening();

    if (!window.speechSynthesis) {
      if (onComplete) onComplete();
      return;
    }

    try {
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(text.trim());
      const isTamil = /[\u0B80-\u0BFF]/.test(text);

      // Warm, natural voice tuning: rate=1.02, pitch=1.0
      utterance.rate = 1.02;
      utterance.pitch = 1.0;

      // Select warm Indian English / Neural voice
      const voices = (window.speechSynthesis && window.speechSynthesis.getVoices()) || [];
      let selectedVoice = null;
      if (isTamil) {
        selectedVoice = voices.find(v => v.lang && (v.lang === 'ta-IN' || v.lang.startsWith('ta')))
          || voices.find(v => v.name && v.name.toLowerCase().includes('tamil'));
      }
      if (!selectedVoice) {
        selectedVoice = voices.find(v => (v.lang === 'en-IN' || v.lang === 'en_IN') && (v.name.includes('Natural') || v.name.includes('Neural') || v.name.includes('Google') || v.name.includes('Online')))
          || voices.find(v => v.lang === 'en-IN' || v.lang === 'en_IN')
          || voices.find(v => v.name && (v.name.toLowerCase().includes('india') || v.name.toLowerCase().includes('heera') || v.name.toLowerCase().includes('neerja') || v.name.toLowerCase().includes('ravi') || v.name.toLowerCase().includes('prabhat')))
          || voices.find(v => v.lang && v.lang.startsWith('en') && (v.name.includes('Natural') || v.name.includes('Neural')))
          || voices.find(v => v.lang && v.lang.startsWith('en'));
      }

      if (selectedVoice) {
        utterance.voice = selectedVoice;
        utterance.lang = selectedVoice.lang || (isTamil ? 'ta-IN' : 'en-IN');
      } else {
        utterance.lang = isTamil ? 'ta-IN' : 'en-IN';
      }

      setOrbMode('SPEAKING');

      let completed = false;
      const finishTTS = () => {
        if (completed) return;
        completed = true;
        setOrbMode('IDLE');
        // Restart only after a 450ms buffer delay so SRI never catches its own voice echo
        setTimeout(() => {
          if (onComplete) onComplete();
        }, 450);
      };

      utterance.onend = finishTTS;
      utterance.onerror = (e) => {
        console.warn('Speech synthesis notice:', e);
        finishTTS();
      };

      window.speechSynthesis.speak(utterance);
    } catch(err) {
      console.warn('TTS error:', err);
      setOrbMode('IDLE');
      setTimeout(() => {
        if (onComplete) onComplete();
      }, 450);
    }
  }

  // Hook voiceschanged so voices are immediately cached
  if (window.speechSynthesis) {
    window.speechSynthesis.onvoiceschanged = () => {
      window.speechSynthesis.getVoices();
    };
  }

  function setOrbMode(mode) {
    orbMode = mode;
    const hint = document.getElementById('orbHint');
    if (!hint) return;

    if (mode === 'LISTENING') {
      const stopText = continuousVoiceLoop ? 'Tap sphere to stop' : 'English / Tamil';
      hint.innerHTML = `<span style="color:#F59E0B;font-weight:600;display:inline-flex;align-items:center;gap:6px;"><span class="dot-gold" style="animation:pulseDot 0.8s infinite alternate;"></span> 🎙️ Listening... (${stopText})</span>`;
    } else if (mode === 'PROCESSING') {
      hint.innerHTML = '<span style="color:#F59E0B;font-weight:600;display:inline-flex;align-items:center;gap:6px;"><span class="dot-gold" style="animation:pulseDot 0.5s infinite alternate;"></span> ⚡ Thinking... (SRI AI)</span>';
    } else if (mode === 'SPEAKING') {
      const stopText = continuousVoiceLoop ? 'Tap sphere to stop' : 'Live Agent';
      hint.innerHTML = `<span style="color:#10B981;font-weight:600;display:inline-flex;align-items:center;gap:6px;"><span class="dot-green" style="animation:pulseDot 0.8s infinite alternate;"></span> 🔊 Speaking... (${stopText})</span>`;
    } else {
      hint.innerHTML = 'Tap the golden sphere to talk with SRI in Tamil or English';
    }
  }

  // Proactively speak back newly returned executive agent response from LLM
  // And if continuousVoiceLoop is active, automatically re-trigger listening once speaking completes!
  try {
    if (sessionStorage.getItem('sri_pending_voice_reply') === '1') {
      sessionStorage.removeItem('sri_pending_voice_reply');
      if (STATE.messages && STATE.messages.length > 0) {
        const last = STATE.messages[STATE.messages.length - 1];
        if (last && last.agent) {
          setTimeout(() => {
            speakVoiceReply(last.agent, () => {
              if (continuousVoiceLoop) {
                startClientVoice();
              }
            });
          }, 100);
        }
      }
    }
  } catch(e) {}

  // -------------------------------------------------------------
  // Floating Background Particles & Silk Wave Animation
  // -------------------------------------------------------------
  const bgCanvas = document.getElementById('bgParticles');
  if (bgCanvas) {
    const bgCtx = bgCanvas.getContext('2d');
    let bgW = bgCanvas.width = window.innerWidth;
    let bgH = bgCanvas.height = window.innerHeight;
    window.addEventListener('resize', () => {
      bgW = bgCanvas.width = window.innerWidth;
      bgH = bgCanvas.height = window.innerHeight;
    });
    const embers = Array.from({length: 45}, () => ({
      x: Math.random() * bgW,
      y: Math.random() * bgH,
      r: Math.random() * 2.2 + 0.6,
      vy: -(Math.random() * 0.45 + 0.15),
      vx: (Math.random() - 0.5) * 0.2,
      a: Math.random() * 0.6 + 0.2,
      color: ['#F59E0B', '#D97706', '#FBBF24'][Math.floor(Math.random() * 3)]
    }));
    let waveT = 0;
    function renderBg() {
      bgCtx.clearRect(0, 0, bgW, bgH);
      waveT += 0.008;
      bgCtx.beginPath();
      for (let x = 0; x <= bgW; x += 12) {
        const y = bgH * 0.72 + Math.sin(x * 0.003 + waveT) * 35 + Math.cos(x * 0.002 + waveT * 0.7) * 20;
        if (x === 0) bgCtx.moveTo(x, y); else bgCtx.lineTo(x, y);
      }
      bgCtx.strokeStyle = 'rgba(245, 158, 11, 0.035)';
      bgCtx.lineWidth = 45;
      bgCtx.stroke();

      embers.forEach(p => {
        p.y += p.vy;
        p.x += p.vx;
        if (p.y < -10) { p.y = bgH + 10; p.x = Math.random() * bgW; }
        if (p.x < 0) p.x = bgW;
        if (p.x > bgW) p.x = 0;
        bgCtx.beginPath();
        bgCtx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        bgCtx.fillStyle = p.color;
        bgCtx.globalAlpha = p.a;
        bgCtx.fill();
        bgCtx.globalAlpha = 1.0;
      });
      requestAnimationFrame(renderBg);
    }
    renderBg();
  }

  // -------------------------------------------------------------
  // 3D Golden Orb Canvas (Live Pulse on Voice Listening)
  // -------------------------------------------------------------
  const canvas = document.getElementById('sriOrb');
  const ctx = canvas.getContext('2d');
  const dpr = window.devicePixelRatio || 1;
  let t = 0;

  const pts = Array.from({length: 1000}, () => {
    const u = Math.random(), v = Math.random();
    const th = 2 * Math.PI * u, ph = Math.acos(2 * v - 1);
    return { th, ph, r: 1, s: Math.random() * 1.4 + 0.35 };
  });

  function renderOrb() {
    const W = canvas.clientWidth || 380;
    const H = 280;
    if (canvas.width !== W * dpr) {
      canvas.width = W * dpr; canvas.height = H * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }
    ctx.clearRect(0, 0, W, H);
    const isMob = window.innerWidth < 900;
    const R = isMob ? 64 : 88;
    const cx = W / 2, cy = H / 2;
    const isListening = orbMode === 'LISTENING';
    const isSpeaking = orbMode === 'SPEAKING';
    const isActive = isListening || isSpeaking;
    t += isSpeaking ? 0.048 : (isListening ? 0.038 : 0.015);

    // Ambient Radial Halo (Vibrant pulse on Listening, Emerald/Gold on Speaking)
    const haloRadius = R * (isSpeaking ? 1.85 : (isListening ? 1.75 : 1.55));
    const g = ctx.createRadialGradient(cx, cy, 8, cx, cy, haloRadius);
    if (isSpeaking) {
      g.addColorStop(0, 'rgba(16,185,129,0.52)');
      g.addColorStop(0.45, 'rgba(245,158,11,0.36)');
      g.addColorStop(1, 'rgba(6,7,9,0)');
    } else if (isListening) {
      g.addColorStop(0, 'rgba(245,158,11,0.58)');
      g.addColorStop(1, 'rgba(6,7,9,0)');
    } else {
      g.addColorStop(0, 'rgba(245,158,11,0.34)');
      g.addColorStop(1, 'rgba(6,7,9,0)');
    }
    ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);

    if (isMob) {
      // Mobile: 17 Full-Bleed Golden Sine-Wave Ribbons
      for (let i = 0; i < 17; i++) {
        ctx.beginPath();
        const phase = i * 0.22;
        const waveSpeed = isSpeaking ? 3.0 : (isListening ? 2.2 : 1.3);
        const waveAmp = 25 + i * (isSpeaking ? 2.1 : 1.55);
        for (let x = 0; x <= W; x += 2) {
          const edgeFade = Math.sin((x / W) * Math.PI);
          const y = cy + Math.sin(x * 0.018 + t * waveSpeed + phase) * waveAmp * edgeFade;
          if (x === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
        }
        ctx.strokeStyle = isSpeaking ?
          `rgba(16, 185, 129, ${0.08 + (i / 17) * 0.26})` :
          `rgba(245, 158, 11, ${0.06 + (i / 17) * 0.24})`;
        ctx.lineWidth = isSpeaking ? 1.25 : 1.05;
        ctx.stroke();
      }
    } else {
      // Desktop: 2 Intersecting Golden Orbits
      [-0.52, 0.52].forEach((tilt, idx) => {
        ctx.save(); ctx.translate(cx, cy); ctx.rotate(tilt);
        ctx.beginPath(); ctx.ellipse(0, 0, R * 1.58, R * 0.62, 0, 0, Math.PI * 2);
        ctx.strokeStyle = isSpeaking ? 'rgba(16,185,129,0.85)' : (isListening ? 'rgba(245,158,11,0.85)' : 'rgba(245,158,11,0.48)');
        ctx.lineWidth = 1.2; ctx.stroke();
        const da = t * (idx === 0 ? 1.1 : -0.9);
        ctx.beginPath(); ctx.arc(Math.cos(da)*R*1.58, Math.sin(da)*R*0.62, 2.5, 0, Math.PI*2);
        ctx.fillStyle = isSpeaking ? '#A7F3D0' : '#FDE68A'; ctx.fill();
        ctx.restore();
      });
    }

    pts.forEach(p => {
      const th = p.th + t * (isSpeaking ? 1.1 : (isListening ? 0.9 : 0.45));
      const rad = R * (0.9 + (p.s * 0.06));
      const x3 = rad * Math.sin(p.ph) * Math.cos(th);
      const y3 = rad * Math.cos(p.ph);
      const z3 = rad * Math.sin(p.ph) * Math.sin(th);
      const a = (z3 + R) / (2 * R);
      ctx.beginPath(); ctx.arc(cx + x3, cy + y3, p.s, 0, Math.PI * 2);
      ctx.fillStyle = isSpeaking ?
        `rgba(167,243,208,${0.2 + a * 0.8})` :
        `rgba(251,191,36,${0.16 + a * 0.84})`;
      ctx.fill();
    });

    const sp = ctx.createRadialGradient(cx - R*0.35, cy - R*0.35, 2, cx - R*0.35, cy - R*0.35, R*0.42);
    sp.addColorStop(0, isSpeaking ? 'rgba(240,253,244,0.92)' : 'rgba(255,251,235,0.88)');
    sp.addColorStop(1, isSpeaking ? 'rgba(16,185,129,0)' : 'rgba(245,158,11,0)');
    ctx.fillStyle = sp; ctx.beginPath(); ctx.arc(cx - R*0.35, cy - R*0.35, R*0.42, 0, Math.PI*2); ctx.fill();

    if (isMob) {
      ctx.save(); ctx.translate(cx, cy); ctx.rotate(-0.42);
      ctx.beginPath(); ctx.ellipse(0, 0, R * 1.38, R * 0.52, 0, 0, Math.PI * 2);
      ctx.strokeStyle = isSpeaking ? 'rgba(167,243,208,0.92)' : (isListening ? 'rgba(253,230,138,0.9)' : 'rgba(253,230,138,0.55)');
      ctx.lineWidth = 1.2; ctx.stroke();
      ctx.restore();
    } else {
      ctx.beginPath(); ctx.arc(cx, cy, 26, 0, Math.PI * 2);
      ctx.fillStyle = 'rgba(14,14,18,0.9)'; ctx.fill();
      ctx.strokeStyle = isSpeaking ? '#10B981' : (isListening ? '#F59E0B' : 'rgba(245,158,11,0.4)'); ctx.lineWidth = 1; ctx.stroke();
      ctx.fillStyle = isSpeaking ? '#10B981' : (isListening ? '#F59E0B' : '#E5D3B3');
      ctx.beginPath(); ctx.roundRect(cx - 4.5, cy - 11, 9, 14, 4.5); ctx.fill();
      ctx.strokeStyle = isSpeaking ? '#10B981' : (isListening ? '#F59E0B' : '#E5D3B3'); ctx.lineWidth = 1.8;
      ctx.beginPath(); ctx.arc(cx, cy - 2, 8, 0.1*Math.PI, 0.9*Math.PI); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(cx, cy + 6); ctx.lineTo(cx, cy + 11); ctx.stroke();
    }
    requestAnimationFrame(renderOrb);
  }
  renderOrb();
</script>
</body>
</html>"""
    rendered_html = html_template.replace("__STATE_PAYLOAD__", state_payload)
    components.html(rendered_html, height=900, scrolling=False)
