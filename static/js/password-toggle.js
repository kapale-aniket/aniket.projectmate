/* Show / hide password with eye icon on all password fields */
(function () {
  "use strict";

  function enhancePasswordFields(root) {
    var scope = root && root.querySelectorAll ? root : document;
    scope.querySelectorAll('input[type="password"]').forEach(function (input) {
      if (input.dataset.pmToggle === "0") return;
      if (input.closest(".pm-password-wrap")) return;

      var wrap = document.createElement("div");
      wrap.className = "pm-password-wrap";
      input.parentNode.insertBefore(wrap, input);
      wrap.appendChild(input);

      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "pm-password-toggle";
      btn.setAttribute("aria-label", "Show password");
      btn.setAttribute("title", "Show password");
      btn.innerHTML = '<i class="fas fa-eye" aria-hidden="true"></i>';

      btn.addEventListener("click", function () {
        var showing = input.type === "password";
        input.type = showing ? "text" : "password";
        var label = showing ? "Hide password" : "Show password";
        btn.setAttribute("aria-label", label);
        btn.setAttribute("title", label);
        var icon = btn.querySelector("i");
        if (icon) {
          icon.className = showing ? "fas fa-eye-slash" : "fas fa-eye";
        }
      });

      wrap.appendChild(btn);
    });
  }

  function init() {
    enhancePasswordFields(document);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

  document.body.addEventListener("htmx:afterSwap", function (evt) {
    enhancePasswordFields(evt.detail && evt.detail.target ? evt.detail.target : document);
  });

  window.PMPasswordToggle = { enhance: enhancePasswordFields };
})();
