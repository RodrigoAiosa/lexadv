/* LEX — chat da solicitação (atualização por polling a cada 5 s) */
(function () {
  "use strict";

  var root = document.querySelector("[data-chat]");
  if (!root) return;

  var list = root.querySelector("[data-chat-list]");
  var form = root.querySelector("[data-chat-form]");
  var errorBox = root.querySelector("[data-chat-error]");
  var csrf = (document.querySelector('meta[name="csrf-token"]') || {}).content || "";
  var seen = new Set();
  var lastCreated = null;

  list.querySelectorAll("[data-id]").forEach(function (li) {
    seen.add(li.getAttribute("data-id"));
    lastCreated = li.getAttribute("data-created");
  });
  scrollToEnd();

  function scrollToEnd() { list.scrollTop = list.scrollHeight; }

  function showError(text) {
    if (!errorBox) return;
    errorBox.textContent = text || "";
    errorBox.hidden = !text;
  }

  function formatDate(iso) {
    var d = new Date(iso);
    return isNaN(d) ? "" : d.toLocaleString("pt-BR", {
      timeZone: "America/Sao_Paulo", day: "2-digit", month: "2-digit", year: "numeric",
      hour: "2-digit", minute: "2-digit"
    });
  }

  function addMessage(msg) {
    if (seen.has(msg.id)) return;
    seen.add(msg.id);
    lastCreated = msg.created_at;
    var li = document.createElement("li");
    li.className = "msg " + (msg.mine ? "msg--mine" : "msg--other");
    li.setAttribute("data-id", msg.id);
    li.setAttribute("data-created", msg.created_at);
    var p = document.createElement("p");
    p.className = "prewrap";
    p.textContent = msg.body; // textContent evita injeção de HTML
    var t = document.createElement("time");
    t.textContent = formatDate(msg.created_at);
    li.appendChild(p);
    li.appendChild(t);
    list.appendChild(li);
  }

  function poll() {
    if (document.hidden) return;
    var url = root.getAttribute("data-messages-url");
    if (lastCreated) url += "?after=" + encodeURIComponent(lastCreated);
    fetch(url, { credentials: "same-origin" })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (data) {
        if (!data || !data.messages || !data.messages.length) return;
        var nearEnd = list.scrollHeight - list.scrollTop - list.clientHeight < 80;
        data.messages.forEach(addMessage);
        if (nearEnd) scrollToEnd();
      })
      .catch(function () { /* tenta de novo no próximo ciclo */ });
  }

  if (form) {
    var input = form.querySelector("textarea");
    var button = form.querySelector("button");

    input.addEventListener("keydown", function (event) {
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        form.requestSubmit();
      }
    });

    form.addEventListener("submit", function (event) {
      event.preventDefault();
      var body = input.value.trim();
      if (!body) return;
      button.disabled = true;
      showError("");
      fetch(root.getAttribute("data-send-url"), {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
        body: JSON.stringify({ body: body })
      })
        .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, json: j }; }); })
        .then(function (res) {
          if (!res.ok) { showError(res.json.error || "Não foi possível enviar a mensagem."); return; }
          input.value = "";
          addMessage(res.json.message);
          scrollToEnd();
        })
        .catch(function () { showError("Sem conexão. Tente novamente."); })
        .finally(function () { button.disabled = false; input.focus(); });
    });
  }

  window.setInterval(poll, 5000);
  document.addEventListener("visibilitychange", poll);
})();
