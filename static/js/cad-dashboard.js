/**
 * Personalização dos widgets do dashboard CAD.
 */
(function () {
  var modal = document.getElementById("cad-widget-modal");
  var listEl = document.getElementById("cad-widget-list");
  var emptyEl = document.getElementById("cad-widget-empty");
  var grid = document.getElementById("cad-kpi-grid");
  var emptyGrid = document.getElementById("cad-widgets-empty");
  var addBtn = document.getElementById("btn-add-widget");
  if (!modal || !grid || !addBtn) return;

  function esc(t) {
    var d = document.createElement("div");
    d.textContent = t == null ? "" : String(t);
    return d.innerHTML;
  }

  function syncEmpty() {
    var has = grid.querySelectorAll("[data-widget-id]").length > 0;
    if (emptyGrid) emptyGrid.hidden = has;
  }

  function closeModal() {
    modal.style.display = "none";
    modal.setAttribute("aria-hidden", "true");
  }

  function openModal() {
    modal.style.display = "block";
    modal.setAttribute("aria-hidden", "false");
    loadDisponiveis();
  }

  function renderWidget(w) {
    var art = document.createElement("article");
    art.className = "cad-kpi cad-kpi--" + esc(w.tone || "muted");
    art.setAttribute("data-widget-id", w.id);
    art.setAttribute("data-widget-key", w.widget_key);
    art.innerHTML =
      '<button type="button" class="cad-kpi__remove" data-remove-widget="' + w.id + '" title="Remover quadro" aria-label="Remover">×</button>' +
      '<div class="cad-kpi__top"><span class="cad-kpi__icon"><i class="fas ' + esc(w.icon) + '"></i></span>' +
      '<span class="cad-kpi__hint">' + esc(w.subtitle) + '</span></div>' +
      '<div class="cad-kpi__value">' + esc(w.value) + '</div>' +
      '<div class="cad-kpi__label">' + esc(w.label) + '</div>';
    grid.appendChild(art);
    syncEmpty();
  }

  function loadDisponiveis() {
    fetch("/cad/api/dashboard/widgets/disponiveis", { credentials: "same-origin" })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var itens = data.itens || [];
        if (!itens.length) {
          listEl.innerHTML = "";
          emptyEl.hidden = false;
          return;
        }
        emptyEl.hidden = true;
        var groups = {};
        itens.forEach(function (i) {
          if (!groups[i.group]) groups[i.group] = [];
          groups[i.group].push(i);
        });
        listEl.innerHTML = Object.keys(groups).map(function (g) {
          return '<div class="cad-modal__group"><div class="cad-modal__group-title">' + esc(g) + '</div>' +
            groups[g].map(function (i) {
              return '<button type="button" class="cad-modal__pick" data-key="' + esc(i.key) + '">' +
                '<i class="fas ' + esc(i.icon) + '"></i><span><strong>' + esc(i.label) + '</strong><small>' + esc(i.subtitle) + '</small></span></button>';
            }).join("") + '</div>';
        }).join("");
      });
  }

  function addWidget(key) {
    fetch("/cad/api/dashboard/widgets", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ widget_key: key }),
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (!data.ok) return;
        renderWidget(data.widget);
        loadDisponiveis();
      });
  }

  function removeWidget(id) {
    fetch("/cad/api/dashboard/widgets/" + id, {
      method: "DELETE",
      credentials: "same-origin",
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (!data.ok) return;
        var node = grid.querySelector('[data-widget-id="' + id + '"]');
        if (node) node.remove();
        syncEmpty();
      });
  }

  addBtn.addEventListener("click", openModal);
  modal.addEventListener("click", function (e) {
    if (e.target.closest("[data-close='cad-widget-modal']")) closeModal();
  });
  listEl.addEventListener("click", function (e) {
    var btn = e.target.closest("[data-key]");
    if (!btn) return;
    addWidget(btn.getAttribute("data-key"));
  });
  grid.addEventListener("click", function (e) {
    var btn = e.target.closest("[data-remove-widget]");
    if (!btn) return;
    e.preventDefault();
    removeWidget(btn.getAttribute("data-remove-widget"));
  });
  syncEmpty();
})();
