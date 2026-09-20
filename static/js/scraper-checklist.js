/* Shared keyword × location checklist for LinkedIn & Naukri job scrapers */
(function (window) {
  "use strict";

  function lines(value) {
    return String(value || "")
      .split(/\r?\n/)
      .map(function (s) { return s.trim(); })
      .filter(Boolean);
  }

  function searchKey(keyword, location) {
    return String(keyword || "").trim() + "|" + String(location || "").trim().toLowerCase();
  }

  function buildFromForm(form) {
    if (!form) return [];
    var fd = new FormData(form);
    var keywords = lines(fd.get("keywords"));
    var locations = lines(fd.get("locations"));
    if (!locations.length) locations = [""];
    var items = [];
    keywords.forEach(function (keyword) {
      locations.forEach(function (location) {
        var locLabel = location || "Anywhere";
        items.push({
          id: searchKey(keyword, location),
          keyword: keyword,
          location: location,
          label: locLabel + " \u2192 " + keyword,
          status: "pending",
          enabled: true,
          checked: true,
        });
      });
    });
    return items;
  }

  function getSkipSearches(listEl) {
    if (!listEl) return [];
    var skipped = [];
    listEl.querySelectorAll("[data-search-key]").forEach(function (row) {
      var cb = row.querySelector('input[type="checkbox"]');
      if (cb && !cb.checked) skipped.push(row.getAttribute("data-search-key"));
    });
    return skipped;
  }

  function getLocalCheckState(listEl) {
    var state = {};
    if (!listEl) return state;
    listEl.querySelectorAll(".li-checklist-item").forEach(function (row) {
      var key = row.getAttribute("data-search-key");
      var cb = row.querySelector('input[type="checkbox"]');
      if (key && cb) state[key] = cb.checked;
    });
    return state;
  }

  function render(listEl, countEl, panelEl, items, opts) {
    opts = opts || {};
    var interactive = opts.interactive !== false;
    var liveSkip = opts.liveSkip === true;
    if (panelEl && !opts.keepPanelVisible) {
      panelEl.classList.toggle("d-none", !items || !items.length);
    }
    if (countEl) {
      var activeCount = items ? items.filter(function (item) {
        return item.status !== "skipped";
      }).length : 0;
      countEl.textContent = items && items.length
        ? activeCount + " / " + items.length + " searches"
        : "0";
    }
    if (!listEl) return;
    if (!items || !items.length) {
      listEl.innerHTML = '<li class="small text-muted py-2">Enter keywords and locations to build the search queue.</li>';
      return;
    }
    listEl.innerHTML = items.map(function (item) {
      var status = item.status || "pending";
      var checked = item.checked !== false && status !== "skipped";
      if (status === "done") checked = true;
      var disabled = !interactive || status === "done" || status === "skipped";
      if (liveSkip && (status === "pending" || status === "active" || status === "paused")) {
        disabled = false;
      }
      var badge = "";
      if (status === "active") badge = ' <span class="badge text-bg-primary">In progress</span>';
      if (status === "paused") badge = ' <span class="badge text-bg-warning">Paused</span>';
      if (status === "done") badge = ' <span class="badge text-bg-success">Done</span>';
      if (status === "skipped") badge = ' <span class="badge text-bg-secondary">Skipped</span>';
      var key = item.id || searchKey(item.keyword, item.location);
      return (
        '<li class="li-checklist-item li-checklist-' + status + '" data-search-key="' + key + '">' +
        '<label class="li-checklist-label mb-0">' +
        '<input type="checkbox" class="form-check-input me-1 li-checklist-cb" ' +
        (checked ? "checked " : "") +
        (disabled ? "disabled " : "") +
        'data-search-key="' + key + '">' +
        "<span>" + (item.label || key) + "</span>" + badge +
        "</label></li>"
      );
    }).join("");
  }

  function mergeServerItems(localItems, serverItems) {
    if (!serverItems || !serverItems.length) return localItems;
    var byKey = {};
    localItems.forEach(function (item) {
      byKey[item.id || searchKey(item.keyword, item.location)] = Object.assign({}, item);
    });
    serverItems.forEach(function (item) {
      var key = item.id || searchKey(item.keyword, item.location);
      var prev = byKey[key] || {};
      byKey[key] = Object.assign({}, prev, item, {
        id: key,
        checked: item.status === "skipped" ? false : prev.checked !== false,
      });
    });
    return Object.keys(byKey).map(function (k) { return byKey[k]; });
  }

  function bindForm(form, opts) {
    opts = opts || {};
    var panel = document.getElementById(opts.panelId || "liChecklistPanel");
    var list = document.getElementById(opts.listId || "liChecklist");
    var count = document.getElementById(opts.countId || "liChecklistCount");
    if (!form || !list) return;

    function refresh(interactive) {
      render(list, count, panel, buildFromForm(form), {
        interactive: interactive !== false,
        keepPanelVisible: !!opts.keepPanelVisible,
      });
    }

    refresh(true);
    form.querySelectorAll('textarea[name="keywords"], textarea[name="locations"]').forEach(function (el) {
      el.addEventListener("input", function () { refresh(true); });
    });
    return { refresh: refresh, getSkipSearches: function () { return getSkipSearches(list); } };
  }

  /** Copy saved settings fields onto the run/start form (same labels & values). */
  function syncRunFormFromSettings(settingsForm, runForm, pairs) {
    if (!settingsForm || !runForm || !pairs || !pairs.length) return;
    pairs.forEach(function (pair) {
      var from = settingsForm.querySelector('[name="' + pair.from + '"]');
      var to = runForm.querySelector('[name="' + pair.to + '"]');
      if (!from || !to) return;
      if (to.type === "checkbox") to.checked = !!from.checked;
      else to.value = from.value;
    });
    runForm.querySelectorAll('textarea[name="keywords"], textarea[name="locations"]').forEach(function (el) {
      el.dispatchEvent(new Event("input", { bubbles: true }));
    });
  }

  window.PMScraperChecklist = {
    lines: lines,
    searchKey: searchKey,
    buildFromForm: buildFromForm,
    getSkipSearches: getSkipSearches,
    getLocalCheckState: getLocalCheckState,
    render: render,
    mergeServerItems: mergeServerItems,
    bindForm: bindForm,
    syncRunFormFromSettings: syncRunFormFromSettings,
  };
})(window);
