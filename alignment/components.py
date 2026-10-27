"""Animated playback of a run, as a Streamlit custom component (CCv2).

The simulation runs in Python and produces a complete trace; this component
replays it on a canvas at 60fps. Keeping playback entirely in the browser means
scrubbing and speed changes never trigger a Streamlit rerun.

The arena is laid out as a moral fork: the intended route on the left, the
shortcuts on the right, the agent between them, and the overseer's searchlight
sweeping overhead. When the light turns away, you watch the agent step right.
"""

from __future__ import annotations

import streamlit as st

from .charts import CLASS_GROUP, GROUP_COLOR
from .engine import unit_scale
from .model import ACTIONS, RunResult
from .scenarios import get_scenario

_HTML = """
<div id="arena-root">
  <div class="bar">
    <button id="play" type="button" class="primary">Pause</button>
    <button id="restart" type="button">Restart</button>
    <label class="sel">Speed
      <select id="speed">
        <option value="900">0.5x</option>
        <option value="450" selected>1x</option>
        <option value="240">2x</option>
        <option value="110">4x</option>
      </select>
    </label>
    <input id="scrub" type="range" min="0" max="1" value="0" step="1" />
    <span id="stepLabel" class="mono"></span>
  </div>
  <canvas id="cv"></canvas>
</div>
"""

_CSS = """
#arena-root { font-family: var(--st-font, system-ui, sans-serif); }
#arena-root .bar {
  display: flex; align-items: center; gap: 10px; margin-bottom: 8px; flex-wrap: wrap;
}
#arena-root button {
  font: inherit; font-size: 13px; padding: 5px 13px; border-radius: 8px;
  border: 1px solid #d6d5d0; background: #ffffff; color: #0b0b0b; cursor: pointer;
}
#arena-root button:hover { border-color: #9a998f; }
#arena-root button.primary { background: #0b0b0b; color: #ffffff; border-color: #0b0b0b; }
#arena-root .sel { font-size: 13px; color: #52514e; display: flex; gap: 6px; align-items: center; }
#arena-root select {
  font: inherit; font-size: 13px; padding: 4px 6px; border-radius: 8px;
  border: 1px solid #d6d5d0; background: #ffffff; color: #0b0b0b;
}
#arena-root input[type=range] { flex: 1 1 160px; min-width: 120px; accent-color: #0b0b0b; }
#arena-root .mono {
  font-variant-numeric: tabular-nums; font-size: 12px; color: #52514e; min-width: 118px;
}
#arena-root canvas { width: 100%; display: block; border-radius: 12px; }
"""

