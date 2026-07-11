/* Global toast notifications for Aniket.ProjectMate */
(function (window, document) {
  "use strict";

  var ICONS = {
    success: "fa-circle-check",
    error: "fa-circle-xmark",
    danger: "fa-circle-xmark",
    warning: "fa-triangle-exclamation",
    info: "fa-circle-info",
  };

  function ensureContainer() {
    var el = document.getElementById("pmToastContainer");
    if (el) return el;
    el = document.createElement("div");
    el.id = "pmToastContainer";
    el.className = "toast-container position-fixed top-0 end-0 p-3 pm-toast-container";
    el.setAttribute("aria-live", "polite");
    el.setAttribute("aria-atomic", "true");
    document.body.appendChild(el);
    return el;
  }

  function normalizeType(type) {
    type = (type || "info").toLowerCase();
    if (type === "error") return "danger";
    if (type.indexOf("success") !== -1) return "success";
    if (type.indexOf("danger") !== -1 || type.indexOf("error") !== -1) return "danger";
    if (type.indexOf("warning") !== -1) return "warning";
    return "info";
  }

  function showToast(message, type, delay) {
    if (!message) return;
    type = normalizeType(type);
    delay = delay || (type === "danger" ? 7000 : 4500);
    var container = ensureContainer();
    var icon = ICONS[type] || ICONS.info;
    var toastEl = document.createElement("div");
    toastEl.className = "toast pm-toast pm-toast-" + type + " align-items-center border-0";
    toastEl.setAttribute("role", "alert");
    toastEl.setAttribute("aria-live", "assertive");
    toastEl.setAttribute("aria-atomic", "true");
    toastEl.innerHTML =
      '<div class="d-flex">' +
      '<div class="toast-body">' +
      '<span class="pm-toast-icon"><i class="fas ' + icon + '"></i></span>' +
      '<span class="pm-toast-text"></span>' +
      "</div>" +
      '<button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>' +
      "</div>";
    toastEl.querySelector(".pm-toast-text").textContent = message;
    container.appendChild(toastEl);

    if (window.bootstrap && bootstrap.Toast) {
      var t = new bootstrap.Toast(toastEl, { autohide: true, delay: delay });
      toastEl.addEventListener("hidden.bs.toast", function () {
        toastEl.remove();
      });
      t.show();
    } else {
      toastEl.classList.add("show");
      setTimeout(function () {
        toastEl.remove();
      }, delay);
    }
  }

  function scrollUpAfterSuccess() {
    var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    var behavior = reduce ? "auto" : "smooth";
    var dash = document.getElementById("dash-content");
    var feedbackTop = document.getElementById("feedback-top");
    var target = dash || feedbackTop;
    if (target) {
      target.scrollIntoView({ behavior: behavior, block: "start" });
      return;
    }
    window.scrollTo({ top: 0, behavior: behavior });
  }

  function initServerToasts() {
    var toasts = document.querySelectorAll("#pmToastContainer .toast");
    var hasSuccess = false;
    toasts.forEach(function (el) {
      if (el.classList.contains("pm-toast-success")) hasSuccess = true;
      if (!window.bootstrap || !bootstrap.Toast) return;
      var delay = parseInt(el.getAttribute("data-bs-delay") || "4500", 10);
      var t = bootstrap.Toast.getOrCreateInstance(el, { autohide: true, delay: delay });
      el.addEventListener("hidden.bs.toast", function () {
        el.remove();
      });
      t.show();
    });
    if (hasSuccess) {
      window.setTimeout(scrollUpAfterSuccess, 80);
    }
  }

  window.PMToast = {
    show: showToast,
    success: function (msg, delay) {
      showToast(msg, "success", delay);
    },
    error: function (msg, delay) {
      showToast(msg, "danger", delay);
    },
    warning: function (msg, delay) {
      showToast(msg, "warning", delay);
    },
    info: function (msg, delay) {
      showToast(msg, "info", delay);
    },
  };

  document.addEventListener("DOMContentLoaded", initServerToasts);

  // HTMX: show toast from response headers if present
  document.body.addEventListener("htmx:afterRequest", function (e) {
    var xhr = e.detail && e.detail.xhr;
    if (!xhr) return;
    var msg = xhr.getResponseHeader("X-Toast-Message");
    var type = xhr.getResponseHeader("X-Toast-Type") || "success";
    if (msg) showToast(decodeURIComponent(msg), type);
    if (e.detail.successful === false && e.detail.failed) {
      // network / 5xx
      if (xhr.status >= 500) showToast("Something went wrong. Please try again.", "danger");
    }
  });

  document.body.addEventListener("htmx:responseError", function () {
    showToast("Request failed. Please try again.", "danger");
  });

  document.body.addEventListener("htmx:sendError", function () {
    showToast("Network error. Check your connection.", "danger");
  });
})(window, document);
