/* Aniket.ProjectMate — frontend interactions */
(function () {
  "use strict";

  function getCsrfToken() {
    // Prefer cookie (stays correct after login); fall back to hidden input
    const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    if (match) return decodeURIComponent(match[1]);
    const input = document.querySelector("[name=csrfmiddlewaretoken]");
    return input && input.value ? input.value : "";
  }

  function syncCsrfInputs() {
    const token = getCsrfToken();
    if (!token) return;
    document.querySelectorAll("[name=csrfmiddlewaretoken]").forEach(function (input) {
      input.value = token;
    });
  }

  function applyTheme(theme) {
    const next = theme === "dark" ? "dark" : "light";
    document.documentElement.setAttribute("data-theme", next);
    document.cookie = "theme=" + next + ";path=/;max-age=" + 60 * 60 * 24 * 365 + ";SameSite=Lax";
    document.querySelectorAll("[data-theme-icon]").forEach((icon) => {
      icon.className = next === "dark" ? "fas fa-sun" : "fas fa-moon";
    });
    document.querySelectorAll("[data-theme-toggle]").forEach((btn) => {
      btn.setAttribute("aria-label", next === "dark" ? "Switch to light mode" : "Switch to dark mode");
      btn.setAttribute("title", next === "dark" ? "Light mode" : "Dark mode");
    });
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) {
      meta.setAttribute(
        "content",
        next === "dark" ? "#0b1220" : meta.getAttribute("data-light-color") || "#1a365d"
      );
    }
  }

  function syncTheme(theme, url) {
    if (!url) return;
    const body = new URLSearchParams();
    body.set("theme", theme);
    fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
        "X-CSRFToken": getCsrfToken(),
        "X-Requested-With": "XMLHttpRequest",
      },
      body: body.toString(),
      credentials: "same-origin",
    }).catch(function () {});
  }

  function bindThemeToggle() {
    document.querySelectorAll("[data-theme-toggle]").forEach((btn) => {
      if (btn.dataset.bound === "1") return;
      btn.dataset.bound = "1";
      btn.addEventListener("click", function (e) {
        e.preventDefault();
        e.stopPropagation();
        const current = document.documentElement.getAttribute("data-theme") || "light";
        const next = current === "dark" ? "light" : "dark";
        applyTheme(next);
        syncTheme(next, btn.getAttribute("data-theme-url"));
      });
    });
  }

  const themeMeta = document.querySelector('meta[name="theme-color"]');
  if (themeMeta && !themeMeta.getAttribute("data-light-color")) {
    themeMeta.setAttribute("data-light-color", themeMeta.getAttribute("content") || "#1a365d");
  }

  bindThemeToggle();
  syncCsrfInputs();

  // Leaving dashboard/login for Home should not leave dashboard in Back history
  function bindHistoryReplaceLinks(root) {
    (root || document).querySelectorAll("a[data-history-replace]").forEach(function (link) {
      if (link.dataset.replaceBound === "1") return;
      link.dataset.replaceBound = "1";
      link.addEventListener("click", function (e) {
        var path = window.location.pathname || "";
        var fromPrivate =
          /^\/dashboard(\/|$)/.test(path) ||
          /^\/accounts\/(login|register)\/?$/.test(path);
        if (!fromPrivate) return;
        e.preventDefault();
        e.stopPropagation();
        window.location.replace(link.href);
      });
    });
  }

  bindHistoryReplaceLinks(document);

  document.body.addEventListener("htmx:afterSwap", function () {
    bindThemeToggle();
    syncCsrfInputs();
    bindHistoryReplaceLinks(document);
  });
  window.addEventListener("pageshow", syncCsrfInputs);

  // Reveal on scroll
  const reveals = document.querySelectorAll(".reveal");
  if (reveals.length && "IntersectionObserver" in window) {
    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting) {
            e.target.classList.add("visible");
            io.unobserve(e.target);
          }
        });
      },
      { threshold: 0.12 }
    );
    reveals.forEach((el) => io.observe(el));
  } else {
    reveals.forEach((el) => el.classList.add("visible"));
  }

  // Animated counters
  document.querySelectorAll("[data-counter]").forEach((el) => {
    const target = parseInt(el.getAttribute("data-counter"), 10) || 0;
    const duration = 1400;
    let start = null;
    const step = (ts) => {
      if (!start) start = ts;
      const p = Math.min((ts - start) / duration, 1);
      const eased = 1 - Math.pow(1 - p, 3);
      el.textContent = Math.floor(eased * target).toLocaleString();
      if (p < 1) requestAnimationFrame(step);
      else el.textContent = target.toLocaleString();
    };
    if ("IntersectionObserver" in window) {
      const cio = new IntersectionObserver(
        (entries) => {
          if (entries[0].isIntersecting) {
            requestAnimationFrame(step);
            cio.disconnect();
          }
        },
        { threshold: 0.4 }
      );
      cio.observe(el);
    } else {
      requestAnimationFrame(step);
    }
  });

  // Auto-dismiss legacy alerts (toasts handled by toasts.js)
  document.querySelectorAll(".alert-dismissible:not(.toast)").forEach((alert) => {
    setTimeout(() => {
      alert.classList.add("fade");
      setTimeout(() => alert.remove(), 400);
    }, 5000);
  });

  // Feedback slider — 4 cards visible; next/prev moves one page
  function bindFeedbackSliders(root) {
    (root || document).querySelectorAll("[data-feedback-slider]").forEach(function (slider) {
      if (slider.dataset.bound === "1") return;
      slider.dataset.bound = "1";
      var track = slider.querySelector("[data-slider-track]");
      if (!track) return;

      var section = slider.closest("#testimonials") || slider.parentElement;
      var prev = section ? section.querySelector("[data-slider-prev]") : null;
      var next = section ? section.querySelector("[data-slider-next]") : null;
      if (!prev) prev = slider.querySelector("[data-slider-prev]");
      if (!next) next = slider.querySelector("[data-slider-next]");

      function pageAmount() {
        // Scroll by full track width ≈ one row of 4 cards
        return Math.max(track.clientWidth - 8, 280);
      }

      function slideBy(dir) {
        track.scrollBy({ left: dir * pageAmount(), behavior: "smooth" });
      }

      if (prev) prev.addEventListener("click", function () { slideBy(-1); });
      if (next) next.addEventListener("click", function () { slideBy(1); });
    });
  }

  bindFeedbackSliders(document);
  document.body.addEventListener("htmx:afterSwap", function (evt) {
    bindFeedbackSliders(evt.detail && evt.detail.target ? evt.detail.target : document);
    bindLearnRail(evt.detail && evt.detail.target ? evt.detail.target : document);
  });

  // Category learn rail
  function bindLearnRail(root) {
    var scope = root || document;
    var rail = scope.querySelector ? scope.querySelector("[data-learn-rail]") : null;
    if (!rail && scope !== document) {
      rail = document.querySelector("[data-learn-rail]");
    }
    if (!rail || rail.dataset.bound === "1") return;
    rail.dataset.bound = "1";

    var section = rail.closest(".pm-learn") || document;
    var prev = section.querySelector("[data-learn-prev]");
    var next = section.querySelector("[data-learn-next]");

    function slide(dir) {
      var panel = rail.querySelector(".pm-learn__panel");
      var amount = panel ? panel.offsetWidth + 16 : 300;
      rail.scrollBy({ left: dir * amount, behavior: "smooth" });
    }

    if (prev) prev.addEventListener("click", function () { slide(-1); });
    if (next) next.addEventListener("click", function () { slide(1); });
  }

  bindLearnRail(document);

  function bindStarRating(scope) {
    var root = scope && scope.querySelectorAll ? scope : document;
    root.querySelectorAll(".pm-star-rating").forEach(function (group) {
      if (group.dataset.bound === "1") return;
      group.dataset.bound = "1";
      var options = Array.prototype.slice.call(group.querySelectorAll(".pm-star-rating__option"));

      function paint(upto) {
        options.forEach(function (opt, idx) {
          opt.classList.toggle("is-active", idx < upto);
          opt.classList.remove("is-preview");
        });
      }

      function selectedIndex() {
        var checked = group.querySelector("input:checked");
        if (!checked) return 0;
        var opt = checked.closest(".pm-star-rating__option");
        return opt ? options.indexOf(opt) + 1 : 0;
      }

      paint(selectedIndex());

      options.forEach(function (opt, idx) {
        opt.addEventListener("mouseenter", function () {
          paint(idx + 1);
        });
        opt.addEventListener("click", function () {
          var input = opt.querySelector("input");
          if (input) input.checked = true;
          paint(idx + 1);
        });
        var input = opt.querySelector("input");
        if (input) {
          input.addEventListener("change", function () {
            paint(selectedIndex());
          });
        }
      });

      group.addEventListener("mouseleave", function () {
        paint(selectedIndex());
      });
    });
  }

  bindStarRating(document);

  function bindProjectPlanGate(scope) {
    var root = scope && scope.querySelector ? scope : document;
    var form = root.querySelector("[data-project-idea-form]") || document.querySelector("[data-project-idea-form]");
    if (!form || form.dataset.planGateBound === "1") return;
    form.dataset.planGateBound = "1";

    var planInput = form.querySelector("[name='selected_plan']");
    var plansSection = document.getElementById("project-plans");
    var hint = document.querySelector("[data-plan-hint]");
    var selectedLabel = document.querySelector("[data-selected-plan-label]");
    var selectedName = document.querySelector("[data-selected-plan-name]");
    var hasPlans = !!plansSection;

    function hasPlan() {
      return !!(planInput && planInput.value);
    }

    function setLocked(locked) {
      if (!hasPlans) {
        form.classList.remove("is-locked");
        return;
      }
      form.classList.toggle("is-locked", locked);
    }

    function selectPlan(id, name) {
      if (!planInput) return;
      planInput.value = id;
      document.querySelectorAll("[data-plan-card]").forEach(function (card) {
        var on = String(card.getAttribute("data-plan-id")) === String(id);
        card.classList.toggle("is-selected", on);
        var btn = card.querySelector("[data-plan-select]");
        if (btn) btn.textContent = on ? "Selected" : "Select this plan";
      });
      if (selectedLabel && selectedName) {
        selectedName.textContent = name || "Selected plan";
        selectedLabel.hidden = false;
      }
      if (hint) hint.hidden = true;
      setLocked(false);
      if (window.PMToast) {
        window.PMToast.success("Plan selected. Now fill your details above.");
      }
      var formSection = document.getElementById("project-form");
      if (formSection) {
        window.setTimeout(function () {
          formSection.scrollIntoView({ behavior: "smooth", block: "start" });
          var nameField = form.querySelector("[name='name']");
          if (nameField) nameField.focus({ preventScroll: true });
        }, 180);
      }
    }

    function nudgeToPlans() {
      if (!plansSection) return;
      if (hint) hint.hidden = false;
      plansSection.classList.add("is-nudge");
      window.setTimeout(function () {
        plansSection.classList.remove("is-nudge");
      }, 800);
      plansSection.scrollIntoView({ behavior: "smooth", block: "start" });
      if (window.PMToast) {
        window.PMToast.warning("Select a plan first, then fill your info.");
      }
    }

    setLocked(!hasPlan());
    if (hasPlan()) {
      var currentId = planInput.value;
      var currentCard = document.querySelector('[data-plan-card][data-plan-id="' + currentId + '"]');
      var currentName = currentCard ? currentCard.getAttribute("data-plan-name") : "";
      document.querySelectorAll("[data-plan-card]").forEach(function (card) {
        var on = String(card.getAttribute("data-plan-id")) === String(currentId);
        card.classList.toggle("is-selected", on);
        var btn = card.querySelector("[data-plan-select]");
        if (btn) btn.textContent = on ? "Selected" : "Select this plan";
      });
      if (selectedLabel && selectedName && currentName) {
        selectedName.textContent = currentName;
        selectedLabel.hidden = false;
      }
    }

    document.querySelectorAll("[data-plan-select]").forEach(function (btn) {
      if (btn.dataset.bound === "1") return;
      btn.dataset.bound = "1";
      btn.addEventListener("click", function () {
        selectPlan(btn.getAttribute("data-plan-id"), btn.getAttribute("data-plan-name"));
      });
    });

    form.addEventListener(
      "focusin",
      function (e) {
        if (!hasPlans || hasPlan()) return;
        var target = e.target;
        if (!target || !target.matches("input, textarea, select, button")) return;
        e.preventDefault();
        if (target.blur) target.blur();
        nudgeToPlans();
      },
      true
    );

    form.addEventListener("click", function (e) {
      if (!hasPlans || hasPlan()) return;
      if (e.target.closest("[data-form-lock] a")) return;
      e.preventDefault();
      nudgeToPlans();
    });

    form.addEventListener("submit", function (e) {
      if (hasPlans && !hasPlan()) {
        e.preventDefault();
        nudgeToPlans();
      }
    });
  }

  bindProjectPlanGate(document);
  document.body.addEventListener("htmx:afterSwap", function (evt) {
    var target = evt.detail && evt.detail.target ? evt.detail.target : document;
    bindProjectPlanGate(target);
    bindStarRating(target);
  });

  // HTMX indicators + friendly CSRF / error toasts
  document.body.addEventListener("htmx:beforeRequest", () => {
    document.documentElement.classList.add("htmx-loading");
  });
  document.body.addEventListener("htmx:afterRequest", () => {
    document.documentElement.classList.remove("htmx-loading");
  });
  document.body.addEventListener("htmx:responseError", function (evt) {
    const status = evt.detail && evt.detail.xhr ? evt.detail.xhr.status : 0;
    if (window.PMToast) {
      if (status === 403) {
        window.PMToast.warning("Session expired. Please reload the page and try again.");
      } else if (status >= 500) {
        window.PMToast.error("Something went wrong. Please try again.");
      }
    }
  });
})();
