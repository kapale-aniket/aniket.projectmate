/**
 * Mark mandatory form fields with a red asterisk on their labels.
 * Works with HTML required / data-pm-required (set by Django form patch).
 */
(function () {
  function markRequiredAsterisks(scope) {
    var root = scope && scope.querySelectorAll ? scope : document;

    function addStar(label) {
      if (!label || label.querySelector(".pm-required")) return;
      label.classList.add("is-required");
      var star = document.createElement("span");
      star.className = "pm-required";
      star.setAttribute("aria-hidden", "true");
      star.textContent = " *";
      label.appendChild(star);
    }

    function findLabelFor(el) {
      if (el.id) {
        try {
          var byFor = root.querySelector('label[for="' + CSS.escape(el.id) + '"]');
          if (byFor) return byFor;
        } catch (err) {
          var safeId = el.id.replace(/\\/g, "\\\\").replace(/"/g, '\\"');
          var byFor2 = root.querySelector('label[for="' + safeId + '"]');
          if (byFor2) return byFor2;
        }
      }
      var wrap = el.closest(
        ".mb-3, .mb-2, .pm-project-form__field, .form-group, .col-12, .col-md-6, .col-md-4, .col-lg-6, [class*='col-']"
      );
      if (wrap) {
        var label = wrap.querySelector("label.form-label, .form-label, label:not(.form-check-label)");
        if (label) return label;
        var spanLabel = wrap.querySelector("span.form-label");
        if (spanLabel) return spanLabel;
      }
      var parentLabel = el.closest("label");
      if (parentLabel) return parentLabel;
      return null;
    }

    root
      .querySelectorAll(
        "input[required], select[required], textarea[required], [data-pm-required='1'], [aria-required='true']"
      )
      .forEach(function (el) {
        if (el.type === "hidden") return;
        if (el.type === "radio") {
          var group =
            el.closest(".pm-star-rating") ||
            el.closest('[role="radiogroup"]') ||
            el.closest(".mb-3, .mb-2, .pm-project-form__field");
          if (group) {
            var groupLabel =
              group.previousElementSibling &&
              (group.previousElementSibling.matches("label, .form-label, span.form-label")
                ? group.previousElementSibling
                : null);
            if (!groupLabel && group.parentElement) {
              groupLabel = group.parentElement.querySelector(
                ":scope > label.form-label, :scope > .form-label, :scope > span.form-label"
              );
            }
            if (!groupLabel && group.parentElement) {
              groupLabel = group.parentElement.querySelector(
                "label.form-label, .form-label, span.form-label"
              );
            }
            addStar(groupLabel);
          }
          return;
        }
        if (el.type === "checkbox") {
          var checkWrap = el.closest(".form-check");
          var checkLabel =
            (el.id && root.querySelector('label[for="' + el.id + '"]')) ||
            (checkWrap && checkWrap.querySelector("label")) ||
            el.closest("label");
          addStar(checkLabel);
          return;
        }
        addStar(findLabelFor(el));
      });
  }

  function run(scope) {
    markRequiredAsterisks(scope || document);
  }

  window.PMMarkRequiredAsterisks = run;

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      run(document);
    });
  } else {
    run(document);
  }

  document.body.addEventListener("htmx:afterSwap", function (evt) {
    run(evt.detail && evt.detail.target ? evt.detail.target : document);
  });
})();
