/* ProjectMateBot - knowledge-base chat helper */
(function (window, document) {
  "use strict";

  var STORAGE_KEY = "pm_chatbot_v3";
  var HISTORY_LIMIT = 16;

  var TOPICS = [
    { id: "start", label: "Popular", icon: "fa-star" },
    { id: "account", label: "Account", icon: "fa-user" },
    { id: "classes", label: "Classes", icon: "fa-chalkboard" },
    { id: "courses", label: "Courses", icon: "fa-graduation-cap" },
    { id: "dashboard", label: "Dashboard", icon: "fa-gauge" },
    { id: "rewards", label: "Rewards", icon: "fa-trophy" },
    { id: "referrals", label: "Referrals", icon: "fa-user-plus" },
    { id: "projects", label: "Projects", icon: "fa-lightbulb" },
    { id: "contact", label: "Contact", icon: "fa-headset" },
  ];

  var SUGGESTIONS = {
    start: [
      "What is ProjectMate?",
      "How can you help me?",
    ],
    account: [
      "How do I create an account?",
      "How do I log in?",
      "I forgot my password",
    ],
    classes: [
      "How do I join a free class?",
      "Where are meet links?",
      "Do I need to register for classes?",
    ],
    courses: [
      "How do paid courses work?",
      "How do I enroll in a course?",
      "Where can I see course prices?",
    ],
    dashboard: [
      "What is in the student dashboard?",
      "How do I check attendance?",
      "Where do I upload my resume?",
    ],
    rewards: [
      "How do rewards and points work?",
      "Where can I see my reward points?",
    ],
    referrals: [
      "How do referrals work?",
      "Where is my referral link?",
    ],
    projects: [
      "How can ProjectMate help with projects?",
      "Where do I submit a project request?",
    ],
    contact: [
      "How can I contact support?",
      "Is WhatsApp available?",
      "Where is the contact form?",
    ],
  };

  function csrfToken() {
    var match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    if (match) return decodeURIComponent(match[1]);
    var input = document.querySelector("[name=csrfmiddlewaretoken]");
    return input ? input.value : "";
  }

  function escapeHtml(str) {
    return String(str || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  /** Format replies: **bold**, lists, and [[Click Label|/path/]] as real buttons */
  function formatReply(text) {
    var raw = String(text || "");
    var lines = raw.split(/\n/);
    var html = [];
    var inList = false;
    var btnRow = [];

    var PATH_LABELS = {
      "/": "Go to Home",
      "/accounts/register/": "Click Register",
      "/accounts/login/": "Click Login",
      "/accounts/logout/": "Click Logout",
      "/accounts/password-reset/": "Reset Password",
      "/accounts/trust/": "Why Login",
      "/dashboard/": "Open Dashboard",
      "/dashboard/profile/": "Open Profile",
      "/dashboard/classes/": "My Classes",
      "/dashboard/attendance/": "My Attendance",
      "/dashboard/rewards/": "Open Rewards",
      "/dashboard/referrals/": "Open Referrals",
      "/dashboard/resume/": "Upload Resume",
      "/dashboard/notifications/": "Open Notifications",
      "/dashboard/project-requests/": "My Project Requests",
      "/dashboard/feedbacks/": "My Feedbacks",
      "/classes/": "Browse Free Classes",
      "/courses/": "Browse Courses",
      "/project/": "View Projects",
      "/feedback/": "Submit Feedback",
      "/feedback/testimonials/": "View Testimonials",
      "/announcements/": "Open Announcements",
      "/contact/": "Open Contact",
      "/about/": "About Us",
      "/search/": "Open Search",
    };

    function closeList() {
      if (inList) {
        html.push("</ul>");
        inList = false;
      }
    }

    function flushButtons() {
      if (!btnRow.length) return;
      html.push('<div class="pm-chat__actions">' + btnRow.join("") + "</div>");
      btnRow = [];
    }

    function makeBtn(label, url) {
      var href = escapeHtml(url);
      var text = escapeHtml(label);
      return (
        '<a class="pm-chat__btn" href="' +
        href +
        '"><i class="fas fa-arrow-right" aria-hidden="true"></i> ' +
        text +
        "</a>"
      );
    }

    function labelForPath(path) {
      if (PATH_LABELS[path]) return PATH_LABELS[path];
      // soft match without trailing slash
      var withSlash = path.endsWith("/") ? path : path + "/";
      if (PATH_LABELS[withSlash]) return PATH_LABELS[withSlash];
      return "Open page";
    }

    function extractCtas(s) {
      var found = [];
      var rest = String(s);
      // [[Label|/path/]]
      rest = rest.replace(/\[\[([^|\]]+)\|([^\]]+)\]\]/g, function (_, label, url) {
        found.push({ label: label.trim(), url: url.trim() });
        return " ";
      });
      // [Label](/path/)
      rest = rest.replace(/\[([^\]]+)\]\(([^)]+)\)/g, function (_, label, url) {
        found.push({ label: label.trim(), url: url.trim() });
        return " ";
      });
      // Bare paths like /accounts/register/ or `/accounts/register/`
      rest = rest.replace(/`(\/[a-z0-9_\-\/?=&%]+\/?)`/gi, function (_, path) {
        found.push({ label: labelForPath(path), url: path });
        return " ";
      });
      rest = rest.replace(/(^|[\s(])(\/[a-z0-9_\-\/?=&%]+\/?)(?=[\s).,]|$)/gi, function (_, pre, path) {
        found.push({ label: labelForPath(path), url: path });
        return pre + " ";
      });
      return { text: rest.replace(/\s+/g, " ").trim(), ctas: found };
    }

    function inlineFmt(s) {
      var parsed = extractCtas(s);
      var out = escapeHtml(parsed.text);
      out = out.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
      if (parsed.ctas.length) {
        out +=
          (out ? " " : "") +
          parsed.ctas
            .map(function (c) {
              return makeBtn(c.label, c.url);
            })
            .join(" ");
      }
      return out;
    }

    function lineIsOnlyButtons(trimmed) {
      var t = trimmed.replace(/\s+/g, " ").trim();
      if (!t) return false;
      // remove all CTA / path tokens; if nothing left, line is buttons-only
      var left = t
        .replace(/\[\[([^|\]]+)\|([^\]]+)\]\]/g, "")
        .replace(/\[([^\]]+)\]\(([^)]+)\)/g, "")
        .replace(/`(\/[a-z0-9_\-\/?=&%]+\/?)`/gi, "")
        .replace(/(^|[\s(])(\/[a-z0-9_\-\/?=&%]+\/?)(?=[\s).,]|$)/gi, " ")
        .replace(/\s+/g, "")
        .trim();
      return left === "" && /[\[\/]/.test(t);
    }

    lines.forEach(function (line) {
      var trimmed = line.trim();
      if (!trimmed) {
        closeList();
        return;
      }

      if (lineIsOnlyButtons(trimmed)) {
        closeList();
        var only = extractCtas(trimmed);
        only.ctas.forEach(function (c) {
          btnRow.push(makeBtn(c.label, c.url));
        });
        return;
      }

      var bullet = trimmed.match(/^([•\-\*]|\d+\.)\s+(.*)$/);
      if (bullet) {
        flushButtons();
        if (!inList) {
          html.push('<ul class="pm-chat__list">');
          inList = true;
        }
        html.push("<li>" + inlineFmt(bullet[2]) + "</li>");
        return;
      }
      closeList();
      flushButtons();
      if (/^\*(.+)\*$/.test(trimmed) && trimmed.indexOf("**") === -1) {
        html.push(
          '<p class="pm-chat__muted">' +
            inlineFmt(trimmed.replace(/^\*|\*$/g, "")) +
            "</p>"
        );
        return;
      }
      html.push("<p>" + inlineFmt(trimmed) + "</p>");
    });
    closeList();
    flushButtons();
    return html.join("") || "<p>" + escapeHtml(raw) + "</p>";
  }

  function loadState() {
    try {
      var raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return { history: [], topic: "start" };
      var data = JSON.parse(raw);
      return {
        history: Array.isArray(data.history) ? data.history.slice(-HISTORY_LIMIT) : [],
        topic: data.topic || "start",
      };
    } catch (e) {
      return { history: [], topic: "start" };
    }
  }

  function saveState(state) {
    try {
      localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({
          history: (state.history || []).slice(-HISTORY_LIMIT),
          topic: state.topic || "start",
        })
      );
    } catch (e) {}
  }

  function init() {
    var root = document.getElementById("pmChatbot");
    if (!root || root.dataset.bound === "1") return;
    root.dataset.bound = "1";

    var askUrl = root.getAttribute("data-ask-url") || "/chatbot/ask/";
    var panel = document.getElementById("pmChatPanel");
    var launcher = document.getElementById("pmChatLauncher");
    var closeBtn = document.getElementById("pmChatClose");
    var messagesEl = document.getElementById("pmChatMessages");
    var typingEl = document.getElementById("pmChatTyping");
    var topicsEl = document.getElementById("pmChatTopics");
    var topicsWrap = document.getElementById("pmChatTopicsWrap");
    var topicsPrev = document.getElementById("pmChatTopicsPrev");
    var topicsNext = document.getElementById("pmChatTopicsNext");
    var chipsEl = document.getElementById("pmChatChips");
    var form = document.getElementById("pmChatForm");
    var input = document.getElementById("pmChatInput");
    var sendBtn = document.getElementById("pmChatSend");
    var statusLabel = document.getElementById("pmChatStatusLabel");

    if (!panel || !launcher || !messagesEl || !input) return;

    var state = loadState();
    var busy = false;

    function setOpen(open) {
      root.classList.toggle("is-open", open);
      panel.setAttribute("aria-hidden", open ? "false" : "true");
      launcher.setAttribute("aria-expanded", open ? "true" : "false");
      if (open) {
        if (root.dataset.welcomed !== "1") {
          root.dataset.welcomed = "1";
          ensureWelcome();
        }
        setTimeout(function () {
          input.focus();
          updateTopicsNav();
        }, 180);
      }
    }

    function scrollBottom() {
      messagesEl.scrollTop = messagesEl.scrollHeight;
    }

    function setTyping(on) {
      if (!typingEl) return;
      typingEl.setAttribute("aria-hidden", on ? "false" : "true");
      typingEl.classList.toggle("is-visible", !!on);
      if (on) {
        messagesEl.appendChild(typingEl);
        scrollBottom();
      }
    }

    function appendBubble(role, text, opts) {
      opts = opts || {};
      var row = document.createElement("div");
      row.className = "pm-chat__row pm-chat__row--" + role;
      var bubble = document.createElement("div");
      bubble.className = "pm-chat__bubble pm-chat__bubble--" + role;
      if (role === "bot") {
        bubble.innerHTML = formatReply(text);
      } else {
        bubble.textContent = text;
      }
      if (opts.mode === "ai") {
        bubble.classList.add("pm-chat__bubble--ai");
      }
      row.appendChild(bubble);
      if (typingEl && typingEl.parentNode === messagesEl) {
        messagesEl.insertBefore(row, typingEl);
      } else {
        messagesEl.appendChild(row);
      }
      scrollBottom();
      return bubble;
    }

    function clearChatVisual() {
      Array.prototype.slice.call(messagesEl.children).forEach(function (node) {
        if (node !== typingEl) node.remove();
      });
    }

    function ensureWelcome() {
      var hasUser = state.history.some(function (m) {
        return m.role === "user";
      });
      if (hasUser) {
        clearChatVisual();
        state.history.forEach(function (m) {
          appendBubble(m.role === "user" ? "user" : "bot", m.content);
        });
        return;
      }
      if (messagesEl.querySelector(".pm-chat__bubble--bot")) return;
      appendBubble(
        "bot",
        "Hi! I'm **ProjectMateBot** - your ProjectMate help guide.\n\n" +
          "I answer from our **project knowledge base** only (accounts, classes, courses, dashboard, rewards, and more).\n\n" +
          "If I don't understand, I'll ask you to **check spelling** and ask a related ProjectMate question - I won't give random answers.\n\n" +
          "Try a topic below or type your question."
      );
    }

    function updateTopicsNav() {
      if (!topicsEl || !topicsWrap) return;
      var maxScroll = Math.max(0, topicsEl.scrollWidth - topicsEl.clientWidth);
      var hasOverflow = maxScroll > 6;
      var atStart = topicsEl.scrollLeft <= 6;
      var atEnd = topicsEl.scrollLeft >= maxScroll - 6;

      // Back arrow: only after user scrolls forward (not at start)
      var showPrev = hasOverflow && !atStart;
      // Next arrow: only when more tabs exist to the right
      var showNext = hasOverflow && !atEnd;

      if (topicsPrev) {
        topicsPrev.hidden = false;
        topicsPrev.classList.toggle("is-hidden", !showPrev);
        topicsPrev.setAttribute("aria-hidden", showPrev ? "false" : "true");
        topicsPrev.tabIndex = showPrev ? 0 : -1;
      }
      if (topicsNext) {
        topicsNext.hidden = false;
        topicsNext.classList.toggle("is-hidden", !showNext);
        topicsNext.setAttribute("aria-hidden", showNext ? "false" : "true");
        topicsNext.tabIndex = showNext ? 0 : -1;
      }

      topicsWrap.classList.toggle("is-at-start", atStart || !hasOverflow);
      topicsWrap.classList.toggle("is-at-end", atEnd || !hasOverflow);
      topicsWrap.classList.toggle("has-overflow", hasOverflow);
    }

    function scrollTopics(dir) {
      if (!topicsEl) return;
      var amount = Math.max(140, Math.floor(topicsEl.clientWidth * 0.7));
      topicsEl.scrollBy({ left: dir * amount, behavior: "smooth" });
      // Update during and after smooth scroll so Back appears right away
      requestAnimationFrame(updateTopicsNav);
      setTimeout(updateTopicsNav, 120);
      setTimeout(updateTopicsNav, 320);
    }

    function renderTopics() {
      if (!topicsEl) return;
      topicsEl.innerHTML = "";
      TOPICS.forEach(function (t) {
        var btn = document.createElement("button");
        btn.type = "button";
        btn.className =
          "pm-chat__topic" + (state.topic === t.id ? " is-active" : "");
        btn.innerHTML =
          '<i class="fas ' + t.icon + '" aria-hidden="true"></i> ' + t.label;
        btn.addEventListener("click", function () {
          state.topic = t.id;
          saveState(state);
          renderTopics();
          renderChips(true);
        });
        topicsEl.appendChild(btn);
      });
      requestAnimationFrame(function () {
        updateTopicsNav();
        // Keep active topic visible
        var active = topicsEl.querySelector(".pm-chat__topic.is-active");
        if (active && active.scrollIntoView) {
          active.scrollIntoView({ inline: "nearest", block: "nearest", behavior: "smooth" });
          setTimeout(updateTopicsNav, 240);
        }
      });
    }

    function renderChips(highlight) {
      if (!chipsEl) return;
      chipsEl.innerHTML = "";
      chipsEl.classList.remove("is-highlight");
      var list = SUGGESTIONS[state.topic] || SUGGESTIONS.start;
      list.forEach(function (q, index) {
        var btn = document.createElement("button");
        btn.type = "button";
        btn.className = "pm-chat__chip" + (highlight ? " pm-chat__chip--flash" : "");
        if (highlight) {
          btn.style.animationDelay = index * 0.07 + "s";
        }
        btn.textContent = q;
        btn.addEventListener("click", function () {
          input.value = q;
          sendMessage(q);
        });
        chipsEl.appendChild(btn);
      });
      if (highlight) {
        chipsEl.classList.add("is-highlight");
        // Clear flash classes after animation so they can re-trigger next tab click
        setTimeout(function () {
          chipsEl.classList.remove("is-highlight");
          Array.prototype.forEach.call(
            chipsEl.querySelectorAll(".pm-chat__chip--flash"),
            function (el) {
              el.classList.remove("pm-chat__chip--flash");
              el.style.animationDelay = "";
            }
          );
        }, 1200);
      }
    }

    function apiHistory() {
      return state.history
        .filter(function (m) {
          return m.role === "user" || m.role === "assistant";
        })
        .slice(-HISTORY_LIMIT)
        .map(function (m) {
          return { role: m.role, content: m.content };
        });
    }

    function sendMessage(text) {
      var msg = String(text || "").trim();
      if (!msg || busy) return;
      busy = true;
      if (sendBtn) sendBtn.disabled = true;
      input.value = "";

      appendBubble("user", msg);
      state.history.push({ role: "user", content: msg });
      saveState(state);
      setTyping(true);
      if (statusLabel) statusLabel.textContent = "Thinking…";

      var payload = {
        message: msg,
        history: apiHistory().slice(0, -1),
      };

      fetch(askUrl, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
          "X-CSRFToken": csrfToken(),
        },
        body: JSON.stringify(payload),
      })
        .then(function (res) {
          return res.json().then(function (data) {
            return { ok: res.ok, data: data };
          });
        })
        .then(function (result) {
          var reply =
            (result.data && result.data.reply) ||
            "Sorry - I couldn't answer that just now. Please try again or use Contact / WhatsApp.";
          appendBubble("bot", reply, {
            mode: result.data && result.data.mode,
          });
          state.history.push({ role: "assistant", content: reply });
          saveState(state);
          if (statusLabel) {
            statusLabel.textContent = "Any doubts? I will guide you";
          }
        })
        .catch(function () {
          appendBubble(
            "bot",
            "I couldn't reach the chat service. Check your connection and try again.\n\nYou can also use **/contact/** or the WhatsApp icon for human help."
          );
          if (statusLabel) statusLabel.textContent = "Offline · try again";
        })
        .finally(function () {
          setTyping(false);
          busy = false;
          if (sendBtn) sendBtn.disabled = false;
          if (statusLabel && statusLabel.textContent === "Thinking…") {
            statusLabel.textContent = "Any doubts? I will guide you";
          }
          input.focus();
        });
    }

    launcher.addEventListener("click", function () {
      setOpen(!root.classList.contains("is-open"));
    });
    if (closeBtn) {
      closeBtn.addEventListener("click", function () {
        setOpen(false);
      });
    }
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && root.classList.contains("is-open")) {
        setOpen(false);
      }
    });

    if (form) {
      form.addEventListener("submit", function (e) {
        e.preventDefault();
        e.stopPropagation();
        sendMessage(input.value);
      });
    }
    if (sendBtn) {
      sendBtn.addEventListener("click", function (e) {
        e.preventDefault();
        sendMessage(input.value);
      });
    }
    input.addEventListener("keydown", function (e) {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendMessage(input.value);
      }
    });

    if (topicsPrev) {
      topicsPrev.addEventListener("click", function () {
        scrollTopics(-1);
      });
    }
    if (topicsNext) {
      topicsNext.addEventListener("click", function () {
        scrollTopics(1);
      });
    }
    if (topicsEl) {
      topicsEl.addEventListener("scroll", function () {
        updateTopicsNav();
      }, { passive: true });
      window.addEventListener("resize", function () {
        updateTopicsNav();
      });
    }

    renderTopics();
    renderChips();
    setTimeout(function () {
      launcher.classList.add("pm-chat__launcher--pulse");
      updateTopicsNav();
    }, 1200);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})(window, document);
