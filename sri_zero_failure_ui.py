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
    if chat_history is None:
        chat_history = []

    st.markdown("""
    <style>
    html, body, [data-testid="stAppViewContainer"], [data-testid="stApp"], .main {
        background-color: #060709 !important;
        margin: 0 !important;
        padding: 0 !important;
        overflow: hidden !important;
    }
    [data-testid="stToolbar"], [data-testid="stDecoration"], #MainMenu, footer, [data-testid="stHeader"] {
        display: none !important;
    }
    .block-container {
        padding: 0 !important;
        margin: 0 !important;
        max-width: 100vw !important;
    }
    [data-testid="stSidebar"] {
        background-color: #090B0E !important;
        border-left: 1px solid rgba(245, 158, 11, 0.35) !important;
        z-index: 99999 !important;
    }
    iframe {
        display: block !important;
        border: none !important;
        width: 100vw !important;
        height: 100vh !important;
    }
    </style>
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
    -webkit-tap-highlight-color: transparent;
    outline: none;
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
  }}

  /* Top Header */
  .topbar {{
    height: 58px;
    padding: 0 18px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-shrink: 0;
  }}
  .brand {{
    font-family: 'Playfair Display', serif;
    font-size: 22px;
    font-weight: 700;
    color: #F5E6C8;
  }}
  .brand span {{ color: #F59E0B; }}
  .right-controls {{ display: flex; align-items: center; gap: 10px; }}
  .status-pill {{
    background: #0B1312;
    border: 1px solid rgba(16, 185, 129, 0.35);
    border-radius: 999px;
    padding: 5px 12px;
    font-size: 11.5px;
    color: #34D399;
    display: flex;
    align-items: center;
    gap: 6px;
    font-weight: 500;
  }}
  .dot-green {{
    width: 6px; height: 6px; border-radius: 50%;
    background: #10B981; box-shadow: 0 0 8px #10B981;
  }}
  .gear-btn {{
    width: 34px; height: 34px;
    background: #111318;
    border: 1px solid #242832;
    color: #9CA3AF;
    border-radius: 50%;
    font-size: 15px;
    cursor: pointer;
    display: flex; align-items: center; justify-content: center;
  }}

  /* Welcome Kirubha + Latest Work Row (Mobile & Subheader) */
  .welcome-row {{
    padding: 4px 18px 8px 18px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-shrink: 0;
  }}
  .welcome-sub {{ color: #D97706; font-size: 12px; font-weight: 500; }}
  .welcome-name {{ color: #FFFFFF; font-size: 22px; font-weight: 700; letter-spacing: -0.3px; }}
  .latest-btn {{
    background: rgba(245, 158, 11, 0.08);
    border: 1px solid rgba(245, 158, 11, 0.4);
    color: #D97706;
    border-radius: 999px;
    padding: 6px 14px;
    font-size: 11.5px;
    font-weight: 500;
    cursor: pointer;
  }}

  /* Main Layout */
  .main-grid {{
    flex: 1;
    display: grid;
    grid-template-columns: 270px 1fr 390px;
    gap: 18px;
    padding: 12px 22px;
    overflow: hidden;
  }}
  .left-col {{
    display: flex; flex-direction: column; justify-content: space-between;
  }}
  .stat-row {{
    display: flex; justify-content: space-between; padding: 10px 0;
    border-bottom: 1px solid #181B22; font-size: 13.5px; color: #9CA3AF;
  }}
  .gold-val {{ color: #F59E0B; font-weight: 600; }}

  /* Center Orb & Bottom Controls */
  .center-col {{
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: space-between;
    overflow: hidden;
  }}
  .orb-wrap {{
    flex: 1;
    width: 100%;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
  }}
  canvas#sriOrb {{
    width: 100%;
    height: 270px;
    cursor: pointer;
    user-select: none;
  }}
  .orb-hint {{
    font-size: 12px;
    color: #71717A;
    margin-top: 6px;
    text-align: center;
  }}
  .orb-hint.listening {{
    color: #F59E0B;
    font-weight: 600;
  }}

  /* Horizontal Action Pills */
  .pills-row {{
    display: flex;
    flex-direction: row;
    flex-wrap: nowrap;
    gap: 8px;
    width: 100%;
    overflow-x: auto;
    padding: 6px 0;
    justify-content: center;
    scrollbar-width: none;
  }}
  .pills-row::-webkit-scrollbar {{ display: none; }}
  .pill-btn {{
    flex: 0 0 auto;
    background: #0C0E12;
    border: 1px solid #222630;
    color: #D4D4D8;
    border-radius: 999px;
    padding: 7px 14px;
    font-size: 12px;
    cursor: pointer;
    white-space: nowrap;
  }}
  .pill-btn:first-child {{
    border-color: rgba(245, 158, 11, 0.55);
    color: #F59E0B;
  }}

  /* Unified Chat Bar */
  .chat-bar {{
    width: 100%;
    background: #0C0E12;
    border: 1px solid #222630;
    border-radius: 999px;
    display: flex;
    align-items: center;
    padding: 5px 6px 5px 16px;
    gap: 8px;
    margin-top: 6px;
  }}
  .chat-bar input {{
    flex: 1;
    background: transparent;
    border: none;
    color: #FFF;
    font-size: 13.5px;
  }}
  .mic-inline {{
    background: transparent;
    border: none;
    color: #9CA3AF;
    font-size: 16px;
    cursor: pointer;
    padding: 4px 6px;
  }}
  .send-circle {{
    width: 34px; height: 34px;
    border-radius: 50%;
    background: #F59E0B;
    color: #060709;
    border: none;
    font-weight: 700;
    font-size: 14px;
    cursor: pointer;
    display: flex; align-items: center; justify-content: center;
  }}

  /* Right Glass Panel */
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
    cursor: pointer;
  }}
  .seg-tab.active {{
    background: #141821; border: 1px solid #F59E0B; color: #FFF; font-weight: 600;
  }}
  .workspace-pane {{
    flex: 1; background: #060709; border: 1px solid #181B22;
    border-radius: 12px; overflow: auto; padding: 12px;
    font-family: 'JetBrains Mono', monospace; font-size: 12px; color: #E5E7EB;
  }}

  /* Bottom 2-Pill Switcher (Matching 1000102295.jpg) */
  .mob-nav {{ display: none; }}

  @media (max-width: 900px) {{
    .main-grid {{
      display: flex;
      flex-direction: column;
      padding: 4px 16px 8px 16px;
    }}
    .left-col {{ display: none !important; }}
    .pills-row {{ justify-content: flex-start; }}
    .right-col {{ display: none; flex: 1; }}
    body.show-project .center-col {{ display: none; }}
    body.show-project .right-col {{ display: flex; }}

    .mob-nav {{
      display: flex;
      justify-content: center;
      align-items: center;
      gap: 12px;
      padding: 8px 16px 18px 16px;
      flex-shrink: 0;
    }}
    .mob-pill {{
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
    }}
    .mob-pill.active {{
      background: #F59E0B;
      color: #060709;
      border-color: #F59E0B;
    }}
  }}
</style>
</head>
<body>
  <div class="topbar">
    <div class="brand">SRI AI<span>.</span></div>
    <div class="right-controls">
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
        <canvas id="sriOrb" onclick="startClientVoice()"></canvas>
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
          <input id="promptInput" type="text" placeholder="Message SRI..." onkeydown="if(event.key==='Enter') submitPrompt()">
          <button class="mic-inline" onclick="startClientVoice()">🎙️</button>
          <button class="send-circle" onclick="submitPrompt()">➤</button>
        </div>
      </div>
    </div>

    <div class="right-col">
      <div class="seg-tabs">
        <div class="seg-tab active" id="tabPreview" onclick="switchTab('preview')">Preview</div>
        <div class="seg-tab" id="tabCode" onclick="switchTab('code')">Code</div>
      </div>
      <div style="font-size:11px;color:#71717A;margin-bottom:8px;font-family:'JetBrains Mono',monospace;" id="fileLabel">workspace/login.html</div>
      <div class="workspace-pane" id="panePreview"></div>
      <pre class="workspace-pane" id="paneCode" style="display:none;white-space:pre-wrap;"></pre>
    </div>
  </div>

  <div class="mob-nav">
    <div class="mob-pill active" id="navHub" onclick="setMobilePage('hub')">✦ Agent Hub</div>
    <div class="mob-pill" id="navProj" onclick="setMobilePage('project')">👁️ Project View</div>
  </div>

<script>
  const STATE = {state_payload};
  document.getElementById('stAgent').textContent = '● ' + STATE.agentStatus;
  document.getElementById('stActive').textContent = STATE.activeTasks;
  document.getElementById('stComp').textContent = STATE.completed;
  document.getElementById('stFail').textContent = STATE.failed;
  document.getElementById('fileLabel').textContent = STATE.workspaceFile;
  document.getElementById('panePreview').innerHTML = STATE.previewHtml;
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
    const btn = window.parent.document.querySelector('[data-testid="collapsedControl"] button, [data-testid="collapsedControl"]');
    if (btn) btn.click();
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

  // Client-Side Web Speech API (No Blank Black Reload or Mic Timeout!)
  let isListening = false;
  function startClientVoice() {{
    const hint = document.getElementById('orbHint');
    const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRec) {{
      hint.textContent = "Type your message below or use Chrome voice keyboard";
      document.getElementById('promptInput').focus();
      return;
    }}
    if (isListening) return;
    const rec = new SpeechRec();
    rec.lang = 'ta-IN';
    rec.interimResults = true;
    isListening = true;
    hint.textContent = "Listening... Speak in Tamil or English";
    hint.classList.add('listening');

    rec.onresult = (e) => {{
      const transcript = Array.from(e.results).map(r => r[0].transcript).join('');
      document.getElementById('promptInput').value = transcript;
      if (e.results[0].isFinal) {{
        isListening = false;
        hint.classList.remove('listening');
        sendToPython(transcript);
      }}
    }};
    rec.onerror = () => {{
      isListening = false;
      hint.classList.remove('listening');
      hint.textContent = "Tap the golden sphere to talk with SRI in Tamil or English";
    }};
    rec.onend = () => {{
      isListening = false;
      hint.classList.remove('listening');
    }};
    rec.start();
  }}

  // 3D Golden Orb Canvas
  const canvas = document.getElementById('sriOrb');
  const ctx = canvas.getContext('2d');
  const dpr = window.devicePixelRatio || 1;
  let t = 0;

  const pts = Array.from({{length: 1100}}, () => {{
    const u = Math.random(), v = Math.random();
    const th = 2 * Math.PI * u, ph = Math.acos(2 * v - 1);
    return {{ th, ph, s: Math.random() * 1.45 + 0.35 }};
  }});

  function renderOrb() {{
    const W = canvas.clientWidth || 380;
    const H = 270;
    if (canvas.width !== W * dpr) {{
      canvas.width = W * dpr; canvas.height = H * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }}
    ctx.clearRect(0, 0, W, H);
    const isMob = window.innerWidth < 900;
    const R = isMob ? 66 : 88;
    const cx = W / 2, cy = H / 2;
    t += isListening ? 0.04 : 0.015;

    const g = ctx.createRadialGradient(cx, cy, 8, cx, cy, R * 1.6);
    g.addColorStop(0, isListening ? 'rgba(251,191,36,0.5)' : 'rgba(245,158,11,0.34)');
    g.addColorStop(1, 'rgba(6,7,9,0)');
    ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);

    if (isMob) {{
      for (let i = 0; i < 17; i++) {{
        ctx.beginPath();
        const phase = i * 0.22;
        for (let x = 0; x <= W; x += 2) {{
          const edgeFade = Math.sin((x / W) * Math.PI);
          const amp = isListening ? (36 + i * 2) : (25 + i * 1.55);
          const y = cy + Math.sin(x * 0.018 + t * 1.3 + phase) * amp * edgeFade;
          if (x === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
        }}
        ctx.strokeStyle = `rgba(245, 158, 11, ${{0.06 + (i / 17) * 0.25}})`;
        ctx.lineWidth = 1.05; ctx.stroke();
      }}
    }} else {{
      [-0.52, 0.52].forEach((tilt, idx) => {{
        ctx.save(); ctx.translate(cx, cy); ctx.rotate(tilt);
        ctx.beginPath(); ctx.ellipse(0, 0, R * 1.58, R * 0.62, 0, 0, Math.PI * 2);
        ctx.strokeStyle = 'rgba(245,158,11,0.48)'; ctx.lineWidth = 1.2; ctx.stroke();
        const da = t * (idx === 0 ? 1.1 : -0.9);
        ctx.beginPath(); ctx.arc(Math.cos(da)*R*1.58, Math.sin(da)*R*0.62, 2.5, 0, Math.PI*2);
        ctx.fillStyle = '#FDE68A'; ctx.fill();
        ctx.restore();
      }});
    }}

    pts.forEach(p => {{
      const th = p.th + t * 0.45;
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
      ctx.strokeStyle = 'rgba(253,230,138,0.55)'; ctx.lineWidth = 1.2; ctx.stroke();
      ctx.restore();
    }} else {{
      ctx.beginPath(); ctx.arc(cx, cy, 26, 0, Math.PI * 2);
      ctx.fillStyle = 'rgba(14,14,18,0.9)'; ctx.fill();
      ctx.strokeStyle = 'rgba(245,158,11,0.4)'; ctx.lineWidth = 1; ctx.stroke();
      ctx.fillStyle = '#E5D3B3';
      ctx.beginPath(); ctx.roundRect(cx - 4.5, cy - 11, 9, 14, 4.5); ctx.fill();
      ctx.strokeStyle = '#E5D3B3'; ctx.lineWidth = 1.8;
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
