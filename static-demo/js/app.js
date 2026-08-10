/* ============================================================
 * app.js — 纯前端演示版交互逻辑
 * 与 Flask 版 UI 一致, 翻译调用改为浏览器端 translate() 引擎
 * ============================================================ */
(function () {
  "use strict";

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

  var MAX_LEN = 5000;
  var lastTranslation = "";

  inputText.addEventListener("input", function () {
    var len = inputText.value.length;
    charCount.textContent = len + " / " + MAX_LEN;
    if (len > MAX_LEN) {
      inputText.value = inputText.value.slice(0, MAX_LEN);
      charCount.textContent = MAX_LEN + " / " + MAX_LEN;
    }
  });

  swapBtn.addEventListener("click", function () {
    var src = sourceLang.value, tgt = targetLang.value;
    if (src !== "auto") sourceLang.value = tgt;
    if (tgt !== "auto") targetLang.value = src;
  });

  clearBtn.addEventListener("click", function () {
    inputText.value = "";
    charCount.textContent = "0 / " + MAX_LEN;
    outputText.innerHTML = '<span class="placeholder">译文将显示在这里</span>';
    engineTag.textContent = "";
    warningBox.classList.add("hidden");
    metaBar.classList.add("hidden");
    copyBtn.disabled = true;
    inputText.focus();
  });

  copyBtn.addEventListener("click", function () {
    if (!lastTranslation) return;
    navigator.clipboard.writeText(lastTranslation).then(function () {
      copyBtn.textContent = "已复制 ✓";
      setTimeout(function () { copyBtn.textContent = "复制"; }, 1200);
    }).catch(function () { alert("复制失败，请手动选择复制。"); });
  });

  inputText.addEventListener("keydown", function (e) {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") doTranslate();
  });

  useOnline.addEventListener("change", function () {
    onlineBadge.classList.toggle("off", !useOnline.checked);
    onlineBadge.textContent = useOnline.checked ? "● 在线" : "○ 离线";
  });

  function doTranslate() {
    var text = inputText.value.trim();
    if (!text) { showError("请输入要翻译的内容。"); return; }

    translateBtn.disabled = true;
    translateBtn.innerHTML = '<span class="btn-icon">⏳</span> 翻译中…';
    warningBox.classList.add("hidden");
    metaBar.classList.add("hidden");

    translate(text, sourceLang.value, targetLang.value, useOnline.checked)
      .then(renderResult)
      .catch(function () { showError("翻译过程发生错误，请重试。"); })
      .finally(function () {
        translateBtn.disabled = false;
        translateBtn.innerHTML = '<span class="btn-icon">⚡</span> 翻 译';
      });
  }

  function renderResult(data) {
    if (data.error) { showError(data.error); return; }
    lastTranslation = data.translation || "";
    outputText.classList.remove("error");
    outputText.textContent = lastTranslation || "（空译文）";
    copyBtn.disabled = false;

    if (data.engine === "online") {
      engineTag.textContent = "在线翻译";
      engineTag.className = "engine-tag online";
    } else {
      engineTag.textContent = "本地词典";
      engineTag.className = "engine-tag local";
    }

    var langName = data.source === "en" ? "英→中" : data.source === "zh" ? "中→英" : "";
    metaBar.innerHTML =
      '<span class="tag">方向: ' + langName + '</span>' +
      '<span class="tag">引擎: ' + (data.engine === "online" ? "在线" : "本地") + '</span>' +
      (data.engine === "local"
        ? '<span class="tag">词典覆盖率: ' + Math.round((data.coverage || 0) * 100) + '%</span>'
        : "");
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

  translateBtn.addEventListener("click", doTranslate);
})();
