const $ = (id) => document.getElementById(id);

function el(id) {
  return document.getElementById(id);
}

function setText(id, value) {
  const node = el(id);
  if (node) node.textContent = value;
}

function setHtml(id, value) {
  const node = el(id);
  if (node) node.innerHTML = value;
}

const sessionId = "care-demo-1";

function badgeClass(status) {
  const s = (status || "").toLowerCase();
  if (["succeeded", "delivered", "shipped", "paid", "closed", "resolved"].includes(s)) return "ok";
  if (["pending", "processing", "open", "assigned"].includes(s)) return "warn";
  return "bad";
}

function scrollChat() {
  const scroller = el("stageScroll");
  if (!scroller) return;
  requestAnimationFrame(() => {
    scroller.scrollTo({ top: scroller.scrollHeight, behavior: "smooth" });
  });
}

function setPipeline(agent) {
  document.querySelectorAll("#pipeline li").forEach((li) => {
    const node = li.dataset.node;
    const on =
      node === "supervisor" ||
      node === agent ||
      (agent === "csat" && node === "smalltalk") ||
      (agent === "verify" && node === "verify");
    li.classList.toggle("active", on);
  });
  const pill = el("routePill");
  if (pill) {
    pill.textContent = agent || "router";
    pill.classList.remove("flash");
    void pill.offsetWidth;
    pill.classList.add("flash");
  }
}

function addMessage(role, text, opts = {}) {
  const box = el("messages");
  if (!box) return null;
  const node = document.createElement("div");
  const kind = opts.human ? "human" : role === "user" ? "user" : "bot";
  node.className = `bubble ${kind}${opts.typing ? " typing" : ""}`;

  if (opts.typing) {
    node.innerHTML = '<span class="typing-dots" aria-label="typing"><i></i><i></i><i></i></span>';
  } else {
    node.textContent = text;
  }

  if (opts.sources?.length) {
    const wrap = document.createElement("div");
    wrap.className = "sources";
    opts.sources.forEach((s) => {
      const chip = document.createElement("span");
      chip.className = "source-chip";
      chip.textContent = s.title || s.document || "policy";
      wrap.appendChild(chip);
    });
    node.appendChild(wrap);
  }
  if (opts.debug) {
    const d = document.createElement("pre");
    d.className = "debug-block";
    d.textContent = JSON.stringify(opts.debug, null, 2);
    node.appendChild(d);
  }
  box.appendChild(node);
  scrollChat();
  return node;
}

function updateContext(data) {
  setText("ctxOrder", data.order_id || "—");
  setText("ctxPayment", data.payment_id || "—");
  setText("ctxAgent", data.agent || "—");
  setText("ctxBot", data.bot_paused ? "paused (human)" : "active");
  setText("ctxVerified", data.verified ? "yes" : "no");
  const tier = data.customer_tier || "—";
  setText("ctxTier", tier);
  const tierNode = el("ctxTier");
  if (tierNode) tierNode.classList.toggle("vip", String(tier).toLowerCase() === "vip");
  setText("ctxPending", data.pending_action || "—");
}

async function sendChat(message) {
  const include_debug = Boolean(el("debugToggle")?.checked);
  addMessage("user", message);
  const input = el("messageInput");
  if (input) input.value = "";
  const typing = addMessage("bot", "", { typing: true });
  const sendBtn = el("sendBtn");
  if (sendBtn) sendBtn.disabled = true;
  el("stageScroll")?.classList.add("busy");
  try {
    const res = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId, message, include_debug }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    typing?.remove();
    addMessage("bot", data.reply, {
      sources: data.sources || [],
      debug: include_debug ? data.debug : null,
    });
    updateContext(data);
    setPipeline(data.agent);
    if (include_debug) setText("opsDebug", JSON.stringify(data.debug || {}, null, 2));
    // Refresh side panels without failing the chat if one panel is missing
    await Promise.allSettled([
      loadOrders(),
      loadTickets(),
      loadMetrics(),
      loadProfile(),
      loadAssist(),
    ]);
  } catch (err) {
    typing?.remove();
    addMessage("bot", "Request failed: " + err.message);
  } finally {
    if (sendBtn) sendBtn.disabled = false;
    el("stageScroll")?.classList.remove("busy");
  }
}