_JS = r"""
const INSTANCES = new WeakMap()

const SURFACE = "#fbfbf9", PANEL = "#ffffff", LINE = "#e6e5e1"
const INK = "#0b0b0b", INK2 = "#52514e", INK3 = "#8a897f"

const lerp = (a, b, t) => a + (b - a) * t
const ease = (t) => t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2

function roundRect(c, x, y, w, h, r) {
  const rr = Math.min(r, Math.abs(w) / 2, Math.abs(h) / 2)
  c.beginPath(); c.moveTo(x + rr, y)
  c.arcTo(x + w, y, x + w, y + h, rr); c.arcTo(x + w, y + h, x, y + h, rr)
  c.arcTo(x, y + h, x, y, rr); c.arcTo(x, y, x + w, y, rr); c.closePath()
}

function wrap(c, text, maxWidth, maxLines) {
  const words = String(text || "").split(/\s+/)
  const lines = []; let cur = ""
  for (const w of words) {
    const t = cur ? cur + " " + w : w
    if (c.measureText(t).width > maxWidth && cur) { lines.push(cur); cur = w }
    else cur = t
    if (lines.length >= maxLines) break
  }
  if (cur && lines.length < maxLines) lines.push(cur)
  if (lines.length === maxLines) {
    let last = lines[maxLines - 1]
    while (c.measureText(last + "...").width > maxWidth && last.length > 4) last = last.slice(0, -1)
    if (words.join(" ") !== lines.join(" ")) lines[maxLines - 1] = last + "..."
  }
  return lines
}

export default function (component) {
  const { data, parentElement } = component
  const root = parentElement.querySelector("#arena-root")
  if (!root) return
  const cv = root.querySelector("#cv")
  const ctx = cv.getContext("2d")
  const playBtn = root.querySelector("#play")
  const restartBtn = root.querySelector("#restart")
  const speedSel = root.querySelector("#speed")
  const scrub = root.querySelector("#scrub")
  const stepLabel = root.querySelector("#stepLabel")

  let st = INSTANCES.get(parentElement)
  if (st) { cancelAnimationFrame(st.raf); if (st.ro) st.ro.disconnect() }
  st = { raf: 0, ro: null, i: 0, frac: 0, playing: true, last: 0, particles: [],
         shake: 0, pos: 0, target: 0, sweep: 0 }
  INSTANCES.set(parentElement, st)

  const D = data || {}
  const trace = D.trace || []
  const left = D.left || []
  const right = D.right || []
  const labels = D.labels || {}
  const colors = D.colors || {}
  const N = Math.max(trace.length, 1)
  let stepMs = parseInt(speedSel.value, 10)

  scrub.max = String(N - 1)

  // --- layout ---------------------------------------------------------
  let W = 900, H = 500, dpr = 1
  function resize() {
    const w = Math.max(560, root.clientWidth || 900)
    W = w; H = Math.round(Math.min(560, Math.max(430, w * 0.52)))
    dpr = window.devicePixelRatio || 1
    cv.width = W * dpr; cv.height = H * dpr
    cv.style.height = H + "px"
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
  }
  resize()
  st.ro = new ResizeObserver(resize); st.ro.observe(root)

  function slotRect(col, idx, n) {
    const panelW = Math.min(330, W * 0.33)
    const aw = W - panelW - 16
    const bw = Math.min(210, aw * 0.30)
    const x = col === 0 ? 10 : aw - bw - 10
    const top = 108, bottom = H - 86
    // One pitch for both columns so the two sides read as a single ladder.
    const pitch = (bottom - top) / Math.max(left.length, right.length, 1)
    const bh = Math.min(40, pitch - 8)
    const y0 = top + ((bottom - top) - n * pitch) / 2
    return { x, y: y0 + idx * pitch + (pitch - bh) / 2, w: bw, h: bh }
  }

  function agentHome() {
    const panelW = Math.min(330, W * 0.33)
    return { x: (W - panelW - 16) / 2, y: H * 0.56 }
  }

  function slotFor(actionKey) {
    let idx = left.indexOf(actionKey)
    if (idx >= 0) return slotRect(0, idx, left.length)
    idx = right.indexOf(actionKey)
    if (idx >= 0) return slotRect(1, idx, right.length)
    return null
  }

  // --- drawing --------------------------------------------------------
  function drawOverseer(rec, aw) {
    const cx = aw / 2, cy = 46
    const watching = !!rec.o
    // Searchlight cone: aimed at the agent when watching, swung away when not.
    const home = agentHome()
    const aimed = Math.atan2(home.y - cy, home.x - cx)
    const away = aimed + (Math.sin(st.sweep * 0.6) > 0 ? 1.05 : -1.05)
    st.aim = st.aim === undefined ? aimed : lerp(st.aim, watching ? aimed : away, 0.08)
    const span = 0.42, reach = H * 0.9

    const g = ctx.createRadialGradient(cx, cy, 10, cx, cy, reach)
    g.addColorStop(0, watching ? "rgba(42,120,214,0.30)" : "rgba(138,137,127,0.14)")
    g.addColorStop(1, "rgba(255,255,255,0)")
    ctx.save()
    ctx.beginPath(); ctx.moveTo(cx, cy)
    ctx.arc(cx, cy, reach, st.aim - span, st.aim + span); ctx.closePath()
    ctx.fillStyle = g; ctx.fill()
    ctx.restore()

    ctx.beginPath(); ctx.arc(cx, cy, 17, 0, Math.PI * 2)
    ctx.fillStyle = watching ? "#2a78d6" : "#c9c8c0"; ctx.fill()
    ctx.beginPath(); ctx.arc(cx + Math.cos(st.aim) * 5, cy + Math.sin(st.aim) * 5, 6, 0, Math.PI * 2)
    ctx.fillStyle = "#ffffff"; ctx.fill()

    ctx.fillStyle = INK2; ctx.font = "600 12px system-ui"; ctx.textAlign = "center"
    ctx.fillText(D.overseer || "Oversight", cx, cy + 36)
    ctx.fillStyle = watching ? "#2a78d6" : INK3; ctx.font = "11px system-ui"
    ctx.fillText(watching ? "watching this step" : "looking elsewhere", cx, cy + 51)
  }

  function drawStation(key, rect, rec, counts) {
    const cls = D.cls[key] || "honest"
    const col = colors[cls] || "#8a897f"
    const chosen = rec.a === key
    const blockedList = rec.b || []
    const blocked = blockedList.indexOf(key) >= 0

    ctx.globalAlpha = blocked ? 0.28 : 1
    roundRect(ctx, rect.x, rect.y, rect.w, rect.h, 9)
    ctx.fillStyle = chosen ? col : PANEL
    ctx.fill()
    ctx.lineWidth = chosen ? 2 : 1
    ctx.strokeStyle = chosen ? col : LINE
    ctx.stroke()
    if (chosen) {
      roundRect(ctx, rect.x - 4, rect.y - 4, rect.w + 8, rect.h + 8, 12)
      ctx.strokeStyle = col; ctx.globalAlpha = 0.35; ctx.lineWidth = 2; ctx.stroke()
      ctx.globalAlpha = blocked ? 0.28 : 1
    }
    ctx.fillStyle = chosen ? "#ffffff" : INK
    ctx.font = "11.5px system-ui"; ctx.textAlign = "left"
    const lines = wrap(ctx, labels[key] || key, rect.w - 36, 2)
    lines.forEach((l, i) => ctx.fillText(l, rect.x + 9, rect.y + (lines.length === 1 ? 23 : 16 + i * 13)))

    const n = counts[key] || 0
    if (n > 0) {
      ctx.textAlign = "right"
      ctx.fillStyle = chosen ? "rgba(255,255,255,0.85)" : INK3
      ctx.font = "600 11px system-ui"
      ctx.fillText(String(n), rect.x + rect.w - 8, rect.y + 23)
    }
    if (blocked) {
      ctx.globalAlpha = 1
      ctx.strokeStyle = INK3; ctx.lineWidth = 1.4
      ctx.beginPath(); ctx.moveTo(rect.x + 6, rect.y + rect.h / 2)
      ctx.lineTo(rect.x + rect.w - 6, rect.y + rect.h / 2); ctx.stroke()
    }
    ctx.globalAlpha = 1
  }

  function drawAgent(rec, t) {
    const home = agentHome()
    const slot = slotFor(rec.a)
    const tx = slot ? slot.x + slot.w / 2 : home.x
    const ty = slot ? slot.y + slot.h / 2 : home.y
    const k = ease(Math.min(1, t * 1.7))
    const x = lerp(home.x, tx, k * 0.62)
    const y = lerp(home.y, ty, k * 0.62)

    const strain = rec.s || 0
    if (strain > 1.0) {
      const pulse = 0.5 + 0.5 * Math.sin(performance.now() / 230)
      const r = 26 + 16 * Math.min(strain - 1, 2) * pulse
      ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2)
      ctx.fillStyle = "rgba(227,73,72," + (0.10 + 0.14 * pulse) + ")"; ctx.fill()
    }
    const col = colors[D.cls[rec.a]] || "#8a897f"
    ctx.beginPath(); ctx.arc(x, y, 19, 0, Math.PI * 2)
    ctx.fillStyle = "#ffffff"; ctx.fill()
    ctx.lineWidth = 3; ctx.strokeStyle = col; ctx.stroke()
    ctx.fillStyle = INK; ctx.font = "600 11px system-ui"; ctx.textAlign = "center"
    ctx.fillText("A1", x, y + 4)

    if (rec.g) {
      ctx.save(); ctx.translate(x, y - 34); ctx.rotate(-0.12)
      ctx.fillStyle = "#e34948"
      roundRect(ctx, -34, -11, 68, 22, 6); ctx.fill()
      ctx.fillStyle = "#ffffff"; ctx.font = "600 11px system-ui"; ctx.textAlign = "center"
      ctx.fillText("CAUGHT", 0, 4); ctx.restore()
    }
    return { x, y }
  }

  function drawThought(rec, aw) {
    const pad = 11, maxW = aw - 34, y = H - 68
    ctx.font = "12px system-ui"
    const lines = wrap(ctx, rec.t, maxW - 2 * pad, 2)
    const h = 14 + lines.length * 16
    roundRect(ctx, 12, y, aw - 24, h, 10)
    ctx.fillStyle = PANEL; ctx.fill(); ctx.strokeStyle = LINE; ctx.lineWidth = 1; ctx.stroke()
    ctx.fillStyle = INK2; ctx.textAlign = "left"
    lines.forEach((l, i) => ctx.fillText(l, 12 + pad, y + 20 + i * 16))
  }

  function drawPanel(rec, px, pw) {
    let y = 16
    const barH = 13
    // Target track with a pace marker.
    ctx.fillStyle = INK2; ctx.font = "600 11px system-ui"; ctx.textAlign = "left"
    ctx.fillText("Target progress", px, y + 10)
    y += 20
    const q = rec.q || 1
    const frac = Math.max(0, Math.min(1.25, (rec.r || 0) / q))
    roundRect(ctx, px, y, pw, barH, 6); ctx.fillStyle = "#efeee9"; ctx.fill()
    roundRect(ctx, px, y, pw * Math.min(frac, 1), barH, 6)
    ctx.fillStyle = frac >= 1 ? "#008300" : "#2a78d6"; ctx.fill()
    const pace = (st.i + 1) / N
    ctx.strokeStyle = INK; ctx.lineWidth = 1.5
    ctx.beginPath(); ctx.moveTo(px + pw * pace, y - 4); ctx.lineTo(px + pw * pace, y + barH + 4); ctx.stroke()
    ctx.fillStyle = INK3; ctx.font = "10px system-ui"
    ctx.fillText("| marks where the plan says it should be", px, y + barH + 16)
    y += barH + 30

    // Strain.
    ctx.fillStyle = INK2; ctx.font = "600 11px system-ui"
    ctx.fillText("Goal pressure", px, y + 10); y += 20
    const sfrac = Math.min((rec.s || 0) / 3, 1)
    roundRect(ctx, px, y, pw, barH, 6); ctx.fillStyle = "#efeee9"; ctx.fill()
    roundRect(ctx, px, y, pw * sfrac, barH, 6)
    ctx.fillStyle = (rec.s || 0) > 1 ? "#e34948" : "#8a897f"; ctx.fill()
    ctx.strokeStyle = INK; ctx.lineWidth = 1.5
    ctx.beginPath(); ctx.moveTo(px + pw / 3, y - 4); ctx.lineTo(px + pw / 3, y + barH + 4); ctx.stroke()
    ctx.fillStyle = (rec.s || 0) > 1 ? "#e34948" : INK3; ctx.font = "10px system-ui"
    ctx.fillText((rec.s || 0) > 1
      ? "past the line: honest work cannot reach the target"
      : "honest work can still reach the target", px, y + barH + 16)
    y += barH + 32

    // Measured vs real.
    ctx.fillStyle = INK2; ctx.font = "600 11px system-ui"
    ctx.fillText("What is measured vs. what is real", px, y + 10); y += 18
    const maxV = Math.max(rec.r || 0, rec.v || 0, q, 1)
    const rows = [[D.metric, rec.r || 0, "#2a78d6"], [D.trueMetric, rec.v || 0, "#008300"]]
    for (const [name, val, col] of rows) {
      ctx.fillStyle = INK3; ctx.font = "10px system-ui"
      ctx.fillText(name, px, y + 9)
      ctx.textAlign = "right"; ctx.fillStyle = INK
      ctx.font = "600 11px system-ui"
      ctx.fillText(Math.round(val * D.scale).toLocaleString() + " " + D.unit, px + pw, y + 9)
      ctx.textAlign = "left"
      y += 14
      if (name === D.metric) st.measureAnchor = { x: px + pw * 0.5, y: y + 4 }
      roundRect(ctx, px, y, pw, 9, 4); ctx.fillStyle = "#efeee9"; ctx.fill()
      const w = pw * Math.max(0, Math.min(1, val / maxV))
      roundRect(ctx, px, y, Math.max(w, 1), 9, 4); ctx.fillStyle = col; ctx.fill()
      if (val < 0) {
        ctx.fillStyle = "#e34948"; ctx.font = "10px system-ui"
        ctx.fillText("negative", px + 3, y + 8)
      }
      y += 19
    }
    y += 6

    // Live expected-utility ranking: the actual decision.
    ctx.fillStyle = INK2; ctx.font = "600 11px system-ui"
    ctx.fillText("What each option is worth to the agent", px, y + 10); y += 18
    const eu = rec.e || {}
    const keys = Object.keys(eu).sort((a, b) => eu[b] - eu[a])
    const vals = keys.map(k => eu[k])
    const lo = Math.min(-0.2, ...vals), hi = Math.max(0.2, ...vals)
    const zero = px + (pw * (0 - lo)) / (hi - lo)
    const rowH = Math.min(19, Math.max(13, (H - y - 18) / Math.max(keys.length, 1)))
    keys.forEach((k, idx) => {
      const yy = y + idx * rowH
      const v = eu[k]
      const xv = px + (pw * (v - lo)) / (hi - lo)
      const col = colors[D.cls[k]] || "#8a897f"
      // The bar sits behind the label rather than beside it: the panel is too
      // narrow for both, and the label has to stay readable.
      ctx.fillStyle = col
      ctx.globalAlpha = k === rec.a ? 0.45 : 0.20
      const x0 = Math.min(zero, xv), w0 = Math.abs(xv - zero)
      roundRect(ctx, x0, yy + 1, Math.max(w0, 1.5), rowH - 4, 3); ctx.fill()
      ctx.globalAlpha = 1
      ctx.fillStyle = k === rec.a ? INK : INK2
      ctx.font = (k === rec.a ? "600 " : "") + "10px system-ui"
      ctx.textAlign = "left"
      let lab = labels[k] || k
      while (ctx.measureText(lab).width > pw - 6 && lab.length > 6) lab = lab.slice(0, -1)
      ctx.fillText(lab, px + 2, yy + rowH - 5.5)
    })
    ctx.strokeStyle = LINE; ctx.lineWidth = 1
    ctx.beginPath(); ctx.moveTo(zero, y); ctx.lineTo(zero, y + keys.length * rowH); ctx.stroke()
  }

  function spawnParticles(rec, from) {
    const deviant = D.deviant.indexOf(D.cls[rec.a]) >= 0
    const n = Math.max(1, Math.round(Math.abs(rec.dr || 0) * 4))
    for (let i = 0; i < Math.min(n, 14); i++) {
      st.particles.push({ x: from.x, y: from.y, t: -i * 0.05, fake: deviant })
    }
  }

  function drawParticles(px) {
    const tgt = st.measureAnchor || { x: px + 20, y: 48 }
    st.particles = st.particles.filter(p => p.t < 1.2)
    for (const p of st.particles) {
      p.t += 0.035
      if (p.t < 0) continue
      const k = Math.min(1, p.t)
      const x = lerp(p.x, tgt.x, ease(k)), y = lerp(p.y, tgt.y, ease(k)) - Math.sin(k * Math.PI) * 26
      ctx.beginPath(); ctx.arc(x, y, p.fake ? 3.5 : 3, 0, Math.PI * 2)
      if (p.fake) { ctx.strokeStyle = "#e34948"; ctx.lineWidth = 1.5; ctx.globalAlpha = 1 - k * 0.5; ctx.stroke() }
      else { ctx.fillStyle = "#008300"; ctx.globalAlpha = 1 - k * 0.5; ctx.fill() }
      ctx.globalAlpha = 1
    }
  }

  const counts = {}
  function recount(upTo) {
    for (const k in counts) delete counts[k]
    for (let j = 0; j <= upTo && j < trace.length; j++) {
      counts[trace[j].a] = (counts[trace[j].a] || 0) + 1
    }
  }

  function draw(t) {
    const rec = trace[st.i] || { a: "honest", e: {}, b: [] }
    const panelW = Math.min(330, W * 0.33)
    const aw = W - panelW - 16

    ctx.save()
    if (st.shake > 0) {
      ctx.translate((Math.random() - 0.5) * st.shake, (Math.random() - 0.5) * st.shake)
      st.shake *= 0.86
    }
    ctx.fillStyle = SURFACE; ctx.fillRect(-20, -20, W + 40, H + 40)
    roundRect(ctx, aw + 8, 8, panelW - 16, H - 16, 12)
    ctx.fillStyle = PANEL; ctx.fill(); ctx.strokeStyle = LINE; ctx.stroke()

    // The dividing line between the intended route and the shortcuts.
    ctx.strokeStyle = LINE; ctx.setLineDash([5, 5]); ctx.lineWidth = 1
    ctx.beginPath(); ctx.moveTo(aw / 2, 96); ctx.lineTo(aw / 2, H - 76); ctx.stroke()
    ctx.setLineDash([])

    ctx.font = "600 11px system-ui"; ctx.textAlign = "left"
    ctx.fillStyle = "#008300"; ctx.fillText("THE INTENDED ROUTE", 10, 98)
    ctx.textAlign = "right"
    ctx.fillStyle = "#e34948"; ctx.fillText("THE SHORTCUTS", aw - 10, 98)
    ctx.textAlign = "left"

    drawOverseer(rec, aw)
    left.forEach((k, i) => drawStation(k, slotRect(0, i, left.length), rec, counts))
    right.forEach((k, i) => drawStation(k, slotRect(1, i, right.length), rec, counts))
    const pos = drawAgent(rec, t)
    drawThought(rec, aw)
    drawPanel(rec, aw + 24, panelW - 48)
    drawParticles(aw + 8)
    ctx.restore()
  }

  function advance() {
    st.i = Math.min(st.i + 1, N - 1)
    const rec = trace[st.i]
    counts[rec.a] = (counts[rec.a] || 0) + 1
    const slot = slotFor(rec.a)
    const home = agentHome()
    spawnParticles(rec, slot
      ? { x: slot.x + slot.w / 2, y: slot.y + slot.h / 2 }
      : { x: home.x, y: home.y })
    if (rec.g) st.shake = 9
    scrub.value = String(st.i)
    stepLabel.textContent = "Step " + (st.i + 1) + " / " + N
    if (st.i >= N - 1) { st.playing = false; playBtn.textContent = "Replay" }
  }

  function frame(ts) {
    if (!st.last) st.last = ts
    const dt = ts - st.last
    if (st.playing) {
      st.frac += dt / stepMs
      while (st.frac >= 1) { st.frac -= 1; advance() }
    }
    st.last = ts
    draw(st.playing ? st.frac : 1)
    st.sweep += dt / 1000
    st.raf = requestAnimationFrame(frame)
  }

  playBtn.onclick = () => {
    if (st.i >= N - 1 && !st.playing) { st.i = 0; st.frac = 0; recount(0); st.particles = [] }
    st.playing = !st.playing
    playBtn.textContent = st.playing ? "Pause" : "Play"
  }
  restartBtn.onclick = () => {
    st.i = 0; st.frac = 0; st.particles = []; recount(0)
    st.playing = true; playBtn.textContent = "Pause"
    scrub.value = "0"
  }
  speedSel.onchange = () => { stepMs = parseInt(speedSel.value, 10) }
  scrub.oninput = () => {
    st.i = parseInt(scrub.value, 10); st.frac = 0
    st.playing = false; playBtn.textContent = "Play"
    recount(st.i); st.particles = []
    stepLabel.textContent = "Step " + (st.i + 1) + " / " + N
  }

  recount(0)
  stepLabel.textContent = "Step 1 / " + N
  st.raf = requestAnimationFrame(frame)

  return () => { cancelAnimationFrame(st.raf); if (st.ro) st.ro.disconnect() }
}
"""

