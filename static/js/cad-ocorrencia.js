/**
 * Busca de endereço por CEP (ViaCEP via backend /cad/api/cep).
 * Espera IDs: cep, logradouro, bairro, cidade, uf, complemento (opcionais).
 */
(function () {
  function onlyDigits(v) {
    return String(v || "").replace(/\D/g, "");
  }

  function maskCep(v) {
    var d = onlyDigits(v).slice(0, 8);
    if (d.length > 5) return d.slice(0, 5) + "-" + d.slice(5);
    return d;
  }

  function setMsg(el, text, ok) {
    if (!el) return;
    el.textContent = text || "";
    el.classList.toggle("is-ok", !!ok);
    el.classList.toggle("is-error", !ok && !!text);
  }

  function fill(data) {
    var map = {
      logradouro: data.logradouro,
      bairro: data.bairro,
      cidade: data.cidade,
      uf: data.uf,
      complemento: data.complemento,
    };
    Object.keys(map).forEach(function (id) {
      var node = document.getElementById(id);
      if (node && map[id]) node.value = map[id];
    });
    var cep = document.getElementById("cep");
    if (cep && data.cep) cep.value = data.cep;
  }

  function buscarCep() {
    var cepInput = document.getElementById("cep");
    var msg = document.getElementById("cep-msg");
    var btn = document.getElementById("btn-buscar-cep");
    if (!cepInput) return;
    var cep = onlyDigits(cepInput.value);
    if (cep.length !== 8) {
      setMsg(msg, "Informe um CEP com 8 dígitos.", false);
      return;
    }
    if (btn) {
      btn.disabled = true;
      btn.innerHTML = '<i class="fas fa-spinner fa-spin" aria-hidden="true"></i>';
    }
    setMsg(msg, "Consultando CEP…", true);
    fetch("/cad/api/cep/" + cep)
      .then(function (r) {
        return r.json();
      })
      .then(function (data) {
        if (!data.ok) {
          setMsg(msg, data.error || "CEP não encontrado.", false);
          return;
        }
        fill(data);
        setMsg(msg, "Endereço preenchido via ViaCEP.", true);
        var numero = document.getElementById("numero");
        if (numero) numero.focus();
      })
      .catch(function () {
        setMsg(msg, "Falha ao consultar CEP.", false);
      })
      .finally(function () {
        if (btn) {
          btn.disabled = false;
          btn.innerHTML = '<i class="fas fa-search" aria-hidden="true"></i>';
        }
      });
  }

  function bind() {
    var cepInput = document.getElementById("cep");
    var btn = document.getElementById("btn-buscar-cep");
    if (!cepInput) return;
    cepInput.addEventListener("input", function () {
      this.value = maskCep(this.value);
    });
    cepInput.addEventListener("blur", function () {
      if (onlyDigits(this.value).length === 8) buscarCep();
    });
    if (btn) btn.addEventListener("click", buscarCep);

    var anon = document.getElementById("solicitante_anonimo");
    function toggleAnon() {
      var disabled = !!(anon && anon.checked);
      ["solicitante_nome", "solicitante_documento"].forEach(function (id) {
        var el = document.getElementById(id);
        if (!el) return;
        el.disabled = disabled;
        if (disabled) el.value = "";
      });
    }
    if (anon) {
      anon.addEventListener("change", toggleAnon);
      toggleAnon();
    }

    var emEvento = document.getElementById("em_evento");
    var eventoField = document.getElementById("evento_descricao");
    function toggleEvento() {
      if (!eventoField) return;
      var on = !!(emEvento && emEvento.checked);
      eventoField.disabled = !on;
      if (!on) eventoField.value = "";
    }
    if (emEvento) {
      emEvento.addEventListener("change", toggleEvento);
      toggleEvento();
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bind);
  } else {
    bind();
  }
})();