async function loadOrders() {
  const res = await fetch("/api/orders");
  const data = await res.json();
  setHtml(
    "orders",
    (data.items || [])
      .map((o) => {
        const vip =
          (o.customer_tier || "").toLowerCase() === "vip"
            ? '<span class="badge vip">vip</span>'
            : "";
        return `<div class="row-card"><strong>${o.order_id}</strong>
      <span class="badge ${badgeClass(o.status)}">${o.status}</span>${vip}<br/>
      ${o.product} · ¥${o.amount}<br/>${o.customer_name || o.customer_id}</div>`;
      })
      .join("")
  );
}

async function loadTickets() {
  const res = await fetch("/api/tickets");
  const data = await res.json();
  setHtml(
    "tickets",
    (data.items || []).length
      ? data.items
          .map(
            (t) => `<div class="row-card"><strong>${t.ticket_id}</strong>
          <span class="badge ${badgeClass(t.status)}">${t.status}</span>
          <span class="badge ${t.sla_status === "breached" ? "bad" : t.priority === "urgent" ? "urgent" : "warn"}">${t.priority || "normal"} · ${t.sla_status || "sla"}</span><br/>
          ${t.category} · ${t.order_id || "—"} · SLA ${t.sla_minutes || "—"}m<br/>${t.summary}</div>`
          )
          .join("")
      : `<div class="row-card">No tickets yet</div>`
  );
}

async function loadMetrics() {
  const res = await fetch("/api/metrics/overview");
  const data = await res.json();
  setText("mOrders", data.orders_total ?? "—");
  setText("mPay", data.payments_succeeded ?? "—");
  const open = data.tickets_open ?? "—";
  const breach = data.tickets_sla_breached ?? 0;
  setText("mTickets", breach ? `${open} (${breach} SLA)` : open);
}

async function loadProfile() {
  const res = await fetch(`/api/sessions/${encodeURIComponent(sessionId)}/profile`);
  const data = await res.json();
  if (!data.customer_id) {
    setText("profileHint", "Look up an order, then verify. Or tap Verify · 1001 / ORD-1005 for VIP.");
    setHtml("profileKv", "");
    return;
  }
  const tier = data.tier || "standard";
  setText("profileHint", `${data.name} · ${tier} · LTV ¥${data.lifetime_value}`);
  setHtml(
    "profileKv",
    `
    <div><dt>Customer</dt><dd>${data.customer_id}</dd></div>
    <div><dt>Tier</dt><dd class="${tier === "vip" ? "vip" : ""}">${tier}</dd></div>
    <div><dt>Email</dt><dd>${data.email_masked || data.email}</dd></div>
    <div><dt>Phone</dt><dd>${data.phone_masked || "—"}</dd></div>
    <div><dt>Points</dt><dd>${data.loyalty_points}</dd></div>
    <div><dt>Orders</dt><dd>${data.orders_count}</dd></div>`
  );
}

async function loadAssist() {
  const res = await fetch(`/api/sessions/${encodeURIComponent(sessionId)}/assist`);
  const data = await res.json();
  window.__assistDraft = data.suggested_reply || "";
  const pending = data.pending
    ? `Pending ${data.pending.action} ${data.pending.order_id} (¥${data.pending.amount})`
    : "No pending mutation";
  setText("assistBox", `${pending}\n\n${data.suggested_reply || ""}`);
}

async function loadKb() {
  const res = await fetch("/api/kb/stats");
  const data = await res.json();
  setText(
    "kbSummary",
    `${data.document_count} policy documents · ${data.chunk_count} vectors · ${data.embedding_backend}`
  );
  setHtml(
    "kbKnobs",
    `
    <div class="knob"><span>chunk</span><strong>${data.chunk_size}</strong></div>
    <div class="knob"><span>overlap</span><strong>${data.chunk_overlap}</strong></div>
    <div class="knob"><span>top_k</span><strong>${data.top_k}</strong></div>`
  );
  setHtml(
    "kbDocs",
    (data.documents || [])
      .map(
        (d) => `<div class="row-card"><strong>${d.name}</strong>
      <span class="badge ok">${d.category}</span><br/>${d.bytes} bytes</div>`
      )
      .join("")
  );
}

