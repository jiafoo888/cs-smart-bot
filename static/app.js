const $ = (id) => document.getElementById(id);

let sessionId = "care-demo-1";

function badgeClass(status) {
  const s = (status || "").toLowerCase();
  if (["succeeded", "delivered", "shipped", "paid", "closed"].includes(s)) return "ok";
  if (["pending", "processing", "open", "assigned"].includes(s)) return "warn";
  return "bad";
}

function setPipeline(agent) {
  document.querySelectorAll("#pipeline li").forEach((li) => {
    const node = li.dataset.node;
    const on =
      node === "supervisor" ||
      node === agent ||
      (agent === "csat" && node === "smalltalk");
    li.classList.toggle("active", on);
  });
}

function addMessage(role, text, opts = {}) {
  const box = $("messages");
  const el = document.createElement("div");
  el.className = `bubble ${role === "user" ? "user" : "bot"}${opts.typing ? " typing" : ""}`;
  el.textContent = text;
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
  const scroller = box.parentElement;
  if (scroller) scroller.scrollTop = scroller.scrollHeight;
  else box.scrollTop = box.scrollHeight;
  return el;
}

async function sendChat(message) {
  const include_debug = $("debugToggle").checked;
  addMessage("user", message);
  $("messageInput").value = "";
  const typing = addMessage("bot", "SteelShop Care is drafting a reply…", { typing: true });
  $("sendBtn").disabled = true;
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
    $("ctxOrder").textContent = data.order_id || "—";
    $("ctxPayment").textContent = data.payment_id || "—";
    $("ctxAgent").textContent = data.agent || "—";
    $("ctxBot").textContent = data.bot_paused ? "paused (human)" : "active";
    setPipeline(data.agent);
    if (include_debug) {
      $("opsDebug").textContent = JSON.stringify(data.debug || {}, null, 2);
    }
    await Promise.all([loadOrders(), loadPayments(), loadTickets(), loadMetrics()]);
  } catch (err) {
    typing.remove();
    addMessage("bot", "Request failed: " + err.message);
  } finally {
    $("sendBtn").disabled = false;
  }
}

async function loadOrders() {
  const res = await fetch("/api/orders");
  const data = await res.json();
  $("orders").innerHTML = (data.items || [])
    .map(
      (o) => `<div class="row-card"><strong>${o.order_id}</strong>
      <span class="badge ${badgeClass(o.status)}">${o.status}</span><br/>
      ${o.product} · ¥${o.amount}<br/>${o.customer_name || o.customer_id}</div>`
    )
    .join("");
}

async function loadPayments() {
  const res = await fetch("/api/payments");
  const data = await res.json();
  $("payments").innerHTML = (data.items || [])
    .map(
      (p) => `<div class="row-card"><strong>${p.payment_id}</strong>
      <span class="badge ${badgeClass(p.status)}">${p.status}</span><br/>
      ${p.order_id} · ¥${p.amount} · ${p.method}</div>`
    )
    .join("");
}

async function loadTickets() {
  const res = await fetch("/api/tickets");
  const data = await res.json();
  $("tickets").innerHTML = (data.items || []).length
    ? data.items
        .map(
          (t) => `<div class="row-card"><strong>${t.ticket_id}</strong>
          <span class="badge ${badgeClass(t.status)}">${t.status}</span><br/>
          ${t.category} · ${t.order_id || "—"}<br/>${t.summary}</div>`
        )
        .join("")
    : `<div class="row-card">No tickets yet</div>`;
}

async function loadMetrics() {
  const res = await fetch("/api/metrics/overview");
  const data = await res.json();
  $("mOrders").textContent = data.orders_total ?? "—";
  $("mPay").textContent = data.payments_succeeded ?? "—";
  $("mChunks").textContent = data.kb?.chunk_count ?? "—";
  $("mTickets").textContent = data.tickets_open ?? "—";
}

async function loadKb() {
  const res = await fetch("/api/kb/stats");
  const data = await res.json();
  $("kbSummary").textContent =
    `${data.document_count} policy documents · ${data.chunk_count} vectors · backend ${data.embedding_backend}`;
  $("kbKnobs").innerHTML = `
    <div class="knob"><span>chunk size</span><strong>${data.chunk_size}</strong></div>
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

document.querySelectorAll(".session").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".session").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    sessionId = btn.dataset.session;
    $("sessionLabel").textContent = `session · ${sessionId}`;
    $("messages").innerHTML = "";
    addMessage(
      "bot",
      "Hi — welcome to SteelShop Care. I can answer store policies from our knowledge base, look up orders and payments, process refunds, or escalate to a human specialist."
    );
    $("ctxOrder").textContent = "—";
    $("ctxPayment").textContent = "—";
    $("ctxAgent").textContent = "—";
    $("ctxBot").textContent = "active";
    setPipeline(null);
  });
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
  $("kbHits").innerHTML = (data.hits || [])
    .map(
      (h) => `<div class="row-card"><strong>${h.section || h.source}</strong>
      <span class="badge warn">${h.category}</span><br/>${(h.text || "").slice(0, 160)}…</div>`
    )
    .join("") || `<div class="row-card">No hits</div>`;
});

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
  addMessage("bot", `[Human agent]\n${data.message}`);
  $("ctxBot").textContent = data.bot_paused ? "paused (human)" : "active";
  setPipeline("handoff");
};

$("btnResumeBot").onclick = async () => {
  await fetch(`/api/sessions/${encodeURIComponent(sessionId)}/resume-bot`, { method: "POST" });
  $("ctxBot").textContent = "active";
  addMessage("bot", "Bot resumed — I can take it from here.");
  setPipeline("supervisor");
};

document.querySelectorAll("#csatStars button").forEach((btn) => {
  btn.addEventListener("click", async () => {
    const score = btn.dataset.score;
    await sendChat(`I'd rate this chat ${score} stars`);
  });
});

$("refreshOrders").onclick = loadOrders;
$("refreshPayments").onclick = loadPayments;
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
  await Promise.all([loadOrders(), loadPayments(), loadTickets(), loadMetrics()]);
};

Promise.all([loadOrders(), loadPayments(), loadTickets(), loadMetrics(), loadKb(), loadHealth()]);
addMessage(
  "bot",
  "Hi — welcome to SteelShop Care. I can answer store policies from our knowledge base, look up orders and payments, process refunds, or escalate to a human specialist."
);
setPipeline("supervisor");
