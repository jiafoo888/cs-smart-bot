const $ = (id) => document.getElementById(id);

const sessionId = "care-demo-1";

function badgeClass(status) {
  const s = (status || "").toLowerCase();
  if (["succeeded", "delivered", "shipped", "paid", "closed", "resolved"].includes(s)) return "ok";
  if (["pending", "processing", "open", "assigned"].includes(s)) return "warn";
  return "bad";
}

function scrollChat() {
  const scroller = $("stageScroll");
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
  const pill = $("routePill");
  if (pill) {
    pill.textContent = agent || "router";
    pill.classList.remove("flash");
    void pill.offsetWidth;
    pill.classList.add("flash");
  }
}

function addMessage(role, text, opts = {}) {
  const box = $("messages");
  const el = document.createElement("div");
  const kind = opts.human ? "human" : role === "user" ? "user" : "bot";
  el.className = `bubble ${kind}${opts.typing ? " typing" : ""}`;

  if (opts.typing) {
    el.innerHTML = '<span class="typing-dots" aria-label="typing"><i></i><i></i><i></i></span>';
  } else {
    el.textContent = text;
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
    el.appendChild(wrap);
  }
  if (opts.debug) {
    const d = document.createElement("pre");
    d.className = "debug-block";
    d.textContent = JSON.stringify(opts.debug, null, 2);
    el.appendChild(d);
  }
  box.appendChild(el);
  scrollChat();
  return el;
}

function updateContext(data) {
  $("ctxOrder").textContent = data.order_id || "—";
  $("ctxPayment").textContent = data.payment_id || "—";
  $("ctxAgent").textContent = data.agent || "—";
  $("ctxBot").textContent = data.bot_paused ? "paused (human)" : "active";
  $("ctxVerified").textContent = data.verified ? "yes" : "no";
  const tier = data.customer_tier || "—";
  $("ctxTier").textContent = tier;
  $("ctxTier").classList.toggle("vip", String(tier).toLowerCase() === "vip");
  $("ctxPending").textContent = data.pending_action || "—";
}

async function sendChat(message) {
  const include_debug = $("debugToggle").checked;
  addMessage("user", message);
  $("messageInput").value = "";
  const typing = addMessage("bot", "", { typing: true });
  $("sendBtn").disabled = true;
  $("stageScroll")?.classList.add("busy");
  try {
    const res = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId, message, include_debug }),
    });
    const data = await res.json();
    typing.remove();
    addMessage("bot", data.reply, {
      sources: data.sources || [],
      debug: include_debug ? data.debug : null,
    });
    updateContext(data);
    setPipeline(data.agent);
    if (include_debug) {
      $("opsDebug").textContent = JSON.stringify(data.debug || {}, null, 2);
    }
    await Promise.all([loadOrders(), loadTickets(), loadMetrics(), loadProfile(), loadAssist()]);
  } catch (err) {
    typing.remove();
    addMessage("bot", "Request failed: " + err.message);
  } finally {
    $("sendBtn").disabled = false;
    $("stageScroll")?.classList.remove("busy");
  }
}

async function loadOrders() {
  const res = await fetch("/api/orders");
  const data = await res.json();
  $("orders").innerHTML = (data.items || [])
    .map((o) => {
      const vip =
        (o.customer_tier || "").toLowerCase() === "vip"
          ? '<span class="badge vip">vip</span>'
          : "";
      return `<div class="row-card"><strong>${o.order_id}</strong>
      <span class="badge ${badgeClass(o.status)}">${o.status}</span>${vip}<br/>
      ${o.product} · ¥${o.amount}<br/>${o.customer_name || o.customer_id}</div>`;
    })
    .join("");
}

async function loadTickets() {
  const res = await fetch("/api/tickets");
  const data = await res.json();
  $("tickets").innerHTML = (data.items || []).length
    ? data.items
        .map(
          (t) => `<div class="row-card"><strong>${t.ticket_id}</strong>
          <span class="badge ${badgeClass(t.status)}">${t.status}</span>
          <span class="badge ${t.sla_status === "breached" ? "bad" : t.priority === "urgent" ? "urgent" : "warn"}">${t.priority || "normal"} · ${t.sla_status || "sla"}</span><br/>
          ${t.category} · ${t.order_id || "—"} · SLA ${t.sla_minutes || "—"}m<br/>${t.summary}</div>`
        )
        .join("")
    : `<div class="row-card">No tickets yet</div>`;
}

async function loadMetrics() {
  const res = await fetch("/api/metrics/overview");
  const data = await res.json();
  $("mOrders").textContent = data.orders_total ?? "—";
  $("mPay").textContent = data.payments_succeeded ?? "—";
  const open = data.tickets_open ?? "—";
  const breach = data.tickets_sla_breached ?? 0;
  $("mTickets").textContent = breach ? `${open} (${breach} SLA)` : open;
}

