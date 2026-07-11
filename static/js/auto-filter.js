/* Auto-apply filters on select/change; reset clears query params */
(function () {
  "use strict";

  function debounce(fn, wait) {
    var t;
    return function () {
      var ctx = this, args = arguments;
      clearTimeout(t);
      t = setTimeout(function () { fn.apply(ctx, args); }, wait);
    };
  }

  function submitFilterForm(form) {
    // Drop empty fields so URLs stay clean
    var fd = new FormData(form);
    var params = new URLSearchParams();
/* Keep explicit "all" / empty select values so resettable filters work */
    fd.forEach(function (value, key) {
      var str = value === null ? "" : String(value).trim();
      if (str !== "" || key === "status" || key === "featured" || key === "active" || key === "tab") {
        // skip blank text search fields only
        if (str === "" && (key === "q" || key === "college" || key === "course")) return;
        if (str === "" && key !== "status" && key !== "featured" && key !== "active" && key !== "tab") return;
        params.append(key, str);
      }
    });
    var base = form.getAttribute("action") || window.location.pathname;
    var qs = params.toString();
    window.location.href = qs ? base + "?" + qs : base;
  }

  function bindAutoFilter(form) {
    if (form.dataset.autoFilterBound) return;
    form.dataset.autoFilterBound = "1";

    var debouncedSubmit = debounce(function () {
      submitFilterForm(form);
    }, 450);

    form.querySelectorAll("select, input[type='checkbox'], input[type='radio']").forEach(function (el) {
      el.addEventListener("change", function () {
        submitFilterForm(form);
      });
    });

    form.querySelectorAll("input[type='search'], input[type='text'], input:not([type])").forEach(function (el) {
      el.addEventListener("input", debouncedSubmit);
      el.addEventListener("keydown", function (e) {
        if (e.key === "Enter") {
          e.preventDefault();
          submitFilterForm(form);
        }
      });
    });

    form.addEventListener("submit", function (e) {
      e.preventDefault();
      submitFilterForm(form);
    });
  }

  function bindResetButtons() {
    document.querySelectorAll("[data-reset-filter]").forEach(function (btn) {
      btn.addEventListener("click", function (e) {
        e.preventDefault();
        var url = btn.getAttribute("href") || btn.getAttribute("data-reset-filter") || window.location.pathname;
        window.location.href = url;
      });
    });
  }

  function init() {
    document.querySelectorAll("form[data-auto-filter]").forEach(bindAutoFilter);
    bindResetButtons();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
