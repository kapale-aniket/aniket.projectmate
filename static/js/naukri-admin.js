/* Naukri admin — apply flow + Show (visible browser) */
(function (window, document) {
  "use strict";

  function csrf() {
    var el = document.querySelector("[name=csrfmiddlewaretoken]");
    if (el) return el.value;
    var m = document.cookie.match(/csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[1]) : "";
  }

  function apiBase() {
    var root = document.querySelector("[data-api-base]");
    var base = root ? root.getAttribute("data-api-base") : "/admin/naukri/";
    if (!base.endsWith("/")) base += "/";
    return base;
  }

  function api(path, options) {
    options = options || {};
    options.headers = Object.assign(
      { "X-CSRFToken": csrf(), Accept: "application/json" },
      options.headers || {}
    );
    if (options.json) {
      options.headers["Content-Type"] = "application/json";
      options.body = JSON.stringify(options.json);
      delete options.json;
    }
    return fetch(apiBase() + path.replace(/^\//, ""), options).then(function (res) {
      return res.json().then(function (data) {
        if (!res.ok) {
          var err = new Error((data && data.message) || "Request failed");
          err.payload = data;
          throw err;
        }
        return data;
      });
    });
  }

  function toast(msg, ok) {
    if (window.PMToast) {
      if (ok === false) PMToast.error(msg);
      else PMToast.success(msg);
      return;
    }
    console.log(msg);
  }

  var state = { taskId: null, timer: null, previewTimer: null, running: false };

  function setBadge(status) {
    var el = document.getElementById("nkStatusBadge");
    if (!el) return;
    el.textContent = status || "Idle";
    el.className = "badge " + (
      status === "running" || status === "pending" ? "text-bg-primary" :
      status === "completed" ? "text-bg-success" :
      status === "failed" || status === "stopped" ? "text-bg-danger" :
      "text-bg-secondary"
    );
  }

  function renderLogs(logs) {
    var box = document.getElementById("nkLogs");
    if (!box) return;
    box.textContent = (logs || []).map(function (l) {
      var ts = (l.created_at || "").slice(11, 19);
      return "[" + ts + "] " + (l.message || "");
    }).join("\n");
    box.scrollTop = box.scrollHeight;
  }

  function formPayload(forceVisible) {
    var form = document.getElementById("nkApplyForm");
    var headless = !!(form && form.headless && form.headless.checked);
    if (forceVisible) {
      headless = false;
      if (form && form.headless) form.headless.checked = false;
    }
    return {
      task_type: "apply",
      job_keyword: (form && form.job_keyword && form.job_keyword.value) || "python",
      multi_apply_batch_size: Number((form && form.multi_apply_batch_size && form.multi_apply_batch_size.value) || 5),
      headless: headless,
    };
  }

  function showPreviewPanel(on) {
    var panel = document.getElementById("nkBrowserPreview");
    if (!panel) return;
    panel.classList.toggle("d-none", !on);
  }

  function stopPreviewFrames() {
    if (state.previewTimer) {
      clearInterval(state.previewTimer);
      state.previewTimer = null;
    }
  }

  function pullPreviewFrame() {
    var img = document.getElementById("nkPreviewImg");
    var placeholder = document.getElementById("nkPreviewPlaceholder");
    if (!img) return;
    img.src = apiBase() + "api/browser/screenshot/?t=" + Date.now();
    img.onload = function () {
      img.classList.remove("d-none");
      if (placeholder) placeholder.classList.add("d-none");
    };
  }

  function startPreviewFrames() {
    stopPreviewFrames();
    showPreviewPanel(true);
    pullPreviewFrame();
    state.previewTimer = setInterval(pullPreviewFrame, 1200);
  }

  function enablePreview(enabled) {
    return api("api/browser/preview/", {
      method: "POST",
      json: { enabled: !!enabled, task_id: state.taskId },
    });
  }

  function poll() {
    var q = state.taskId ? ("?id=" + encodeURIComponent(state.taskId)) : "";
    api("api/task/status/" + q).then(function (data) {
      var task = data.task;
      if (!task) {
        state.running = false;
        setBadge("Idle");
        document.getElementById("nkTaskMeta") && (document.getElementById("nkTaskMeta").textContent = "Ready");
        return;
      }
      state.taskId = task.id;
      state.running = task.status === "running" || task.status === "pending";
      setBadge(task.status);
      var meta = document.getElementById("nkTaskMeta");
      if (meta) {
        meta.textContent = task.task_type_label + " · " + task.status +
          (task.progress && task.progress.last_message ? " · " + task.progress.last_message : "");
      }
      renderLogs(data.logs || []);
      if (state.running) {
        state.timer = setTimeout(poll, 2000);
      } else {
        stopPreviewFrames();
      }
    }).catch(function () {
      state.timer = setTimeout(poll, 4000);
    });
  }

  function startApply(forceVisible) {
    var payload = formPayload(!!forceVisible);
    api("api/task/start/", { method: "POST", json: payload })
      .then(function (data) {
        toast(data.message || "Started");
        state.taskId = data.task && data.task.id;
        clearTimeout(state.timer);
        if (!payload.headless) {
          enablePreview(true).then(function () {
            startPreviewFrames();
          }).catch(function () {
            startPreviewFrames();
          });
        }
        poll();
      })
      .catch(function (err) {
        toast((err && err.message) || "Start failed", false);
      });
  }

  function showBrowser() {
    // Always open a visible Naukri Chromium window.
    if (state.running) {
      enablePreview(true)
        .then(function () {
          startPreviewFrames();
          toast("Live preview on. If the browser was headless, Stop then click Show again to open the window.");
        })
        .catch(function () {
          toast("Could not enable preview", false);
        });
      return;
    }
    startApply(true);
    toast("Opening Naukri browser window…");
  }

  function startSession() {
    api("api/task/start/", { method: "POST", json: { task_type: "session" } })
      .then(function (data) {
        toast(data.message || "Session started");
        state.taskId = data.task && data.task.id;
        clearTimeout(state.timer);
        poll();
      })
      .catch(function (err) {
        toast((err && err.message) || "Start failed", false);
      });
  }

  function stopTask() {
    stopPreviewFrames();
    enablePreview(false).catch(function () {});
    api("api/task/control/", {
      method: "POST",
      json: { action: "stop", task_id: state.taskId },
    })
      .then(function (data) {
        toast(data.message || "Stopped");
        clearTimeout(state.timer);
        poll();
      })
      .catch(function (err) {
        toast((err && err.message) || "Stop failed", false);
      });
  }

  function bind() {
    var startBtn = document.getElementById("nkStartTask");
    if (startBtn) startBtn.addEventListener("click", function () { startApply(false); });
    var stopBtn = document.getElementById("nkStopTask");
    if (stopBtn) stopBtn.addEventListener("click", stopTask);
    var showBtn = document.getElementById("nkShowScraping");
    if (showBtn) showBtn.addEventListener("click", showBrowser);
    var hideBtn = document.getElementById("nkHideScraping");
    if (hideBtn) {
      hideBtn.addEventListener("click", function () {
        stopPreviewFrames();
        showPreviewPanel(false);
        enablePreview(false).catch(function () {});
      });
    }
    poll();
  }

  window.PMNaukri = {
    startSession: startSession,
    startApply: startApply,
    showBrowser: showBrowser,
    stopTask: stopTask,
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bind);
  } else {
    bind();
  }
})(window, document);