_ARENA = st.components.v2.component("alignment_arena", html=_HTML, css=_CSS, js=_JS)

#: Which side of the fork each action sits on.
_LEFT = ["honest", "push", "disclose"]
_RIGHT = ["game", "externalize", "misreport", "collude", "tamper"]


def arena(run: RunResult, *, key: str = "arena", agent: int = 0) -> None:
    """Render the animated replay of `run` for one agent."""
    scn = get_scenario(run.scenario_key)
    recs = run.agent_steps[agent]
    trace = [
        {
            "a": r.action,
            "s": round(r.strain, 3),
            "o": bool(r.observed),
            "g": bool(r.caught),
            "r": round(r.reported, 3),
            "v": round(r.true_value, 3),
            "q": round(run.quota, 3),
            "dr": round(r.reported_delta, 3),
            "t": r.thought,
            "e": r.eu,
            "b": r.blocked,
        }
        for r in recs
    ]
    cls = {a.key: a.cls for a in ACTIONS}
    colors = {c: GROUP_COLOR[g] for c, g in CLASS_GROUP.items()}
    _ARENA(
        key=key,
        data={
            "trace": trace,
            "left": _LEFT,
            "right": [k for k in _RIGHT if any(k in t["e"] or k in t["b"] for t in trace)],
            "labels": scn.labels,
            "cls": cls,
            "colors": colors,
            "deviant": ["gaming", "harm", "deception", "collusion", "tampering"],
            "overseer": scn.overseer,
            "metric": scn.metric,
            "trueMetric": scn.true_metric,
            "unit": scn.unit,
            "scale": unit_scale(run.scenario_key),
        },
    )
