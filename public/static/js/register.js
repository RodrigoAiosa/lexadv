/* Cadastro: campos de OAB (só para advogados) e lista de cidades por estado (IBGE) */
(function () {
  "use strict";

  var roles = document.querySelectorAll("input[name=role]");
  var box = document.getElementById("oab-box");
  var oabNumber = document.getElementById("oab_number");
  var oabState = document.getElementById("oab_state");
  var state = document.getElementById("state");
  var city = document.getElementById("city");
  var list = document.getElementById("cidades");

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

  // Só dígitos (e uma letra opcional no fim, como em 12345A) no número da OAB
  if (oabNumber) {
    oabNumber.addEventListener("input", function () {
      oabNumber.value = oabNumber.value.toUpperCase().replace(/[^0-9A-Z]/g, "").replace(/^([0-9]*)([A-Z]).*$/, "$1$2");
    });
  }

  // Cidades do estado escolhido, via API pública do IBGE (se falhar, o campo continua livre)
  var cache = {};
  function loadCities(uf) {
    list.innerHTML = "";
    if (!uf) return;
    var fill = function (names) {
      var frag = document.createDocumentFragment();
      names.forEach(function (n) {
        var o = document.createElement("option");
        o.value = n;
        frag.appendChild(o);
      });
      list.appendChild(frag);
    };
    if (cache[uf]) return fill(cache[uf]);
    fetch("https://servicodados.ibge.gov.br/api/v1/localidades/estados/" + uf + "/municipios?orderBy=nome")
      .then(function (r) { return r.ok ? r.json() : []; })
      .then(function (data) {
        cache[uf] = data.map(function (m) { return m.nome; });
        if (state.value === uf) fill(cache[uf]);
      })
      .catch(function () { /* sem lista: digitação livre */ });
  }

  if (state && city && list) {
    state.addEventListener("change", function () {
      loadCities(state.value);
      if (isLawyer() && !oabState.value) oabState.value = state.value;
    });
    loadCities(state.value);
  }
})();
