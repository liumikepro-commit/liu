/* ============================================================
   app.js — 翻译 Agent 前端逻辑
   功能: 文本翻译、文档翻译(上传/进度/下载)、语言切换、错误处理
   ============================================================ */
(function () {
  "use strict";

  // ---- DOM 引用 ----
  var inputText = document.getElementById("inputText");
  var outputText = document.getElementById("outputText");
  var sourceLang = document.getElementById("sourceLang");
  var targetLang = document.getElementById("targetLang");
  var swapBtn = document.getElementById("swapBtn");
  var translateBtn = document.getElementById("translateBtn");
  var clearBtn = document.getElementById("clearBtn");
  var copyBtn = document.getElementById("copyBtn");
  var charCount = document.getElementById("charCount");
  var engineTag = document.getElementById("engineTag");
  var warningBox = document.getElementById("warningBox");
  var metaBar = document.getElementById("metaBar");
  var onlineBadge = document.getElementById("onlineBadge");
  var useOnline = document.getElementById("useOnline");

  // 文档翻译相关 DOM
  var tabText = document.getElementById("tabText");
  var tabDoc = document.getElementById("tabDoc");
  var panelText = document.getElementById("panelText");
  var panelDoc = document.getElementById("panelDoc");
  var dropZone = document.getElementById("dropZone");
  var fileInput = document.getElementById("fileInput");
  var fileInfo = document.getElementById("fileInfo");
  var fileName = document.getElementById("fileName");
  var removeFileBtn = document.getElementById("removeFileBtn");
  var docSourceLang = document.getElementById("docSourceLang");
  var docTargetLang = document.getElementById("docTargetLang");
  var docUseOnline = document.getElementById("docUseOnline");
  var docBilingual = document.getElementById("docBilingual");
  var docTranslateBtn = document.getElementById("docTranslateBtn");
  var progressArea = document.getElementById("progressArea");
  var progressBar = document.getElementById("progressBar");
  var progressText = document.getElementById("progressText");
  var docResultArea = document.getElementById("docResultArea");
  var downloadPdf = document.getElementById("downloadPdf");
  var docErrorBox = document.getElementById("docErrorBox");

  var MAX_LEN = 100000; // 与后端 config.MAX_INPUT_LEN 保持一致
  var lastTranslation = "";
  var selectedFile = null;   // 当前选择的文档
  var currentTaskId = null;  // 当前文档翻译任务

  // 语言代码 -> 显示名称(与后端 SUPPORTED_LANGUAGES 一致)
  var LANG_NAMES = {
    "zh": "中文", "en": "英语", "ja": "日语", "ko": "韩语",
    "fr": "法语", "de": "德语", "es": "西班牙语", "ru": "俄语",
    "ar": "阿拉伯语", "pt": "葡萄牙语", "th": "泰语"
  };

  // 获取语言方向文字
  function langDir(src, tgt) {
    var s = LANG_NAMES[src] || src;
    var t = LANG_NAMES[tgt] || tgt;
    return s + " → " + t;
  }

  // ============================================================
  // 文本翻译逻辑
  // ============================================================

  // ---- 输入字数统计 ----
  inputText.addEventListener("input", function () {
    var len = inputText.value.length;
    charCount.textContent = len + " / " + MAX_LEN;
    if (len > MAX_LEN) {
      inputText.value = inputText.value.slice(0, MAX_LEN);
      charCount.textContent = MAX_LEN + " / " + MAX_LEN;
    }
  });

  // ---- 交换语言方向 ----
  swapBtn.addEventListener("click", function () {
    var src = sourceLang.value, tgt = targetLang.value;
    if (src !== "auto") sourceLang.value = tgt;
    if (tgt !== "auto") targetLang.value = src;
  });

  // ---- 清空 ----
  clearBtn.addEventListener("click", function () {
    inputText.value = "";
    charCount.textContent = "0 / " + MAX_LEN;
    outputText.textContent = "";
    outputText.innerHTML = '<span class="placeholder">译文将显示在这里</span>';
    engineTag.textContent = "";
    warningBox.classList.add("hidden");
    metaBar.classList.add("hidden");
    copyBtn.disabled = true;
    inputText.focus();
  });

  // ---- 复制 ----
  copyBtn.addEventListener("click", function () {
    if (!lastTranslation) return;
    navigator.clipboard.writeText(lastTranslation).then(function () {
      copyBtn.textContent = "已复制 ✓";
      setTimeout(function () { copyBtn.textContent = "复制"; }, 1200);
    }).catch(function () { alert("复制失败，请手动选择复制。"); });
  });

  // ---- 回车触发翻译 (Ctrl/Cmd + Enter) ----
  inputText.addEventListener("keydown", function (e) {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") doTranslate();
  });

  // ---- 在线状态指示 ----
  useOnline.addEventListener("change", function () {
    onlineBadge.classList.toggle("off", !useOnline.checked);
    onlineBadge.textContent = useOnline.checked ? "● 在线" : "○ 离线";
  });

  // ---- 核心: 翻译请求 ----
  function doTranslate() {
    var text = inputText.value.trim();
    if (!text) {
      showError("请输入要翻译的内容。");
      return;
    }

    translateBtn.disabled = true;
    translateBtn.innerHTML = '<span class="btn-icon">⏳</span> 翻译中…';
    warningBox.classList.add("hidden");
    metaBar.classList.add("hidden");

    fetch("/api/translate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        text: text,
        source: sourceLang.value,
        target: targetLang.value,
        use_online: useOnline.checked
      })
    })
      .then(function (resp) { return resp.json(); })
      .then(function (data) {
        renderResult(data);
      })
      .catch(function () {
        showError("网络请求失败，请检查服务是否运行。");
      })
      .finally(function () {
        translateBtn.disabled = false;
        translateBtn.innerHTML = '<span class="btn-icon">⚡</span> 翻 译';
      });
  }

  // ---- 渲染结果 ----
  function renderResult(data) {
    if (data.error) { showError(data.error); return; }

    lastTranslation = data.translation || "";
    outputText.classList.remove("error");
    outputText.textContent = lastTranslation || "（空译文）";
    copyBtn.disabled = false;

    // 引擎标识
    updateEngineTag(data.engine, data.relay);

    // 元信息
    var dir = langDir(data.source, data.target);
    var engineName = data.engine === "online" ? "在线" :
                     data.engine === "tm" ? "翻译记忆" :
                     data.engine === "relay" ? "中转翻译" : "本地";
    metaBar.innerHTML =
      '<span class="tag">方向: ' + dir + '</span>' +
      '<span class="tag">引擎: ' + engineName + '</span>' +
      (data.engine === "local"
        ? '<span class="tag">词典覆盖率: ' + Math.round((data.coverage || 0) * 100) + '%</span>'
        : "");

    // 未收录提示
    if (data.warning) {
      warningBox.textContent = "⚠ " + data.warning;
      warningBox.classList.remove("hidden");
    }
    metaBar.classList.remove("hidden");
  }

  function showError(msg) {
    outputText.classList.add("error");
    outputText.textContent = msg;
    engineTag.textContent = "";
    copyBtn.disabled = true;
    warningBox.classList.add("hidden");
  }

  // 引擎标识(tm/relay 适配)
  function updateEngineTag(engine, isRelay) {
    if (engine === "online") {
      engineTag.textContent = "在线翻译";
      engineTag.className = "engine-tag online";
    } else if (engine === "tm") {
      engineTag.textContent = "翻译记忆";
      engineTag.className = "engine-tag online";
    } else if (engine === "relay" || isRelay) {
      engineTag.textContent = "中转翻译";
      engineTag.className = "engine-tag relay";
    } else {
      engineTag.textContent = "本地词典";
      engineTag.className = "engine-tag local";
    }
  }

  // ---- 绑定翻译按钮 ----
  translateBtn.addEventListener("click", doTranslate);

  // ============================================================
  // 文档翻译逻辑
  // ============================================================

  // ---- Tab 切换 ----
  function switchTab(which) {
    var isDoc = which === "doc";
    tabText.classList.toggle("active", !isDoc);
    tabDoc.classList.toggle("active", isDoc);
    panelText.classList.toggle("hidden", isDoc);
    panelDoc.classList.toggle("hidden", !isDoc);
  }
  tabText.addEventListener("click", function () { switchTab("text"); });
  tabDoc.addEventListener("click", function () { switchTab("doc"); });

  // ---- 文件选择: 点击 & 拖拽 ----
  dropZone.addEventListener("click", function () { fileInput.click(); });
  dropZone.addEventListener("dragover", function (e) {
    e.preventDefault();
    dropZone.classList.add("drag-over");
  });
  dropZone.addEventListener("dragleave", function () {
    dropZone.classList.remove("drag-over");
  });
  dropZone.addEventListener("drop", function (e) {
    e.preventDefault();
    dropZone.classList.remove("drag-over");
    if (e.dataTransfer.files.length) selectFile(e.dataTransfer.files[0]);
  });
  fileInput.addEventListener("change", function () {
    if (fileInput.files.length) selectFile(fileInput.files[0]);
  });

  function selectFile(file) {
    // 前端格式预校验(与后端一致, 给出清晰提示)
    var ext = (file.name.split(".").pop() || "").toLowerCase();
    if (ext !== "pdf" && ext !== "docx") {
      showDocError(ext === "doc"
        ? "暂不支持旧版 Word (.doc)。请先用 Word 将文档另存为 .docx 后再上传。"
        : "不支持的文件格式 ." + ext + "，当前支持 PDF (.pdf) 与 Word (.docx)。");
      return;
    }
    if (file.size > 20 * 1024 * 1024) {
      showDocError("文件过大（" + Math.round(file.size / 1048576) + "MB），单文件请控制在 20MB 以内。");
      return;
    }
    selectedFile = file;
    fileName.textContent = "📎 " + file.name + "（" + Math.round(file.size / 1024) + " KB）";
    fileInfo.classList.remove("hidden");
    dropZone.classList.add("hidden");
    docTranslateBtn.disabled = false;
    hideDocError();
    hideResult();
  }

  removeFileBtn.addEventListener("click", function () {
    selectedFile = null;
    fileInfo.classList.add("hidden");
    dropZone.classList.remove("hidden");
    docTranslateBtn.disabled = true;
  });

  // ---- 上传并翻译 ----
  docTranslateBtn.addEventListener("click", function () {
    if (!selectedFile) return;
    var fd = new FormData();
    fd.append("file", selectedFile);
    fd.append("source", docSourceLang.value);
    fd.append("target", docTargetLang.value);
    fd.append("use_online", docUseOnline.checked ? "true" : "false");
    fd.append("bilingual", docBilingual.checked ? "true" : "false");

    docTranslateBtn.disabled = true;
    hideDocError();
    hideResult();
    progressArea.classList.remove("hidden");
    setProgress(0, "正在上传文件…");

    fetch("/api/documents/translate", { method: "POST", body: fd })
      .then(function (resp) { return resp.json().then(function (d) { return { ok: resp.ok, data: d }; }); })
      .then(function (res) {
        if (!res.ok) throw new Error(res.data.error || "上传失败");
        currentTaskId = res.data.task_id;
        pollStatus();
      })
      .catch(function (err) {
        progressArea.classList.add("hidden");
        showDocError(err.message || "上传失败，请重试。");
        docTranslateBtn.disabled = false;
      });
  });

  // ---- 进度轮询 ----
  function pollStatus() {
    if (!currentTaskId) return;
    fetch("/api/documents/status/" + currentTaskId)
      .then(function (resp) { return resp.json(); })
      .then(function (task) {
        if (task.error) throw new Error(task.error);
        if (task.status === "running" || task.status === "pending") {
          setProgress(task.progress || 0, task.message || "处理中…");
          setTimeout(pollStatus, 1200);
        } else if (task.status === "done") {
          setProgress(100, "翻译完成");
          finishSuccess();
        } else {
          progressArea.classList.add("hidden");
          showDocError(task.error || "文档处理失败，请重试。");
          docTranslateBtn.disabled = false;
        }
      })
      .catch(function (err) {
        progressArea.classList.add("hidden");
        showDocError(err.message || "查询任务状态失败。");
        docTranslateBtn.disabled = false;
      });
  }

  function setProgress(pct, msg) {
    progressBar.style.width = pct + "%";
    progressText.textContent = msg;
  }

  // ---- 结果展示与下载 ----
  function finishSuccess() {
    setTimeout(function () {
      progressArea.classList.add("hidden");
      docResultArea.classList.remove("hidden");
      downloadPdf.href = "/api/documents/download/" + currentTaskId;
      docTranslateBtn.disabled = false;
    }, 400);
  }

  function hideResult() {
    docResultArea.classList.add("hidden");
  }

  function showDocError(msg) {
    docErrorBox.textContent = "⚠ " + msg;
    docErrorBox.classList.remove("hidden");
  }
  function hideDocError() {
    docErrorBox.classList.add("hidden");
  }

  // ============================================================
  // 设置面板
  // ============================================================
  var settingsModal = document.getElementById("settingsModal");
  var settingsBtn = document.getElementById("settingsBtn");
  var settingsClose = document.getElementById("settingsClose");
  var providerSelect = document.getElementById("providerSelect");
  var keyFields = document.getElementById("keyFields");
  var glossaryLang = document.getElementById("glossaryLang");
  var glossaryTerm = document.getElementById("glossaryTerm");
  var glossaryTarget = document.getElementById("glossaryTarget");
  var glossaryAddBtn = document.getElementById("glossaryAddBtn");
  var glossaryList = document.getElementById("glossaryList");
  var tmEnabled = document.getElementById("tmEnabled");
  var tmStats = document.getElementById("tmStats");
  var tmClearBtn = document.getElementById("tmClearBtn");
  var settingsSaveBtn = document.getElementById("settingsSaveBtn");
  var settingsMsg = document.getElementById("settingsMsg");

  // 各引擎的 Key 字段配置
  var PROVIDER_FIELDS = {
    deepl: [{ key: "deepl_api_key", label: "DeepL API Key", placeholder: "如 xxxx-xxxx-xxxx-xxxx" }],
    baidu: [
      { key: "baidu_app_id", label: "APP ID", placeholder: "百度翻译开放平台 AppID" },
      { key: "baidu_secret_key", label: "密钥", placeholder: "密钥" }
    ],
    tencent: [
      { key: "tencent_secret_id", label: "SecretId", placeholder: "腾讯云 SecretId" },
      { key: "tencent_secret_key", label: "SecretKey", placeholder: "腾讯云 SecretKey" }
    ],
    openai: [
      { key: "openai_api_key", label: "API Key", placeholder: "sk-..." },
      { key: "openai_base_url", label: "接口地址", placeholder: "https://api.openai.com/v1" },
      { key: "openai_model", label: "模型", placeholder: "gpt-4o-mini" }
    ]
  };
  var settingsData = { glossary: { en: {}, zh: {} } };

  settingsBtn.addEventListener("click", openSettings);
  settingsClose.addEventListener("click", function () { settingsModal.classList.add("hidden"); });
  settingsModal.addEventListener("click", function (e) {
    if (e.target === settingsModal) settingsModal.classList.add("hidden");
  });

  function openSettings() {
    settingsMsg.textContent = "";
    settingsMsg.className = "settings-msg";
    settingsModal.classList.remove("hidden");
    fetch("/api/settings").then(function (r) { return r.json(); }).then(function (data) {
      settingsData = data;
      providerSelect.value = data.translator_provider || "google";
      renderKeyFields();
      renderGlossary();
      tmEnabled.checked = data.tm_enabled !== false;
      renderTmStats(data.tm_stats);
    });
  }

  function renderKeyFields() {
    var provider = providerSelect.value;
    var fields = PROVIDER_FIELDS[provider] || [];
    if (!fields.length) {
      keyFields.innerHTML = '<p class="settings-hint">Google / MyMemory 为免费引擎，无需配置 Key。</p>';
      return;
    }
    keyFields.innerHTML = "";
    fields.forEach(function (f) {
      var row = document.createElement("div");
      row.className = "field-row";
      var label = document.createElement("label");
      label.textContent = f.label;
      var input = document.createElement("input");
      input.type = "text";
      input.className = "settings-input";
      input.placeholder = f.placeholder;
      input.dataset.key = f.key;
      // 已配置的 Key 不回显, 用提示占位
      if (settingsData[f.key + "_configured"]) input.placeholder = "已配置（留空保持不变）";
      row.appendChild(label);
      row.appendChild(input);
      keyFields.appendChild(row);
    });
  }
  providerSelect.addEventListener("change", renderKeyFields);

  // ---- 术语表 ----
  function renderGlossary() {
    var g = settingsData.glossary || { en: {}, zh: {} };
    var lang = glossaryLang.value;
    var entries = Object.keys(g[lang] || {});
    if (!entries.length) {
      glossaryList.innerHTML = '<p class="glossary-empty">暂无术语，添加后翻译将强制使用指定译法。</p>';
      return;
    }
    glossaryList.innerHTML = "";
    entries.forEach(function (term) {
      var item = document.createElement("div");
      item.className = "glossary-item";
      item.innerHTML =
        '<span><span class="gt-term"></span><span class="gt-arrow">→</span><span class="gt-target"></span></span>' +
        '<button class="gt-del" title="删除">✕</button>';
      item.querySelector(".gt-term").textContent = term;
      item.querySelector(".gt-target").textContent = g[lang][term];
      item.querySelector(".gt-del").addEventListener("click", function () {
        fetch("/api/glossary?lang=" + lang + "&term=" + encodeURIComponent(term),
              { method: "DELETE" })
          .then(function (r) { return r.json(); })
          .then(function (d) {
            settingsData.glossary = d.glossary;
            renderGlossary();
          });
      });
      glossaryList.appendChild(item);
    });
  }
  glossaryLang.addEventListener("change", renderGlossary);

  glossaryAddBtn.addEventListener("click", function () {
    var term = glossaryTerm.value.trim();
    var target = glossaryTarget.value.trim();
    if (!term || !target) { flashMsg("术语与译文不能为空", true); return; }
    fetch("/api/glossary", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ lang: glossaryLang.value, term: term, target: target })
    }).then(function (r) { return r.json(); }).then(function (d) {
      if (d.error) { flashMsg(d.error, true); return; }
      glossaryTerm.value = "";
      glossaryTarget.value = "";
      settingsData.glossary = d.glossary;
      renderGlossary();
      flashMsg(d.message, false);
    });
  });

  // ---- 翻译记忆 ----
  function renderTmStats(stats) {
    tmStats.textContent = stats ? "（" + stats.entries + " 条记忆，命中 " + stats.hits + " 次）" : "";
  }
  tmClearBtn.addEventListener("click", function () {
    fetch("/api/tm/clear", { method: "POST" })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        renderTmStats(d.stats);
        flashMsg("翻译记忆已清空", false);
      });
  });

  // ---- 保存 ----
  settingsSaveBtn.addEventListener("click", function () {
    var payload = { translator_provider: providerSelect.value };
    keyFields.querySelectorAll("input[data-key]").forEach(function (input) {
      if (input.value.trim()) payload[input.dataset.key] = input.value.trim();
    });
    payload.tm_enabled = tmEnabled.checked;
    fetch("/api/settings", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    }).then(function (r) { return r.json(); }).then(function (d) {
      if (d.error) { flashMsg(d.error, true); return; }
      flashMsg("设置已保存 ✓", false);
    });
  });

  function flashMsg(msg, isError) {
    settingsMsg.textContent = msg;
    settingsMsg.className = "settings-msg" + (isError ? " error" : "");
    setTimeout(function () { settingsMsg.textContent = ""; }, 2500);
  }
})();
