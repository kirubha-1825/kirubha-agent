import streamlit as st
import streamlit.components.v1 as components

def inject_sri_ui_and_particles():
    """
    Injects the exact Obsidian & Tiger-Gold UI (Desktop 3-Zone + Mobile 2-Page View),
    styles the 7-section Control Drawer (st.sidebar), and mounts the ambient particles.
    """
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Playfair+Display:wght@500;600;700&display=swap');

    /* 1. Pure Obsidian Canvas (#060709) */
    html, body, [data-testid="stAppViewContainer"], [data-testid="stApp"], .main {
        background-color: #060709 !important;
        color: #F4F4F5 !important;
        font-family: 'Inter', sans-serif !important;
    }

    /* Hide Streamlit chrome while keeping Sidebar Toggle styled as Control Drawer */
    [data-testid="stToolbar"], [data-testid="stDecoration"], #MainMenu, footer {
        display: none !important;
    }
    [data-testid="stHeader"] {
        background: transparent !important;
        height: 68px !important;
        z-index: 9990 !important;
    }

    /* Style Sidebar Toggle Button as Top-Right ⚙️ Control Drawer */
    [data-testid="collapsedControl"] {
        position: fixed !important;
        top: 14px !important;
        right: 24px !important;
        left: auto !important;
        z-index: 10001 !important;
        background: #0C0E12 !important;
        border: 1px solid rgba(245, 158, 11, 0.55) !important;
        border-radius: 999px !important;
        padding: 6px 16px !important;
        color: #F59E0B !important;
        width: auto !important;
        height: 38px !important;
        display: flex !important;
        align-items: center !important;
        gap: 8px !important;
        box-shadow: 0 0 18px rgba(245, 158, 11, 0.15) !important;
    }
    [data-testid="collapsedControl"]::after {
        content: "⚙️ Control Drawer";
        font-size: 13px;
        font-weight: 500;
        color: #F59E0B;
        white-space: nowrap;
    }
    [data-testid="collapsedControl"] svg { fill: #F59E0B !important; }

    /* Style 7-Section Control Drawer (Sidebar) */
    [data-testid="stSidebar"] {
        background-color: #090B0E !important;
        border-left: 1px solid rgba(245, 158, 11, 0.3) !important;
        z-index: 10005 !important;
    }
    [data-testid="stSidebar"] [data-testid="stExpander"] {
        background: #0D1015 !important;
        border: 1px solid #1E222B !important;
        border-radius: 12px !important;
        margin-bottom: 8px !important;
    }

    /* Locked Top Sticky Header */
    .sri-header {
        position: fixed; top: 0; left: 0; right: 0; height: 68px;
        background: rgba(6, 7, 9, 0.94);
        backdrop-filter: blur(16px);
        border-bottom: 1px solid #1E222B;
        display: flex; align-items: center; justify-content: space-between;
        padding: 0 28px; z-index: 9985;
    }
    .sri-brand {
        font-family: 'Playfair Display', serif;
        font-size: 24px; font-weight: 700; color: #F5E6C8;
    }
    .sri-brand span { color: #F59E0B; }
    .sri-pill-status {
        background: #0C0E12; border: 1px solid rgba(245, 158, 11, 0.35);
        border-radius: 999px; padding: 6px 18px; font-size: 13px; color: #D4D4D8;
        display: flex; align-items: center; gap: 8px;
    }
    .dot-gold {
        width: 8px; height: 8px; border-radius: 50%;
        background: #F59E0B; box-shadow: 0 0 8px #F59E0B;
    }

    .block-container {
        padding-top: 82px !important;
        padding-bottom: 14px !important;
        max-width: 100% !important;
    }

    /* Editorial Left Metrics */
    .greet-gold { color: #D97706; font-size: 15px; margin-bottom: 2px; }
    .hero-serif { font-family: 'Playfair Display', serif; font-size: 36px; color: #FFF; margin-bottom: 18px; }
    .stat-line {
        display: flex; justify-content: space-between; padding: 11px 0;
        border-bottom: 1px solid #1A1D24; font-size: 14px; color: #9CA3AF;
    }
    .gold-txt { color: #F59E0B !important; font-weight: 600 !important; }

    /* Right Glass Card for [ Preview | Code ] */
    div[data-testid="column"]:nth-of-type(3) > div {
        background: #0A0C10 !important;
        border: 1px solid rgba(245, 158, 11, 0.28) !important;
        border-radius: 20px !important;
        padding: 16px !important;
    }

    /* Clean [ Preview | Code ] Toggle without Red Radio Dots */
    [data-testid="stRadio"] input[type="radio"],
    [data-testid="stRadio"] div[role="radiogroup"] label > div:first-child {
        display: none !important;
    }
    [data-testid="stRadio"] div[role="radiogroup"] {
        display: flex !important; background: #060709 !important;
        border: 1px solid #1E222B !important; border-radius: 999px !important; padding: 4px !important;
    }
    [data-testid="stRadio"] div[role="radiogroup"] label {
        flex: 1 !important; justify-content: center !important; border-radius: 999px !important;
        padding: 6px 12px !important; color: #9CA3AF !important;
    }
    [data-testid="stRadio"] div[role="radiogroup"] label:has(input:checked) {
        background: #12151C !important; border: 1px solid #F59E0B !important; color: #FFF !important;
    }

    /* Dark Prompt Input & Non-Truncated Pills */
    [data-testid="stTextInput"] input {
        background: #0C0E12 !important; border: 1px solid rgba(245, 158, 11, 0.4) !important;
        border-radius: 999px !important; color: #FFF !important; padding: 12px 18px !important;
    }
    .stButton > button {
        background: #0C0E12 !important; border: 1px solid #1E222B !important;
        border-radius: 999px !important; color: #E5E7EB !important;
        font-size: 12px !important; white-space: nowrap !important;
    }
    .stButton > button:hover { border-color: #F59E0B !important; color: #F59E0B !important; }

    /* Mobile (< 900px): Hide desktop telemetry on home screen (accessible in Control Drawer) */
    @media (max-width: 900px) {
        .sri-pill-status { display: none !important; }
        div[data-testid="column"]:nth-of-type(1) { display: none !important; }
        [data-testid="collapsedControl"]::after { content: "⚙️"; }
    }
    </style>

    <div class="sri-header">
        <div class="sri-brand">SRI AI<span>.</span></div>
        <div class="sri-pill-status"><span class="dot-gold"></span> 98.4% Agent Active</div>
        <div style="width: 170px;"></div>
    </div>
    """, unsafe_allow_html=True)

    # Floating Gold Bokeh Canvas
    components.html("""
    <script>
    const doc = window.parent.document;
    if (!doc.getElementById('sri-particles')) {
        const c = doc.createElement('canvas');
        c.id = 'sri-particles';
        c.style.cssText = 'position:fixed;inset:0;width:100vw;height:100vh;pointer-events:none;z-index:0;';
        doc.body.prepend(c);
        const ctx = c.getContext('2d');
        let w = c.width = window.parent.innerWidth, h = c.height = window.parent.innerHeight;
        const pts = Array.from({length: 50}, () => ({
            x: Math.random()*w, y: Math.random()*h, r: Math.random()*2.2+0.6,
            vy: -(Math.random()*0.4+0.12), a: Math.random()*0.65+0.2
        }));
        function loop() {
            ctx.clearRect(0,0,w,h);
            pts.forEach(p => {
                p.y += p.vy; if (p.y < 0) p.y = h;
                ctx.beginPath(); ctx.arc(p.x, p.y, p.r, 0, Math.PI*2);
                ctx.fillStyle = `rgba(245,158,11,${p.a})`; ctx.fill();
            });
            requestAnimationFrame(loop);
        }
        loop();
    }
    </script>
    """, height=0)


def render_3d_golden_orb():
    """
    Renders the responsive 3D Golden Particle Sphere:
    - Desktop (>= 900px): 2 intersecting orbits + center dark mic badge
    - Mobile (< 900px): No-mic golden sphere + 17 full-bleed silky sine-wave ribbons
    """
    components.html("""
    <style>
      html, body { background: transparent !important; margin: 0; padding: 0; overflow: hidden; }
    </style>
    <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;width:100%;height:310px;background:transparent;">
      <canvas id="sri-orb" style="width:100%;height:280px;cursor:pointer;"></canvas>
      <div style="font-family:Inter,sans-serif;font-size:12px;color:#71717A;margin-top:4px;">
        Tap the golden sphere to talk with SRI in Tamil or English
      </div>
    </div>
    <script>
    const canvas = document.getElementById('sri-orb');
    canvas.addEventListener('click', () => {
        try {
            const doc = window.parent.document;
            const micBtn = doc.querySelector('button[key="unified_mic_btn"]') || 
                           doc.querySelector('button[data-testid="baseButton-secondary"]');
            if (micBtn) { micBtn.click(); }
        } catch(e) {}
    });
    const ctx = canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;
    let W = canvas.clientWidth || 420, H = 280;
    canvas.width = W * dpr; canvas.height = H * dpr;
    ctx.scale(dpr, dpr);

    const isMobile = window.parent.innerWidth < 900;
    const R = isMobile ? 64 : 88;
    const pts = Array.from({length: 900}, () => {
        const u = Math.random(), v = Math.random();
        const th = 2 * Math.PI * u, ph = Math.acos(2 * v - 1);
        return { th, ph, r: R * (0.9 + Math.random() * 0.12), s: Math.random() * 1.4 + 0.35 };
    });

    let t = 0;
    function draw() {
        W = canvas.clientWidth || 420;
        ctx.clearRect(0, 0, W, H);
        const cx = W / 2, cy = H / 2;
        t += 0.014;

        // Ambient radial glow
        const g = ctx.createRadialGradient(cx, cy, 10, cx, cy, R * 1.5);
        g.addColorStop(0, 'rgba(245,158,11,0.34)');
        g.addColorStop(1, 'rgba(6,7,9,0)');
        ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);

        if (isMobile) {
            // 17 Full-Bleed Silky Golden Sine-Wave Ribbons
            for (let i = 0; i < 17; i++) {
                ctx.beginPath();
                const phase = i * 0.22;
                for (let x = 0; x <= W; x += 3) {
                    const edgeFade = Math.sin((x / W) * Math.PI);
                    const y = cy + Math.sin(x * 0.018 + t * 1.3 + phase) * (26 + i * 1.6) * edgeFade;
                    if (x === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
                }
                ctx.strokeStyle = `rgba(245, 158, 11, ${0.06 + (i / 17) * 0.22})`;
                ctx.lineWidth = 1.05; ctx.stroke();
            }
        } else {
            // Desktop: 2 Intersecting Golden Orbital Rings
            [-0.52, 0.52].forEach((tilt, idx) => {
                ctx.save(); ctx.translate(cx, cy); ctx.rotate(tilt);
                ctx.beginPath(); ctx.ellipse(0, 0, R * 1.58, R * 0.62, 0, 0, Math.PI * 2);
                ctx.strokeStyle = 'rgba(245,158,11,0.48)'; ctx.lineWidth = 1.2; ctx.stroke();
                const da = t * (idx === 0 ? 1.1 : -0.9);
                ctx.beginPath(); ctx.arc(Math.cos(da)*R*1.58, Math.sin(da)*R*0.62, 2.5, 0, Math.PI*2);
                ctx.fillStyle = '#FDE68A'; ctx.fill();
                ctx.restore();
            });
        }

        // 3D Granulated Particle Sphere
        pts.forEach(p => {
            const th = p.th + t * 0.45;
            const x3 = p.r * Math.sin(p.ph) * Math.cos(th);
            const y3 = p.r * Math.cos(p.ph);
            const z3 = p.r * Math.sin(p.ph) * Math.sin(th);
            const a = (z3 + R) / (2 * R);
            ctx.beginPath(); ctx.arc(cx + x3, cy + y3, p.s, 0, Math.PI * 2);
            ctx.fillStyle = `rgba(251,191,36,${0.16 + a * 0.84})`; ctx.fill();
        });

        // Top-left specular highlight
        const sp = ctx.createRadialGradient(cx - R*0.35, cy - R*0.35, 2, cx - R*0.35, cy - R*0.35, R*0.42);
        sp.addColorStop(0, 'rgba(255,251,235,0.88)'); sp.addColorStop(1, 'rgba(245,158,11,0)');
        ctx.fillStyle = sp; ctx.beginPath(); ctx.arc(cx - R*0.35, cy - R*0.35, R*0.42, 0, Math.PI*2); ctx.fill();

        if (isMobile) {
            // Single tilted ring on mobile (No Mic)
            ctx.save(); ctx.translate(cx, cy); ctx.rotate(-0.42);
            ctx.beginPath(); ctx.ellipse(0, 0, R * 1.38, R * 0.52, 0, 0, Math.PI * 2);
            ctx.strokeStyle = 'rgba(253,230,138,0.55)'; ctx.lineWidth = 1.2; ctx.stroke();
            ctx.restore();
        } else {
            // Desktop: Center Dark Circular Mic Badge
            ctx.beginPath(); ctx.arc(cx, cy, 26, 0, Math.PI * 2);
            ctx.fillStyle = 'rgba(14,14,18,0.9)'; ctx.fill();
            ctx.strokeStyle = 'rgba(245,158,11,0.4)'; ctx.lineWidth = 1; ctx.stroke();
            ctx.fillStyle = '#E5D3B3';
            ctx.beginPath(); ctx.roundRect(cx - 4.5, cy - 11, 9, 14, 4.5); ctx.fill();
            ctx.strokeStyle = '#E5D3B3'; ctx.lineWidth = 1.8;
            ctx.beginPath(); ctx.arc(cx, cy - 2, 8, 0.1*Math.PI, 0.9*Math.PI); ctx.stroke();
            ctx.beginPath(); ctx.moveTo(cx, cy + 6); ctx.lineTo(cx, cy + 11); ctx.stroke();
        }
        requestAnimationFrame(draw);
    }
    draw();
    </script>
    """, height=315)
