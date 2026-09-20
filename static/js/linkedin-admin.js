/* LinkedIn admin — full feature controls (ProjectMate) */
(function (window, document) {
  "use strict";

  function csrf() {
    var el = document.querySelector("[name=csrfmiddlewaretoken]");
    if (el) return el.value;
    var m = document.cookie.match(/csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[1]) : "";
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
    return fetch(path, options).then(function (res) {
      return res.json().then(function (data) {
        if (!res.ok) {
          var err = new Error((data && data.message) || "Request failed");
          err.payload = data;
          throw err;
        }
        return data;
      }).catch(function (e) {
        if (e.payload || e.message === "Request failed") throw e;
        if (!res.ok) throw new Error("Request failed (" + res.status + ")");
        throw e;
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

  function lines(value) {
    return String(value || "")
      .split(/\r?\n/)
      .map(function (s) { return s.trim(); })
      .filter(Boolean);
  }

  function runFormStorageKey(taskType) {
    return "linkedin_run_form_" + (taskType || "job");
  }

  function saveRunFormDraft(form, taskType) {
    if (!form || !window.sessionStorage) return;
    var draft = {};
    form.querySelectorAll("input, textarea, select").forEach(function (el) {
      if (!el.name || el.name === "csrfmiddlewaretoken") return;
      if (el.type === "checkbox") draft[el.name] = el.checked;
      else draft[el.name] = el.value;
    });
    try {
      sessionStorage.setItem(runFormStorageKey(taskType), JSON.stringify(draft));
    } catch (e) {}
  }

  function restoreRunFormDraft(form, taskType) {
    if (!form || !window.sessionStorage) return false;
    try {
      var raw = sessionStorage.getItem(runFormStorageKey(taskType));
      if (!raw) return false;
      var draft = JSON.parse(raw);
      var restored = false;
      Object.keys(draft).forEach(function (name) {
        var el = form.querySelector('[name="' + name + '"]');
        if (!el) return;
        if (el.type === "checkbox") el.checked = !!draft[name];
        else el.value = draft[name] != null ? String(draft[name]) : "";
        restored = true;
      });
      if (restored) {
        form.querySelectorAll('textarea[name="keywords"], textarea[name="locations"]').forEach(function (el) {
          el.dispatchEvent(new Event("input", { bubbles: true }));
        });
      }
      return restored;
    } catch (e) {
      return false;
    }
  }

  function bindRunFormDraft(form, taskType) {
    if (!form) return;
    var draftTimer = null;
    form.querySelectorAll("input, textarea, select").forEach(function (el) {
      if (!el.name || el.name === "csrfmiddlewaretoken") return;
      el.addEventListener("input", function () {
        clearTimeout(draftTimer);
        draftTimer = setTimeout(function () {
          saveRunFormDraft(form, taskType);
        }, 300);
      });
      el.addEventListener("change", function () {
        saveRunFormDraft(form, taskType);
      });
    });
  }

  function formConfig(form, taskType) {
    if (!form) return {};
    var fd = new FormData(form);
    if (taskType === "job") {
      var skip = [];
      if (window.PMScraperChecklist) {
        skip = PMScraperChecklist.getSkipSearches(document.getElementById("liChecklist"));
      }
      return {
        keywords: lines(fd.get("keywords")),
        locations: lines(fd.get("locations")),
        max_pages: parseInt(fd.get("max_pages") || "40", 10),
        max_jobs: parseInt(fd.get("max_jobs") || "0", 10),
        max_job_age_hours: parseInt(fd.get("max_job_age_hours") || "24", 10),
        resume: !!fd.get("resume"),
        skip_previous_jobs: !!fd.get("skip_previous_jobs"),
        headless: true,
        skip_searches: skip,
      };
    }
    if (taskType === "connection") {
      return {
        keywords: lines(fd.get("keywords")),
        locations: lines(fd.get("locations")),
        max_connections_per_run: parseInt(fd.get("max_connections_per_run") || "30", 10),
        max_pages: parseInt(fd.get("max_pages") || "200", 10),
        headless: true,
      };
    }
    if (taskType === "posts") {
      return {
        max_scroll_rounds: parseInt(fd.get("max_scroll_rounds") || "30", 10),
        max_posts_per_run: parseInt(fd.get("max_posts_per_run") || "0", 10),
        headless: true,
      };
    }
    return {};
  }

  function setText(id, text) {
    var el = document.getElementById(id);
    if (el) el.textContent = text == null ? "" : String(text);
  }

  function setLog(text) {
    var el = document.getElementById("liLiveLog");
    if (el) el.textContent = text || "";
  }

  function appendLog(line) {
    var el = document.getElementById("liLiveLog");
    if (!el) return;
    el.textContent += (el.textContent ? "\n" : "") + line;
    el.scrollTop = el.scrollHeight;
  }

  function toggleControls(status) {
    var start = document.getElementById("liStartTask") || document.getElementById("liStartSession");
    var stop = document.getElementById("liStopTask");
    var pause = document.getElementById("liPauseTask");
    var resume = document.getElementById("liResumeTask");
    var active = status === "pending" || status === "running" || status === "paused";
    if (start) start.disabled = active;
    if (stop) {
      stop.hidden = !active;
      stop.disabled = !active;
    }
    if (pause) pause.disabled = status !== "running";
    if (resume) resume.disabled = status !== "paused";
  }

  function updateProgress(data) {
    if (!data) return;
    setText("liKeyword", data.keyword || "—");
    setText("liLocation", data.location || "—");
    setText("liPage", data.page != null ? data.page : "—");
    var found = data.jobs_found || data.connections_sent || data.posts_checked || 0;
    setText("liFound", found);
    setText("liElapsed", data.elapsed || "00:00:00");
    var bar = document.getElementById("liProgressBar");
    if (bar) bar.style.width = (data.progress_pct || 0) + "%";
    var badge = document.getElementById("liStatusBadge");
    if (badge) badge.textContent = data.status || "Idle";
    setText("liTaskMeta", (data.task_type_label || data.task_type || "Task") + " — " + (data.status || "idle"));
    if (data.logs && data.logs.length) {
      setLog(data.logs.map(function (l) {
        return "[" + (l.time || "") + "] " + l.message;
      }).join("\n"));
    }
    var taskActive = data && (
      data.active ||
      data.status === "running" ||
      data.status === "paused" ||
      data.status === "pending"
    );
    renderChecklist(data.search_checklist, taskActive);
  }

  function renderChecklist(items, taskActive) {
    var panel = document.getElementById("liChecklistPanel");
    var list = document.getElementById("liChecklist");
    var count = document.getElementById("liChecklistCount");
    if (!window.PMScraperChecklist) return;
    var form = document.getElementById("liScraperForm");
    var local = PMScraperChecklist.buildFromForm(form);
    var checkState = PMScraperChecklist.getLocalCheckState(list);
    var merged = items && items.length
      ? PMScraperChecklist.mergeServerItems(local, items)
      : local;
    merged.forEach(function (item) {
      var key = item.id || PMScraperChecklist.searchKey(item.keyword, item.location);
      if (Object.prototype.hasOwnProperty.call(checkState, key)) {
        item.checked = checkState[key];
      }
    });
    var liveSkip = !!taskActive;
    PMScraperChecklist.render(list, count, panel, merged, {
      interactive: true,
      liveSkip: liveSkip,
      keepPanelVisible: true,
    });
  }

  function collectSettingsPayload(form) {
    var fd = new FormData(form);
    var tab = form.getAttribute("data-settings-tab") || "job";
    var payload = { tab: tab };
    fd.forEach(function (value, key) {
      if (key === "csrfmiddlewaretoken") return;
      if (payload[key] !== undefined) return;
      var el = form.querySelector('[name="' + key + '"]');
      if (el && el.type === "checkbox") payload[key] = el.checked;
      else payload[key] = value;
    });
    form.querySelectorAll('input[type="checkbox"]').forEach(function (el) {
      if (el.name) payload[el.name] = el.checked;
    });
    return payload;
  }

  function initBrandingButtons(base) {
    var section = document.getElementById("liBrandingSection");
    if (!section) return;
    var form = document.getElementById("liSettingsForm");
    var editPanel = document.getElementById("liBrandingEdit");
    var editLabel = document.getElementById("liBrandingEditLabel");
    var editPrimary = document.getElementById("liBrandingEditPrimary");
    var editUrl = document.getElementById("liBrandingEditUrl");
    var saveBtn = document.getElementById("liBrandingEditSave");
    var cancelBtn = document.getElementById("liBrandingEditCancel");
    var activeBtn = null;

    function fieldInput(name) {
      if (form) {
        var inForm = form.querySelector('[name="' + name + '"]');
        if (inForm) return inForm;
      }
      return document.querySelector('.li-branding-fields [name="' + name + '"]');
    }

    function truncate(val, max) {
      val = String(val || "").trim();
      if (!val) return "—";
      return val.length > max ? val.slice(0, max - 1) + "\u2026" : val;
    }

    function syncButtons() {
      section.querySelectorAll(".li-brand-btn").forEach(function (btn) {
        var field = btn.getAttribute("data-brand-field");
        var input = fieldInput(field);
        var valEl = btn.querySelector(".li-brand-btn__value");
        if (valEl) valEl.textContent = truncate(input && input.value, 36);
      });
    }

    function closeEdit() {
      if (editPanel) editPanel.classList.add("d-none");
      activeBtn = null;
      section.querySelectorAll(".li-brand-btn").forEach(function (b) {
        b.classList.remove("active");
      });
    }

    function persistBranding() {
      if (!form) {
        syncButtons();
        return Promise.resolve();
      }
      return api(base + "api/settings/", { method: "POST", json: collectSettingsPayload(form) })
        .then(function (data) {
          toast(data.message || "Branding saved (LinkedIn & Naukri)");
          syncButtons();
        })
        .catch(function (err) {
          toast(err.message || "Save failed", false);
        });
    }

    syncButtons();

    section.querySelectorAll(".li-brand-btn").forEach(function (btn) {
      btn.addEventListener("click", function () {
        if (activeBtn === btn) {
          closeEdit();
          return;
        }
        activeBtn = btn;
        section.querySelectorAll(".li-brand-btn").forEach(function (b) {
          b.classList.remove("active");
        });
        btn.classList.add("active");
        var field = btn.getAttribute("data-brand-field");
        var urlField = btn.getAttribute("data-brand-url-field");
        var label = btn.getAttribute("data-brand-label") || "Edit";
        if (editLabel) editLabel.textContent = label;
        var primaryInput = fieldInput(field);
        if (editPrimary) editPrimary.value = primaryInput ? primaryInput.value : "";
        if (editUrl) {
          if (urlField) {
            editUrl.classList.remove("d-none");
            var urlInput = fieldInput(urlField);
            editUrl.value = urlInput ? urlInput.value : "";
            editUrl.placeholder =
              urlField.indexOf("whatsapp") >= 0
                ? "https://chat.whatsapp.com/GV7XEmVREg9KrB1sr5dZwL"
                : "https://www.instagram.com/aniket.projectmate";
          } else {
            editUrl.classList.add("d-none");
            editUrl.value = "";
          }
        }
        if (editPanel) editPanel.classList.remove("d-none");
        if (editPrimary) editPrimary.focus();
      });
    });

    function applyEdit() {
      if (!activeBtn) return;
      var field = activeBtn.getAttribute("data-brand-field");
      var urlField = activeBtn.getAttribute("data-brand-url-field");
      var primaryInput = fieldInput(field);
      if (primaryInput && editPrimary) primaryInput.value = editPrimary.value.trim();
      if (urlField && editUrl) {
        var urlInput = fieldInput(urlField);
        if (urlInput) urlInput.value = editUrl.value.trim();
      }
      closeEdit();
      persistBranding();
    }

    if (saveBtn) saveBtn.addEventListener("click", applyEdit);
    if (cancelBtn) cancelBtn.addEventListener("click", closeEdit);
    if (editPrimary) {
      editPrimary.addEventListener("keydown", function (e) {
        if (e.key === "Enter") {
          e.preventDefault();
          applyEdit();
        } else if (e.key === "Escape") {
          closeEdit();
        }
      });
    }
    if (editUrl) {
      editUrl.addEventListener("keydown", function (e) {
        if (e.key === "Enter") {
          e.preventDefault();
          applyEdit();
        } else if (e.key === "Escape") {
          closeEdit();
        }
      });
    }
  }

  var LINKEDIN_JOB_RUN_SYNC_FIELDS = [
    { from: "job_keywords", to: "keywords" },
    { from: "job_locations", to: "locations" },
    { from: "job_max_pages", to: "max_pages" },
    { from: "job_max_jobs", to: "max_jobs" },
    { from: "job_max_age_hours", to: "max_job_age_hours" },
  ];

  function syncRunFormFromSettingsPanel(taskType) {
    var settingsForm = document.getElementById("liSettingsForm");
    var runForm = document.getElementById("liScraperForm");
    if (!window.PMScraperChecklist || !settingsForm || !runForm) return;
    var pairs = taskType === "job" ? LINKEDIN_JOB_RUN_SYNC_FIELDS : [];
    if (pairs.length) {
      PMScraperChecklist.syncRunFormFromSettings(settingsForm, runForm, pairs);
    }
  }

  function initSettings(base, taskType) {
    var toggle = document.getElementById("liSettingsToggle");
    var run = document.getElementById("liRunPanel");
    var panel = document.getElementById("liSettingsPanel");
    if (toggle && run && panel) {
      toggle.addEventListener("click", function () {
        var open = panel.classList.contains("d-none");
        panel.classList.toggle("d-none", !open);
        run.classList.toggle("d-none", open);
      });
    }
    var save = document.getElementById("liSaveSettings");
    var form = document.getElementById("liSettingsForm");
    if (save && form) {
      save.addEventListener("click", function () {
        api(base + "api/settings/", { method: "POST", json: collectSettingsPayload(form) })
          .then(function (data) {
            syncRunFormFromSettingsPanel(taskType);
            toast(data.message || "Settings saved — run form updated");
          })
          .catch(function (err) {
            toast(err.message || "Save failed", false);
          });
      });
    }
    initBrandingButtons(base);
  }

  function initPreview(base) {
    var showBtn = document.getElementById("liShowScraping");
    var hideBtn = document.getElementById("liHideScraping");
    var panel = document.getElementById("liBrowserPreview");
    var img = document.getElementById("liPreviewImg");
    var placeholder = document.getElementById("liPreviewPlaceholder");
    var timer = null;

    function stopFrames() {
      if (timer) {
        clearInterval(timer);
        timer = null;
      }
    }

    function pullFrame() {
      if (!img) return;
      img.src = base + "api/browser/screenshot/?t=" + Date.now();
      img.onload = function () {
        img.classList.remove("d-none");
        if (placeholder) placeholder.classList.add("d-none");
      };
    }

    function setEnabled(enabled) {
      return api(base + "api/browser/preview/", {
        method: "POST",
        json: { enabled: !!enabled },
      });
    }

    if (showBtn) {
      showBtn.addEventListener("click", function () {
        setEnabled(true)
          .then(function (data) {
            toast(data.message || "Preview opened");
            if (panel) panel.classList.remove("d-none");
            stopFrames();
            timer = setInterval(pullFrame, 1200);
            pullFrame();
          })
          .catch(function (err) {
            toast(err.message || "Preview failed", false);
          });
      });
    }
    if (hideBtn) {
      hideBtn.addEventListener("click", function () {
        stopFrames();
        setEnabled(false).catch(function () {});
        if (panel) panel.classList.add("d-none");
      });
    }
  }

  function initOutput(base) {
    var page = document.getElementById("liOutputPage");
    if (!page) return;

    function selectedPaths() {
      return Array.prototype.map.call(
        document.querySelectorAll("[data-merge-file]:checked"),
        function (el) { return el.getAttribute("data-merge-file"); }
      );
    }

    function updateMergeToolbar() {
      var paths = selectedPaths();
      var toolbar = document.getElementById("liMergeToolbar");
      if (toolbar) toolbar.classList.toggle("d-none", paths.length === 0);
      setText("liMergeCount", paths.length);
    }

    document.querySelectorAll("[data-merge-file]").forEach(function (el) {
      el.addEventListener("change", updateMergeToolbar);
    });
    var selectAll = document.getElementById("liMergeSelectAll");
    if (selectAll) {
      selectAll.addEventListener("change", function () {
        document.querySelectorAll("[data-merge-file]").forEach(function (el) {
          el.checked = selectAll.checked;
        });
        updateMergeToolbar();
      });
    }
    var clearBtn = document.getElementById("liMergeClear");
    if (clearBtn) {
      clearBtn.addEventListener("click", function () {
        document.querySelectorAll("[data-merge-file]").forEach(function (el) {
          el.checked = false;
        });
        if (selectAll) selectAll.checked = false;
        updateMergeToolbar();
      });
    }

    function deleteFile(path) {
      if (!path || !confirm("Move this file to trash?")) return;
      api(base + "api/files/delete/", { method: "POST", json: { path: path } })
        .then(function (data) {
          toast(data.message || "Moved to trash");
          window.location.reload();
        })
        .catch(function (err) {
          toast(err.message || "Delete failed", false);
        });
    }

    document.querySelectorAll("[data-delete-file]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        deleteFile(btn.getAttribute("data-delete-file"));
      });
    });

    document.querySelectorAll("[data-purge-file]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var id = btn.getAttribute("data-purge-file");
        var name = btn.getAttribute("data-name") || "file";
        if (!confirm("Permanently delete " + name + "?")) return;
        api(base + "api/files/trash/delete/", { method: "POST", json: { id: id } })
          .then(function (data) {
            toast(data.message || "Deleted");
            window.location.reload();
          })
          .catch(function (err) {
            toast(err.message || "Delete failed", false);
          });
      });
    });

    function updateTrashBulk() {
      var ids = Array.prototype.map.call(
        document.querySelectorAll("[data-trash-select]:checked"),
        function (el) { return el.getAttribute("data-trash-select"); }
      );
      var bar = document.getElementById("liTrashBulk");
      if (bar) bar.classList.toggle("d-none", ids.length === 0);
      return ids;
    }
    document.querySelectorAll("[data-trash-select]").forEach(function (el) {
      el.addEventListener("change", updateTrashBulk);
    });
    var bulk = document.getElementById("liTrashBulkDelete");
    if (bulk) {
      bulk.addEventListener("click", function () {
        var ids = updateTrashBulk();
        if (!ids.length || !confirm("Permanently delete " + ids.length + " file(s)?")) return;
        api(base + "api/files/trash/delete/", { method: "POST", json: { ids: ids } })
          .then(function (data) {
            toast(data.message || "Deleted");
            window.location.reload();
          })
          .catch(function (err) {
            toast(err.message || "Delete failed", false);
          });
      });
    }

    var previewBtn = document.getElementById("liMergePreview");
    var runBtn = document.getElementById("liMergeRun");
    if (previewBtn) {
      previewBtn.addEventListener("click", function () {
        var paths = selectedPaths();
        if (paths.length < 2) {
          toast("Select at least 2 files", false);
          return;
        }
        api(base + "api/files/merge/preview/", { method: "POST", json: { paths: paths } })
          .then(function (data) {
            var meta = document.getElementById("liMergePreviewMeta");
            if (meta) {
              meta.classList.remove("d-none");
              meta.textContent =
                "Merge preview: " +
                (data.preview && data.preview.total_rows != null
                  ? data.preview.total_rows
                  : (data.preview && data.preview.rows && data.preview.rows.length) || 0) +
                " rows · " +
                paths.length +
                " files";
            }
            toast("Merge preview ready");
          })
          .catch(function (err) {
            toast(err.message || "Preview failed", false);
          });
      });
    }
    if (runBtn) {
      runBtn.addEventListener("click", function () {
        var paths = selectedPaths();
        if (paths.length < 2) {
          toast("Select at least 2 files", false);
          return;
        }
        api(base + "api/files/merge/", {
          method: "POST",
          json: {
            paths: paths,
            dedupe: !!(document.getElementById("liMergeDedupe") || {}).checked,
            output_format: (document.getElementById("liMergeFormat") || {}).value || "xlsx",
          },
        })
          .then(function (data) {
            toast(data.message || "Merged");
            window.location.reload();
          })
          .catch(function (err) {
            toast(err.message || "Merge failed", false);
          });
      });
    }
  }

  function initLogs(base) {
    var form = document.getElementById("liLogsFilter");
    function refresh() {
      var q = (document.getElementById("liLogsQ") || {}).value || "";
      var sort = (document.getElementById("liLogsSort") || {}).value || "date";
      var order = (document.getElementById("liLogsOrder") || {}).value || "desc";
      var url =
        base +
        "api/logs/?q=" +
        encodeURIComponent(q) +
        "&sort=" +
        encodeURIComponent(sort) +
        "&order=" +
        encodeURIComponent(order);
      api(url)
        .then(function (data) {
          var logs = data.logs || [];
          setLog(
            logs
              .map(function (l) {
                var t = l.time || (l.created_at ? String(l.created_at).slice(11, 19) : "");
                return "[" + t + "] [" + (l.level || "info") + "] " + l.message;
              })
              .join("\n") || "No logs yet."
          );
        })
        .catch(function () {});
    }
    if (form) {
      form.addEventListener("submit", function (e) {
        e.preventDefault();
        refresh();
      });
    }
    window.setInterval(refresh, 4000);
  }

  function initDashboard(base) {
    function refresh() {
      api(base + "api/stats/")
        .then(function (data) {
          var s = data.stats || data;
          if (s.total_jobs != null) setText("liStatJobs", s.total_jobs);
          if (s.connections_sent != null) setText("liStatConnections", s.connections_sent);
          if (s.posts_scraped != null) setText("liStatPosts", s.posts_scraped);
          if (s.today_records != null) setText("liStatToday", s.today_records);
          if (data.task) updateProgress(data.task);
          else if (data.active_task) updateProgress(data.active_task);
        })
        .catch(function () {});
      api(base + "api/task/status/")
        .then(function (data) {
          if (data && data.id) {
            updateProgress(data);
            toggleControls(data.status);
          } else {
            toggleControls("");
          }
        })
        .catch(function () {});
    }
    refresh();
    window.setInterval(refresh, 3000);
  }

  function init(opts) {
    opts = opts || {};
    var taskType = opts.taskType;
    var features = opts.features || {};
    var base = (opts.apiBase || "/admin/linkedin/").replace(/\/?$/, "/");
    var pollTimer = null;
    var currentTaskId = null;

    initSettings(base, taskType);
    if (features.preview) initPreview(base);
    var runForm = document.getElementById("liScraperForm");
    if (runForm && taskType) {
      restoreRunFormDraft(runForm, taskType);
      bindRunFormDraft(runForm, taskType);
    }
    if (features.checklist && window.PMScraperChecklist) {
      PMScraperChecklist.bindForm(runForm, { keepPanelVisible: true });
      var checklistEl = document.getElementById("liChecklist");
      var skipPushTimer = null;
      if (checklistEl) {
        checklistEl.addEventListener("change", function (e) {
          if (!e.target.classList.contains("li-checklist-cb")) return;
          if (!currentTaskId) return;
          clearTimeout(skipPushTimer);
          skipPushTimer = setTimeout(function () {
            var skip = PMScraperChecklist.getSkipSearches(checklistEl);
            api(base + "api/task/skip-searches/", {
              method: "POST",
              json: { task_id: currentTaskId, skip_searches: skip },
            }).then(function (data) {
              if (data.search_checklist) renderChecklist(data.search_checklist, true);
            }).catch(function () {});
          }, 250);
        });
      }
    }
    if (features.output) initOutput(base);
    if (features.logs) initLogs(base);
    if (features.dashboard) initDashboard(base);
    if (features.settingsOnly) return;

    function poll() {
      var url = base + "api/task/status/" + (currentTaskId ? "?id=" + currentTaskId : "");
      api(url)
        .then(function (data) {
          if (!data || !data.id) {
            setText("liTaskMeta", "Idle");
            toggleControls("");
            return;
          }
          currentTaskId = data.id;
          updateProgress(data);
          toggleControls(data.status);
          if (data.active) {
            pollTimer = window.setTimeout(poll, 2000);
          }
        })
        .catch(function () {
          pollTimer = window.setTimeout(poll, 4000);
        });
    }

    function start() {
      var form = document.getElementById("liScraperForm");
      var config = formConfig(form, taskType);
      saveRunFormDraft(form, taskType);
      renderChecklist(null, false);
      setLog("Starting…");
      api(base + "api/task/start/", {
        method: "POST",
        json: { task_type: taskType, config: config },
      })
        .then(function (data) {
          currentTaskId = data.task_id;
          renderChecklist(null, true);
          toast(data.message || "Started");
          toggleControls("running");
          poll();
        })
        .catch(function (err) {
          toast(err.message || "Failed to start", false);
          appendLog("ERROR: " + (err.message || "Failed"));
        });
    }

    function control(action) {
      api(base + "api/task/control/", {
        method: "POST",
        json: { action: action, task_id: currentTaskId },
      })
        .then(function (data) {
          toast(data.message || action);
          if (data.status) updateProgress(data.status);
          poll();
        })
        .catch(function (err) {
          toast(err.message || "Control failed", false);
        });
    }

    var startBtn = document.getElementById("liStartTask") || document.getElementById("liStartSession");
    if (startBtn) startBtn.addEventListener("click", start);
    var stopBtn = document.getElementById("liStopTask");
    if (stopBtn) stopBtn.addEventListener("click", function () { control("stop"); });
    var pauseBtn = document.getElementById("liPauseTask");
    if (pauseBtn) pauseBtn.addEventListener("click", function () { control("pause"); });
    var resumeBtn = document.getElementById("liResumeTask");
    if (resumeBtn) resumeBtn.addEventListener("click", function () { control("resume"); });

    if (taskType || features.dashboard || features.logs) poll();
  }

  window.PMLinkedIn = { init: init };
})(window, document);