async function loadProfile() {
  const res = await fetch(`/api/sessions/${encodeURIComponent(sessionId)}/profile`);
  const data = await res.json();
  if (!data.customer_id) {
    $("profileHint").textContent = "Look up an order, then verify. ORD-1005 is VIP.";
    $("profileKv").innerHTML = "";
    return;
  }
  const tier = data.tier || "standard";
  $("profileHint").textContent = `${data.name} · ${tier} · LTV ¥${data.lifetime_value}`;
  $("profileKv").innerHTML = `
    <div><dt>Customer</dt><dd>${data.customer_id}</dd></div>
    <div><dt>Tier</dt><dd class="${tier === "vip" ? "vip" : ""}">${tier}</dd></div>
    <div><dt>Email</dt><dd>${data.email_masked || data.email}</dd></div>
    <div><dt>Phone</dt><dd>${data.phone_masked || "—"}</dd></div>
    <div><dt>Points</dt><dd>${data.loyalty_points}</dd></div>
    <div><dt>Orders</dt><dd>${data.orders_count}</dd></div>`;
}

async function loadAssist() {
  const res = await fetch(`/api/sessions/${encodeURIComponent(sessionId)}/assist`);
  const data = await res.json();
  window.__assistDraft = data.suggested_reply || "";
  const pending = data.pending
    ? `Pending ${data.pending.action} ${data.pending.order_id} (¥${data.pending.amount})`
    : "No pending mutation";
  $("assistBox").textContent = `${pending}\n\n${data.suggested_reply || ""}`;
}

async function loadKb() {
  const res = await fetch("/api/kb/stats");
  const data = await res.json();
  $("kbSummary").textContent =
    `${data.document_count} policy documents · ${data.chunk_count} vectors · ${data.embedding_backend}`;
  $("kbKnobs").innerHTML = `
    <div class="knob"><span>chunk</span><strong>${data.chunk_size}</strong></div>
    <div class="knob"><span>overlap</span><strong>${data.chunk_overlap}</strong></div>
    <div class="knob"><span>top_k</span><strong>${data.top_k}</strong></div>`;
  $("kbDocs").innerHTML = (data.documents || [])
    .map(
      (d) => `<div class="row-card"><strong>${d.name}</strong>
      <span class="badge ok">${d.category}</span><br/>${d.bytes} bytes</div>`
    )
    .join("");
}

async function loadHealth() {
  const res = await fetch("/health");
  const data = await res.json();
  $("opsHealth").textContent = JSON.stringify(data, null, 2);
}

$("chatForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const msg = $("messageInput").value.trim();
  if (!msg) return;
  await sendChat(msg);
});

$("messageInput").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    $("chatForm").requestSubmit();
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
    $("panel-" + tab.dataset.tab).classList.add("active");
  });
});

$("kbSearchForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const q = $("kbQuery").value.trim();
  if (!q) return;
  const res = await fetch("/api/policies/search?" + new URLSearchParams({ q }));
  const data = await res.json();
  $("kbHits").innerHTML =
    (data.hits || [])
      .map(
        (h) => `<div class="row-card"><strong>${h.section || h.source}</strong>
      <span class="badge warn">${h.category}</span><br/>${(h.text || "").slice(0, 160)}…</div>`
      )
      .join("") || `<div class="row-card">No hits</div>`;
});

$("btnUseDraft").onclick = () => {
  $("humanMsg").value = window.__assistDraft || "";
};

$("btnHumanReply").onclick = async () => {
  const message = $("humanMsg").value.trim();
  if (!message) return;
  const res = await fetch(`/api/sessions/${encodeURIComponent(sessionId)}/human-reply`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, resume_bot: false }),
  });
  const data = await res.json();
  $("humanMsg").value = "";
  addMessage("bot", `[Agent]\n${data.message}`, { human: true });
  $("ctxBot").textContent = data.bot_paused ? "paused (human)" : "active";
  setPipeline("handoff");
};

$("btnResumeBot").onclick = async () => {
  await fetch(`/api/sessions/${encodeURIComponent(sessionId)}/resume-bot`, { method: "POST" });
  $("ctxBot").textContent = "active";
  addMessage("bot", "Bot resumed.");
  setPipeline("supervisor");
};

document.querySelectorAll("#csatStars button").forEach((btn) => {
  btn.addEventListener("click", async () => {
    await sendChat(`I'd rate this chat ${btn.dataset.score} stars`);
  });
});

$("refreshOrders").onclick = loadOrders;
$("refreshTickets").onclick = loadTickets;

$("btnReingest").onclick = async () => {
  $("btnReingest").textContent = "Ingesting…";
  const res = await fetch("/api/admin/reingest", { method: "POST" });
  const data = await res.json();
  $("btnReingest").textContent = "Re-ingest policies";
  await loadKb();
  await loadMetrics();
  $("opsDebug").textContent = JSON.stringify(data, null, 2);
};

$("btnReseed").onclick = async () => {
  await fetch("/api/admin/reseed", { method: "POST" });
  await Promise.all([loadOrders(), loadTickets(), loadMetrics()]);
};

Promise.all([loadOrders(), loadTickets(), loadMetrics(), loadKb(), loadHealth(), loadProfile(), loadAssist()]);
addMessage(
  "bot",
  "SteelShop Care online. Ask about policies, orders, payments, or refunds. VIP routing kicks in after you verify ORD-1005."
);
setPipeline("supervisor");
