/* Cadastro: campos de OAB (só para advogados), máscaras e validação de e-mail/telefone, cidades do estado */
(function () {
  "use strict";

  var roles = document.querySelectorAll("input[name=role]");
  var box = document.getElementById("oab-box");
  var oabNumber = document.getElementById("oab_number");
  var oabState = document.getElementById("oab_state");
  var state = document.getElementById("state");
  var city = document.getElementById("city");
  var email = document.getElementById("email");
  var phone = document.getElementById("phone");

  function isLawyer() {
    var checked = document.querySelector("input[name=role]:checked");
    return !!checked && checked.value === "advogado";
  }

  function syncRole() {
    if (!box) return;
    var on = isLawyer();
    box.hidden = !on;
    oabNumber.required = on;
    oabState.required = on;
    if (on && !oabState.value && state.value) oabState.value = state.value;
  }

  roles.forEach(function (r) { r.addEventListener("change", syncRole); });
  syncRole();

  // OAB: só dígitos (e uma letra opcional no fim, como em 12345A)
  if (oabNumber) {
    oabNumber.addEventListener("input", function () {
      oabNumber.value = oabNumber.value.toUpperCase().replace(/[^0-9A-Z]/g, "").replace(/^([0-9]*)([A-Z]).*$/, "$1$2");
    });
  }

  // E-mail: bloqueia espaços e caracteres fora do padrão enquanto digita
  if (email) {
    email.addEventListener("input", function () {
      var plain = email.value.normalize("NFD").replace(/[\u0300-\u036f]/g, ""); // José -> Jose
      email.value = plain.replace(/[^A-Za-z0-9._%+\-@]/g, "").toLowerCase();
      email.setCustomValidity("");
    });
    email.addEventListener("invalid", function () {
      email.setCustomValidity(email.value ? "Informe um e-mail válido, como nome@dominio.com.br" : "");
    });
  }

  // Telefone: máscara (11) 91234-5678 ou (11) 1234-5678; só aceita números
  function maskPhone(raw) {
    var d = raw.replace(/\D/g, "");
    if (d.length > 11 && d.indexOf("55") === 0) d = d.slice(2);
    d = d.slice(0, 11);
    if (!d.length) return "";
    if (d.length <= 2) return "(" + d;
    var head = "(" + d.slice(0, 2) + ") ";
    if (d.length === 11) return head + d.slice(2, 7) + "-" + d.slice(7);
    return head + d.slice(2, 6) + (d.length > 6 ? "-" + d.slice(6) : "");
  }
  if (phone) {
    phone.addEventListener("input", function () {
      phone.value = maskPhone(phone.value);
      phone.setCustomValidity("");
    });
    phone.addEventListener("invalid", function () {
      phone.setCustomValidity("Informe o telefone com DDD, como (11) 91234-5678");
    });
    phone.value = maskPhone(phone.value);
  }

  // Cidade: só as cidades do estado escolhido (lista própria do LEX, base do IBGE)
  var cache = {};
  function fillCities(names) {
    city.innerHTML = "";
    var first = document.createElement("option");
    first.value = "";
    first.textContent = "Selecione a cidade";
    city.appendChild(first);
    names.forEach(function (n) {
      var o = document.createElement("option");
      o.value = n;
      o.textContent = n;
      city.appendChild(o);
    });
    city.disabled = false;
  }
  function loadCities(uf) {
    city.disabled = true;
    city.innerHTML = "";
    var wait = document.createElement("option");
    wait.value = "";
    wait.textContent = uf ? "Carregando cidades..." : "Escolha o estado primeiro";
    city.appendChild(wait);
    if (!uf) return;
    if (cache[uf]) return fillCities(cache[uf]);
    fetch("/cidades/" + encodeURIComponent(uf), { credentials: "same-origin" })
      .then(function (r) { return r.ok ? r.json() : Promise.reject(); })
      .then(function (names) {
        cache[uf] = names;
        if (state.value === uf) fillCities(names);
      })
      .catch(function () { wait.textContent = "Não foi possível carregar as cidades. Recarregue a página."; });
  }

  if (state && city) {
    state.addEventListener("change", function () {
      loadCities(state.value);
      if (isLawyer() && !oabState.value) oabState.value = state.value;
    });
    // Se a página já veio com as cidades (erro de validação), não busca de novo
    if (state.value && city.options.length <= 1) loadCities(state.value);
  }
})();
