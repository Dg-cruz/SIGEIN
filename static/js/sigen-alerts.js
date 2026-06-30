/**
 * SIGEIN — alertas padronizados (SweetAlert2).
 * Uso: SIGENAlert.error("mensagem"), SIGENAlert.success("Ok"), SIGENAlert.confirm("Deseja?")
 * window.alert() é substituído automaticamente quando Swal está disponível.
 */
window.SIGENAlert = (function () {
  var TITLES = {
    error: "Atenção",
    warning: "Aviso",
    info: "Informação",
    success: "Sucesso",
    question: "Confirmação",
  };

  function baseConfig(extra) {
    var cfg = {
      customClass: {
        popup: "sigen-swal",
        confirmButton: "sigen-swal-confirm",
        cancelButton: "sigen-swal-cancel",
      },
      buttonsStyling: false,
      confirmButtonText: "Entendi",
      cancelButtonText: "Cancelar",
      heightAuto: false,
    };
    if (!extra) return cfg;
    var merged = {};
    Object.keys(cfg).forEach(function (k) {
      merged[k] = cfg[k];
    });
    Object.keys(extra).forEach(function (k) {
      if (k === "customClass" && cfg.customClass && extra.customClass) {
        merged.customClass = Object.assign({}, cfg.customClass, extra.customClass);
      } else {
        merged[k] = extra[k];
      }
    });
    return merged;
  }

  function normalizeText(message) {
    return String(message == null ? "" : message).trim();
  }

  function fire(icon, message, extra) {
    if (typeof Swal === "undefined") {
      window.alert(normalizeText(message));
      return Promise.resolve();
    }
    var opts = baseConfig(extra || {});
    opts.icon = icon;
    opts.title = opts.title || TITLES[icon] || TITLES.info;
    opts.text = normalizeText(message);
    if (icon === "error") {
      opts.customClass.popup = "sigen-swal sigen-swal--error";
    } else if (icon === "success") {
      opts.customClass.popup = "sigen-swal sigen-swal--success";
    } else if (icon === "warning" || icon === "question") {
      opts.customClass.popup = "sigen-swal";
    }
    return Swal.fire(opts);
  }

  function error(message, extra) {
    return fire("error", message, extra);
  }

  function warning(message, extra) {
    return fire("warning", message, extra);
  }

  function info(message, extra) {
    return fire("info", message, extra);
  }

  function success(message, extra) {
    return fire("success", message, extra);
  }

  function alertMessage(message, extra) {
    return info(message, extra);
  }

  function confirm(message, extra) {
    var opts = Object.assign(
      {
        showCancelButton: true,
        confirmButtonText: "Confirmar",
        cancelButtonText: "Cancelar",
      },
      extra || {}
    );
    return fire("question", message, opts);
  }

  function confirmDanger(message, extra) {
    var opts = Object.assign(
      {
        showCancelButton: true,
        confirmButtonText: "Sim, excluir",
        cancelButtonText: "Cancelar",
        customClass: { popup: "sigen-swal sigen-swal--danger" },
        icon: "warning",
      },
      extra || {}
    );
    if (typeof Swal === "undefined") {
      return Promise.resolve({ isConfirmed: window.confirm(normalizeText(message)) });
    }
    opts.title = opts.title || "Excluir registro?";
    opts.text = normalizeText(message);
    return Swal.fire(baseConfig(opts));
  }

  function showThenBack(message, icon) {
    var fn = error;
    if (icon === "success") fn = success;
    else if (icon === "warning") fn = warning;
    else if (icon === "info") fn = info;
    return fn(message).then(function () {
      if (window.history.length > 1) {
        history.back();
      } else {
        window.location.href = "/dashboard";
      }
    });
  }

  function showPayload(payload) {
    if (!payload || !payload.message) return Promise.resolve();
    var icon = payload.icon || "error";
    if (icon === "success") return success(payload.message);
    if (icon === "warning") return warning(payload.message);
    if (icon === "info") return info(payload.message);
    return error(payload.message);
  }

  function shouldAjaxForm(form) {
    if (!form || form.tagName !== "FORM") return false;
    if ((form.method || "get").toLowerCase() !== "post") return false;
    if (form.dataset.sigenNoAjax === "true") return false;
    if (form.classList.contains("delete-form")) return false;
    var enc = (form.enctype || "").toLowerCase();
    if (enc.indexOf("multipart/form-data") !== -1) return false;
    return true;
  }

  function setFormBusy(form, busy) {
    if (!form) return;
    form.dataset.sigenSubmitting = busy ? "1" : "0";
    form.querySelectorAll('button[type="submit"], input[type="submit"]').forEach(function (btn) {
      btn.disabled = !!busy;
    });
  }

  function submitFormAjax(form) {
    setFormBusy(form, true);
    var url = form.getAttribute("action") || window.location.href;
    return fetch(url, {
      method: "POST",
      body: new FormData(form),
      headers: { "X-Requested-With": "XMLHttpRequest" },
      credentials: "same-origin",
      redirect: "follow",
    })
      .then(function (res) {
        var ct = (res.headers.get("content-type") || "").toLowerCase();
        if (ct.indexOf("application/json") !== -1) {
          return res.json().then(function (data) {
            if (data && (data.alert || (data.ok === false && data.message))) {
              return showPayload(data).then(function () {
                setFormBusy(form, false);
              });
            }
            if (res.redirected) {
              window.location.href = res.url;
              return;
            }
            setFormBusy(form, false);
            return error("Não foi possível concluir a operação. Tente novamente.");
          });
        }
        if (res.redirected) {
          window.location.href = res.url;
          return;
        }
        if (res.ok) {
          return res.text().then(function (html) {
            document.open();
            document.write(html);
            document.close();
          });
        }
        setFormBusy(form, false);
        return error("Não foi possível concluir a operação. Tente novamente.");
      })
      .catch(function () {
        setFormBusy(form, false);
        return error("Erro de conexão. Verifique sua rede e tente novamente.");
      });
  }

  function installAjaxFormPosts() {
    document.addEventListener(
      "submit",
      function (e) {
        if (e.defaultPrevented) return;
        var form = e.target;
        if (!shouldAjaxForm(form)) return;
        if (form.dataset.sigenSubmitting === "1") {
          e.preventDefault();
          return;
        }
        e.preventDefault();
        submitFormAjax(form);
      },
      false
    );
  }

  function installFlashAlert(payload) {
    if (!payload || !payload.message) return;
    showPayload(payload);
  }

  function installNativeAlertOverride() {
    if (typeof Swal === "undefined") return;
    window.alert = function (message) {
      return error(message);
    };
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      installNativeAlertOverride();
      installAjaxFormPosts();
    });
  } else {
    installNativeAlertOverride();
    installAjaxFormPosts();
  }

  return {
    alert: alertMessage,
    error: error,
    warning: warning,
    info: info,
    success: success,
    confirm: confirm,
    confirmDanger: confirmDanger,
    showThenBack: showThenBack,
    showPayload: showPayload,
    installNativeAlertOverride: installNativeAlertOverride,
    installAjaxFormPosts: installAjaxFormPosts,
    installFlashAlert: installFlashAlert,
  };
})();