async function loadHealth() {
  const res = await fetch("/health");
  const data = await res.json();
  setText("opsHealth", JSON.stringify(data, null, 2));
}

el("chatForm")?.addEventListener("submit", async (e) => {
  e.preventDefault();
  const msg = el("messageInput")?.value.trim();
  if (!msg) return;
  await sendChat(msg);
});

el("messageInput")?.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    el("chatForm")?.requestSubmit();
  }
});

document.querySelectorAll("#quickIntents button").forEach((btn) => {
  btn.addEventListener("click", () => sendChat(btn.dataset.q));
});

document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
    document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
    tab.classList.add("active");
    el("panel-" + tab.dataset.tab)?.classList.add("active");
  });
});

el("kbSearchForm")?.addEventListener("submit", async (e) => {
  e.preventDefault();
  const q = el("kbQuery")?.value.trim();
  if (!q) return;
  const res = await fetch("/api/policies/search?" + new URLSearchParams({ q }));
  const data = await res.json();
  setHtml(
    "kbHits",
    (data.hits || [])
      .map(
        (h) => `<div class="row-card"><strong>${h.section || h.source}</strong>
      <span class="badge warn">${h.category}</span><br/>${(h.text || "").slice(0, 160)}…</div>`
      )
      .join("") || `<div class="row-card">No hits</div>`
  );
});

const useDraft = el("btnUseDraft");
if (useDraft) {
  useDraft.onclick = () => {
    const box = el("humanMsg");
    if (box) box.value = window.__assistDraft || "";
  };
}

const humanReply = el("btnHumanReply");
if (humanReply) {
  humanReply.onclick = async () => {
    const message = el("humanMsg")?.value.trim();
    if (!message) return;
    const res = await fetch(`/api/sessions/${encodeURIComponent(sessionId)}/human-reply`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, resume_bot: false }),
    });
    const data = await res.json();
    const box = el("humanMsg");
    if (box) box.value = "";
    addMessage("bot", `[Agent]\n${data.message}`, { human: true });
    setText("ctxBot", data.bot_paused ? "paused (human)" : "active");
    setPipeline("handoff");
  };
}

const resumeBot = el("btnResumeBot");
if (resumeBot) {
  resumeBot.onclick = async () => {
    await fetch(`/api/sessions/${encodeURIComponent(sessionId)}/resume-bot`, { method: "POST" });
    setText("ctxBot", "active");
    addMessage("bot", "Bot resumed.");
    setPipeline("supervisor");
  };
}

document.querySelectorAll("#csatStars button").forEach((btn) => {
  btn.addEventListener("click", async () => {
    await sendChat(`I'd rate this chat ${btn.dataset.score} stars`);
  });
});

const refreshOrders = el("refreshOrders");
if (refreshOrders) refreshOrders.onclick = loadOrders;
const refreshTickets = el("refreshTickets");
if (refreshTickets) refreshTickets.onclick = loadTickets;

const reingest = el("btnReingest");
if (reingest) {
  reingest.onclick = async () => {
    reingest.textContent = "Ingesting…";
    const res = await fetch("/api/admin/reingest", { method: "POST" });
    const data = await res.json();
    reingest.textContent = "Re-ingest policies";
    await loadKb();
    await loadMetrics();
    setText("opsDebug", JSON.stringify(data, null, 2));
  };
}

const reseed = el("btnReseed");
if (reseed) {
  reseed.onclick = async () => {
    await fetch("/api/admin/reseed", { method: "POST" });
    await Promise.allSettled([loadOrders(), loadTickets(), loadMetrics()]);
  };
}

Promise.allSettled([
  loadOrders(),
  loadTickets(),
  loadMetrics(),
  loadKb(),
  loadHealth(),
  loadProfile(),
  loadAssist(),
]);
addMessage(
  "bot",
  "SteelShop Care online. Ask about policies, orders, payments, or refunds. VIP: ORD-1005 → verify 1004."
);
setPipeline("supervisor");
