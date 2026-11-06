/* LEX — comportamentos gerais da interface */
(function () {
  "use strict";

  // Menu mobile
  var toggle = document.querySelector("[data-nav-toggle]");
  var menu = document.getElementById("menu");
  if (toggle && menu) {
    toggle.addEventListener("click", function () {
      var open = menu.classList.toggle("is-open");
      toggle.setAttribute("aria-expanded", String(open));
    });
  }

  // Fechar avisos
  document.querySelectorAll("[data-flash-close]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var box = btn.closest(".flash");
      if (box) box.remove();
    });
  });

  // Confirmação antes de ações importantes
  document.addEventListener("click", function (event) {
    var el = event.target.closest("[data-confirm]");
    if (el && !window.confirm(el.getAttribute("data-confirm"))) {
      event.preventDefault();
    }
  });

  // Evita envio duplo de formulários
  document.querySelectorAll("form").forEach(function (form) {
    form.addEventListener("submit", function (event) {
      if (form.hasAttribute("data-chat-form")) return;
      var submitter = event.submitter;
      window.setTimeout(function () {
        form.querySelectorAll("button[type=submit]").forEach(function (b) {
          if (b !== submitter) b.disabled = true;
        });
        if (submitter) submitter.setAttribute("aria-busy", "true");
      }, 0);
    });
  });

  // Contador de caracteres
  document.querySelectorAll("textarea[data-counter]").forEach(function (area) {
    var out = area.parentElement.querySelector("[data-counter-out]");
    if (!out) return;
    var update = function () { out.textContent = String(area.value.length); };
    area.addEventListener("input", update);
    update();
  });

  // Selo de notificações não lidas
  var bell = document.querySelector("[data-notifications-url]");
  var badge = document.querySelector("[data-notifications-badge]");
  function refreshBadge() {
    if (!bell || !badge || document.hidden) return;
    fetch(bell.getAttribute("data-notifications-url"), { credentials: "same-origin" })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (data) {
        if (!data) return;
        badge.textContent = data.unread > 99 ? "99+" : String(data.unread);
        badge.hidden = !data.unread;
      })
      .catch(function () { /* silencioso */ });
  }
  if (bell) {
    refreshBadge();
    window.setInterval(refreshBadge, 30000);
    document.addEventListener("visibilitychange", refreshBadge);
  }
})();
