(function () {
  "use strict";

  var DEFAULTS = {
    job: null,
    connection: null,
    posts: null,
  };

  function parseJson(text, fallback) {
    try {
      return JSON.parse(text || "");
    } catch (e) {
      return fallback;
    }
  }

  function hiddenInput(section) {
    var type = section.getAttribute("data-excel-format-section");
    return document.querySelector('[name="' + type + '_excel_format"]');
  }

  function readFormat(section) {
    var input = hiddenInput(section);
    var type = section.getAttribute("data-excel-format-section");
    var fallback = DEFAULTS[type] || { columns: [], style: {}, layout: {} };
    return parseJson(input && input.value, fallback);
  }

  function writeFormat(section, fmt) {
    var input = hiddenInput(section);
    if (input) input.value = JSON.stringify(fmt);
  }

  function colorValue(raw) {
    if (!raw) return "";
    var text = String(raw).trim();
    if (text.startsWith("#")) return text.slice(1).toUpperCase();
    return text.toUpperCase();
  }

  function bindMetaFields(editor, section, fmt) {
    editor.querySelectorAll("[data-excel-field]").forEach(function (el) {
      var key = el.getAttribute("data-excel-field");
      el.value = fmt[key] || "";
      el.addEventListener("input", function () {
        var current = readFormat(section);
        current[key] = el.value;
        writeFormat(section, current);
      });
    });

    editor.querySelectorAll("[data-excel-style]").forEach(function (el) {
      var key = el.getAttribute("data-excel-style");
      fmt.style = fmt.style || {};
      el.value = fmt.style[key] ? "#" + colorValue(fmt.style[key]) : "";
      el.addEventListener("input", function () {
        var current = readFormat(section);
        current.style = current.style || {};
        current.style[key] = colorValue(el.value);
        writeFormat(section, current);
      });
    });

    editor.querySelectorAll("[data-excel-layout]").forEach(function (el) {
      var key = el.getAttribute("data-excel-layout");
      fmt.layout = fmt.layout || {};
      el.checked = fmt.layout[key] !== false;
      el.addEventListener("change", function () {
        var current = readFormat(section);
        current.layout = current.layout || {};
        current.layout[key] = el.checked;
        writeFormat(section, current);
      });
    });

    editor.querySelectorAll("[data-excel-layout-text]").forEach(function (el) {
      var key = el.getAttribute("data-excel-layout-text");
      fmt.layout = fmt.layout || {};
      el.value = fmt.layout[key] || "";
      el.addEventListener("input", function () {
        var current = readFormat(section);
        current.layout = current.layout || {};
        current.layout[key] = el.value;
        writeFormat(section, current);
      });
    });
  }

  function renderColumns(section, editor, fmt) {
    var list = editor.querySelector("[data-excel-columns-list]");
    if (!list) return;
    list.innerHTML = "";

    (fmt.columns || []).forEach(function (col, index) {
      var row = document.createElement("div");
      row.className = "pm-excel-column-row";
      row.innerHTML =
        '<label class="pm-excel-col-visible">' +
        '<input type="checkbox" data-col-visible ' +
        (col.visible !== false ? "checked" : "") +
        ' aria-label="Show column">' +
        "</label>" +
        '<input type="text" class="pm-settings-input pm-excel-col-header" data-col-header value="' +
        escapeAttr(col.header || "") +
        '" maxlength="80">' +
        '<input type="number" class="pm-settings-input pm-excel-col-width" data-col-width min="5" max="80" value="' +
        (col.width || 14) +
        '">' +
        '<span class="pm-excel-col-key" title="Field key">' +
        escapeHtml(col.key) +
        "</span>" +
        '<div class="pm-excel-col-actions">' +
        '<button type="button" class="pm-excel-col-btn" data-col-up aria-label="Move up">↑</button>' +
        '<button type="button" class="pm-excel-col-btn" data-col-down aria-label="Move down">↓</button>' +
        "</div>";

      row.querySelector("[data-col-visible]").addEventListener("change", function (e) {
        updateColumn(section, index, { visible: e.target.checked });
        renderColumns(section, editor, readFormat(section));
      });
      row.querySelector("[data-col-header]").addEventListener("input", function (e) {
        updateColumn(section, index, { header: e.target.value });
      });
      row.querySelector("[data-col-width]").addEventListener("input", function (e) {
        updateColumn(section, index, { width: parseInt(e.target.value, 10) || 14 });
      });
      row.querySelector("[data-col-up]").addEventListener("click", function () {
        moveColumn(section, index, -1);
        renderColumns(section, editor, readFormat(section));
      });
      row.querySelector("[data-col-down]").addEventListener("click", function () {
        moveColumn(section, index, 1);
        renderColumns(section, editor, readFormat(section));
      });

      list.appendChild(row);
    });
  }

  function updateColumn(section, index, patch) {
    var fmt = readFormat(section);
    if (!fmt.columns || !fmt.columns[index]) return;
    Object.assign(fmt.columns[index], patch);
    writeFormat(section, fmt);
  }

  function moveColumn(section, index, delta) {
    var fmt = readFormat(section);
    var cols = fmt.columns || [];
    var next = index + delta;
    if (next < 0 || next >= cols.length) return;
    var tmp = cols[index];
    cols[index] = cols[next];
    cols[next] = tmp;
    writeFormat(section, fmt);
  }

  function escapeHtml(text) {
    return String(text)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  function escapeAttr(text) {
    return escapeHtml(text).replace(/"/g, "&quot;");
  }

  function initSection(section) {
    var editor = section.querySelector(".pm-excel-format-editor");
    if (!editor) return;
    var fmt = readFormat(section);
    bindMetaFields(editor, section, fmt);
    renderColumns(section, editor, fmt);

    var resetBtn = editor.querySelector("[data-excel-reset-columns]");
    if (resetBtn) {
      resetBtn.addEventListener("click", function () {
        var type = section.getAttribute("data-excel-format-section");
        if (!DEFAULTS[type]) return;
        var current = readFormat(section);
        current.columns = JSON.parse(JSON.stringify(DEFAULTS[type].columns));
        writeFormat(section, current);
        renderColumns(section, editor, readFormat(section));
      });
    }
  }

  function cacheDefaults() {
    document.querySelectorAll("[data-excel-format-section]").forEach(function (section) {
      var type = section.getAttribute("data-excel-format-section");
      DEFAULTS[type] = JSON.parse(JSON.stringify(readFormat(section)));
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    var sections = document.querySelectorAll("[data-excel-format-section]");
    if (!sections.length) return;
    cacheDefaults();
    sections.forEach(initSection);
  });
})();
