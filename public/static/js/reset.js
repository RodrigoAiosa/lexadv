/* Recuperação de senha: lê o token do fragmento da URL (#access_token=...) e o põe no formulário. */
(function () {
  "use strict";
  var form = document.getElementById("reset-form");
  var box = document.getElementById("reset-invalid");
  var msg = document.getElementById("reset-invalid-msg");
  var field = document.getElementById("access_token");
  if (!form || !field) return;

  var params = new URLSearchParams(window.location.hash.replace(/^#/, ""));
  var token = params.get("access_token");
  var error = params.get("error_description") || params.get("error");

  // Tira o token da barra de endereço e do histórico.
  if (window.location.hash) {
    history.replaceState(null, "", window.location.pathname);
  }

  if (token && params.get("type") === "recovery") {
    field.value = token;
  } else if (!field.value) {
    // Sem token: pode ser reenvio do formulário com erro (token já removido) ou link inválido.
    if (!document.querySelector(".flash")) {
      msg.textContent = error
        ? "Este link expirou ou já foi usado. Peça um novo link de recuperação."
        : "Link inválido. Abra o link que enviamos por e-mail ou peça um novo.";
    }
    box.hidden = false;
    form.hidden = true;
  }
})();
