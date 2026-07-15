(function () {
  var formFiltros = document.getElementById("frota-ativos-filtros");
  var formAtivo = document.getElementById("frota-ativo-form");
  var marcaSel = document.getElementById("marca");
  var modeloSel = document.getElementById("modelo");
  var anoInput = document.getElementById("ano_modelo");
  var placaInput = document.getElementById("placa");
  var timer = null;

  function filterModelos() {
    if (!marcaSel || !modeloSel) return;
    var marca = marcaSel.value;
    var current = modeloSel.value;
    var stillValid = false;
    Array.prototype.forEach.call(modeloSel.options, function (opt) {
      if (!opt.value) {
        opt.hidden = false;
        return;
      }
      var match = opt.getAttribute("data-marca") === marca;
      opt.hidden = !match;
      if (match && opt.value === current) stillValid = true;
    });
    if (!stillValid) modeloSel.value = "";
    modeloSel.disabled = !marca;
  }

  if (marcaSel) {
    marcaSel.addEventListener("change", filterModelos);
    filterModelos();
  }

  function maskAnoModelo(value) {
    var digits = (value || "").replace(/\D/g, "").slice(0, 8);
    if (digits.length <= 4) return digits;
    return digits.slice(0, 4) + "/" + digits.slice(4);
  }

  if (anoInput) {
    anoInput.addEventListener("input", function () {
      var start = anoInput.selectionStart;
      var before = anoInput.value;
      anoInput.value = maskAnoModelo(anoInput.value);
      if (document.activeElement === anoInput && typeof start === "number") {
        var diff = anoInput.value.length - before.length;
        var pos = Math.max(0, start + diff);
        anoInput.setSelectionRange(pos, pos);
      }
    });
  }

  if (placaInput) {
    function formatPlaca(value) {
      var raw = (value || "").replace(/[^A-Za-z0-9]/g, "").toUpperCase().slice(0, 7);
      if (/^[A-Z]{3}\d{4}$/.test(raw)) {
        return raw.slice(0, 3) + "-" + raw.slice(3);
      }
      return raw;
    }
    placaInput.addEventListener("input", function () {
      placaInput.value = formatPlaca(placaInput.value);
    });
  }

  if (formFiltros) {
    function submitFiltros() {
      formFiltros.requestSubmit ? formFiltros.requestSubmit() : formFiltros.submit();
    }
    formFiltros.querySelectorAll("[data-filter-auto]").forEach(function (el) {
      el.addEventListener("change", submitFiltros);
    });
    formFiltros.querySelectorAll("[data-filter-text]").forEach(function (el) {
      el.addEventListener("input", function () {
        clearTimeout(timer);
        timer = setTimeout(submitFiltros, 400);
      });
      el.addEventListener("keydown", function (ev) {
        if (ev.key === "Enter") {
          ev.preventDefault();
          clearTimeout(timer);
          submitFiltros();
        }
      });
    });
  }

  if (formAtivo) {
    formAtivo.addEventListener("submit", function (ev) {
      if (anoInput && !/^\d{4}\/\d{4}$/.test(anoInput.value.trim())) {
        ev.preventDefault();
        anoInput.focus();
        anoInput.reportValidity();
      }
    });
  }
})();
