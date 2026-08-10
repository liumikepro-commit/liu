/* ============================================================
 * translator.js — 纯前端翻译引擎 (静态演示版)
 * 与 Python 版核心逻辑保持一致:
 *   语言检测 -> 分词 -> 词典/修正表查询 -> 词形还原 -> 简单规则 -> 组装
 * 在线增强: 调用 MyMemory 免费 API (失败自动回退本地)
 * 数据来源: dict.js (var DICT)
 * ============================================================ */
"use strict";

/* ---------------- 不规则词形表 (与 Python 版一致) ---------------- */
var IRREGULAR = {
  am: "be", is: "be", are: "be", was: "be", were: "be", been: "be", being: "be",
  go: "go", went: "go", gone: "go", going: "go",
  have: "have", has: "have", had: "have", having: "have",
  do: "do", does: "do", did: "do", done: "do", doing: "do",
  make: "make", made: "make", making: "make",
  take: "take", took: "take", taken: "take", taking: "take",
  get: "get", got: "get", gotten: "get", getting: "get",
  see: "see", saw: "see", seen: "see", seeing: "see",
  eat: "eat", ate: "eat", eaten: "eat", eating: "eat",
  run: "run", ran: "run", running: "run",
  write: "write", wrote: "write", written: "write", writing: "write",
  read: "read", reading: "read",
  speak: "speak", spoke: "speak", spoken: "speak", speaking: "speak",
  think: "think", thought: "think", thinking: "think",
  buy: "buy", bought: "buy", buying: "buy",
  bring: "bring", brought: "bring", bringing: "bring",
  come: "come", came: "come", coming: "come",
  give: "give", gave: "give", given: "give", giving: "give",
  know: "know", knew: "know", known: "know", knowing: "know",
  say: "say", said: "say", saying: "say",
  tell: "tell", told: "tell", telling: "tell",
  feel: "feel", felt: "feel", feeling: "feel",
  find: "find", found: "find", finding: "find",
  teach: "teach", taught: "teach", teaching: "teach",
  sleep: "sleep", slept: "sleep", sleeping: "sleep",
  meet: "meet", met: "meet", meeting: "meet",
  sit: "sit", sat: "sit", sitting: "sit",
  stand: "stand", stood: "stand", standing: "stand",
  swim: "swim", swam: "swim", swum: "swim", swimming: "swim",
  drink: "drink", drank: "drink", drunk: "drink", drinking: "drink",
  fly: "fly", flew: "fly", flown: "fly", flying: "fly",
  begin: "begin", began: "begin", begun: "begin", beginning: "begin",
  children: "child", people: "person", men: "man", women: "woman",
  feet: "foot", teeth: "tooth", mice: "mouse"
};

var ARTICLES = { the: 1, a: 1, an: 1 };
var BE_VERBS = { am: "是", is: "是", are: "是", was: "是", were: "是" };
var ZH_CLASSIFIERS = ["个", "只", "本", "张", "把", "条", "件", "双", "块", "片",
                      "位", "名", "辆", "台", "间", "栋", "棵", "朵", "座"];

/* ---------------- 工具函数 ---------------- */
function hasCJK(text) { return /[\u4e00-\u9fff\u3400-\u4dbf]/.test(text); }
function countCJK(text) { return (text.match(/[\u4e00-\u9fff\u3400-\u4dbf]/g) || []).length; }
function countLatin(text) { return (text.match(/[a-zA-Z]/g) || []).length; }

function normalize(text) {
  if (!text) return "";
  // 全角 -> 半角
  var out = "";
  for (var i = 0; i < text.length; i++) {
    var code = text.charCodeAt(i);
    if (code >= 0xFF01 && code <= 0xFF5E) out += String.fromCharCode(code - 0xFEE0);
    else if (code === 0x3000) out += " ";
    else out += text[i];
  }
  return out.replace(/[ \t]+/g, " ").replace(/\n{3,}/g, "\n\n").trim();
}

function splitSentences(text) {
  var protected_ = text.replace(/Mr\./g, "Mr<DOT>").replace(/Mrs\./g, "Mrs<DOT>")
                       .replace(/Dr\./g, "Dr<DOT>").replace(/U\.S\./g, "US<DOT>");
  var chunks = [];
  protected_.split("\n").forEach(function (para) {
    para = para.trim();
    if (!para) return;
    var parts = para.split(/(?<=[。！？!?\.]{1})[\s\n]*/);
    parts.forEach(function (p) {
      p = p.trim().replace(/<DOT>/g, ".");
      if (p) chunks.push(p);
    });
  });
  return chunks;
}

function isNumberWord(t) { return /^[-+]?\d[\d,\.]*%?$/.test(t); }

/* ---------------- 词形还原 ---------------- */
function lemmatize(word) {
  var w = word.toLowerCase();
  var candidates = [];
  var base = IRREGULAR[w];
  if (base) candidates.push(base);
  var suffixRules = [
    ["ies", function (x) { return x.slice(0, -3) + "y"; }],
    ["es", function (x) { return x.slice(0, -2); }],
    ["s", function (x) { return x.slice(0, -1); }],
    ["ing", function (x) { return x.slice(0, -3); }],
    ["ed", function (x) { return x.slice(0, -2); }],
    ["er", function (x) { return x.slice(0, -2); }],
    ["est", function (x) { return x.slice(0, -3); }],
    ["ly", function (x) { return x.slice(0, -2); }],
    ["d", function (x) { return x.slice(0, -1); }]
  ];
  suffixRules.forEach(function (rule) {
    if (w.endsWith(rule[0]) && w.length > rule[0].length + 1) {
      var s = rule[1](w);
      if (s && candidates.indexOf(s) === -1) candidates.push(s);
    }
  });
  // 双写字母还原: running -> runn -> run
  candidates.slice().forEach(function (c) {
    for (var i = 1; i < c.length; i++) {
      if (c[i] === c[i - 1]) {
        var reduced = c.slice(0, i - 1) + c.slice(i);
        if (candidates.indexOf(reduced) === -1) candidates.push(reduced);
      }
    }
  });
  if (candidates.indexOf(w) === -1) candidates.push(w);
  return candidates;
}

/* ---------------- 词典查询 ---------------- */
function lookupEn(word) {
  word = word.toLowerCase();
  if (DICT.en_overrides.hasOwnProperty(word)) return { text: DICT.en_overrides[word], override: true };
  if (DICT.en_zh.hasOwnProperty(word)) return { text: DICT.en_zh[word][0], override: false };
  return null;
}

function lookupEnWithLemma(word) {
  if (IRREGULAR[word.toLowerCase()]) {
    var r = lookupEn(IRREGULAR[word.toLowerCase()]);
    if (r) return r;
  }
  var cands = lemmatize(word);
  for (var i = 0; i < cands.length; i++) {
    var res = lookupEn(cands[i]);
    if (res) return res;
  }
  return null;
}

function lookupZh(word) {
  if (DICT.zh_overrides.hasOwnProperty(word)) return { text: DICT.zh_overrides[word], override: true };
  if (DICT.zh_en.hasOwnProperty(word)) return { text: DICT.zh_en[word][0], override: false };
  return null;
}

/* ---------------- 分词 ---------------- */
function tokenizeEn(text) {
  var tokens = [];
  var re = /[A-Za-z0-9]+(?:['\-][A-Za-z0-9]+)*/g;
  var m, last = 0;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) tokens.push({ t: text.slice(last, m.index), w: false });
    tokens.push({ t: m[0], w: true });
    last = m.index + m[0].length;
  }
  if (last < text.length) tokens.push({ t: text.slice(last), w: false });
  return tokens;
}

function tokenizeZh(text) {
  var tokens = [];
  var i = 0, n = text.length;
  var maxLen = DICT.max_zh_len || 4;
  while (i < n) {
    var matched = null;
    for (var L = Math.min(maxLen, n - i); L >= 1; L--) {
      var cand = text.substr(i, L);
      if (DICT.zh_en.hasOwnProperty(cand) || DICT.zh_overrides.hasOwnProperty(cand)) {
        matched = cand; break;
      }
    }
    if (matched) { tokens.push({ t: matched, w: true }); i += matched.length; }
    else { tokens.push({ t: text[i], w: false }); i++; }
  }
  return tokens;
}

/* ---------------- 单句翻译 ---------------- */
function translateSentenceEnToZh(sentence) {
  var uncovered = [], hits = 0, misses = 0;
  var tokens = tokenizeEn(sentence);
  var parts = [];
  for (var i = 0; i < tokens.length; i++) {
    var tok = tokens[i];
    if (!tok.w) { parts.push(tok.t); continue; }
    if (isNumberWord(tok.t)) { parts.push(tok.t); continue; }
    var lower = tok.t.toLowerCase();
    if (ARTICLES[lower]) continue;
    if (BE_VERBS[lower]) { parts.push(BE_VERBS[lower]); continue; }
    // 人工精选短语匹配 (2 词以上, 跳过空白/标点 token)
    var phraseMatched = false;
    for (var j = i + 1; j < tokens.length && j <= i + 3; j++) {
      if (!tokens[j].w) continue;  // 跳过空白与标点
      var phrase2 = lower + " " + tokens[j].t.toLowerCase();
      if (DICT.en_overrides.hasOwnProperty(phrase2)) {
        parts.push(DICT.en_overrides[phrase2].split("；")[0]);
        i = j; phraseMatched = true;
        break;
      }
    }
    if (phraseMatched) { hits++; continue; }
    var res = lookupEnWithLemma(tok.t);
    if (res) {
      hits++;
      var tr = res.text;
      if (lower.endsWith("ing") && lower.length > 4) tr = "正在" + tr;
      else if (lower.endsWith("ed") && res.form && res.form !== lower) tr = tr + "了";
      parts.push(tr);
    } else {
      misses++;
      uncovered.push(tok.t);
      parts.push(tok.t);
    }
  }
  return { text: joinZh(parts), uncovered: uncovered, hits: hits, misses: misses };
}

function joinZh(parts) {
  var out = "", prevCjk = false;
  for (var i = 0; i < parts.length; i++) {
    var part = parts[i];
    if (!part) continue;
    var isCjk = hasCJK(part);
    if (out && prevCjk && !isCjk && part[0] && ".,;:!?，。；：！？)】」".indexOf(part[0]) === -1) {
      out += " ";
    }
    out += part;
    prevCjk = isCjk;
  }
  return out;
}

function translateSentenceZhToEn(sentence) {
  var uncovered = [], hits = 0, misses = 0;
  var tokens = tokenizeZh(sentence);
  var parts = [];
  for (var i = 0; i < tokens.length; i++) {
    var tok = tokens[i];
    if (!tok.w) { parts.push(toEnPunct(tok.t)); continue; }
    if (isNumberWord(tok.t)) { parts.push(tok.t); continue; }
    if (ZH_CLASSIFIERS.indexOf(tok.t) !== -1 && i > 0 && tokens[i - 1].w) continue;
    var res = lookupZh(tok.t);
    if (res) {
      hits++;
      var tr = res.text;
      if (!res.override) {
        tr = cleanGloss(tr);
      }
      if (tr.indexOf("/") !== -1) tr = tr.split("/")[0].trim();
      parts.push(tr);
    } else {
      misses++;
      uncovered.push(tok.t);
      parts.push(tok.t);
    }
  }
  var text = parts.filter(function (p) { return p; }).join(" ");
  text = cleanEnText(text);
  return { text: text, uncovered: uncovered, hits: hits, misses: misses };
}

function toEnPunct(ch) {
  var map = { "，": ", ", "。": ". ", "！": "! ", "？": "? ", "：": ": ",
              "；": "; ", "、": ", ", "“": '"', "”": '"', "‘": "'", "’": "'",
              "（": "(", "）": ")", "…": "..." };
  return map[ch] !== undefined ? map[ch] : ch;
}

function cleanGloss(g) {
  var s = g.split(";")[0].split(",")[0].replace(/CL:/g, "").trim();
  if (s.indexOf("to ") === 0) s = s.slice(3);
  return s;
}

function cleanEnText(t) {
  return t.replace(/\s+([,.;:!?])/g, "$1").replace(/\s+/g, " ").trim();
}

/* ---------------- 语言检测 ---------------- */
function detectLanguage(text) {
  var cjk = countCJK(text), latin = countLatin(text), total = cjk + latin;
  if (total === 0) return "unknown";
  if (cjk / total >= 0.2) return "zh";
  return "en";
}

/* ---------------- 在线增强 ---------------- */
function translateOnline(text, source, target) {
  var langpair = source + "|" + target;
  var url = "https://api.mymemory.translated.net/get?q=" +
            encodeURIComponent(text) + "&langpair=" + encodeURIComponent(langpair);
  return fetch(url)
    .then(function (r) { return r.json(); })
    .then(function (data) {
      var tr = data.responseData && data.responseData.translatedText;
      if (!tr || (data.responseStatus !== 200 && data.responseStatus !== undefined)) {
        throw new Error("online failed");
      }
      if (tr.indexOf("MYMEMORY WARNING") === 0) throw new Error("quota exceeded");
      return tr;
    });
}

/* ---------------- 主入口 ---------------- */
function translate(text, source, target, useOnline) {
  text = normalize(text);
  if (!text) {
    return Promise.resolve({ error: "输入为空，请输入要翻译的内容。", translation: "" });
  }
  var detected = detectLanguage(text);
  if (detected === "unknown") {
    return Promise.resolve({ error: "无法识别语言，请检查输入内容。", translation: "" });
  }
  var src = (source === "en" || source === "zh") ? source : detected;
  var tgt = (target === "en" || target === "zh") ? target : (src === "en" ? "zh" : "en");

  var doLocal = function () {
    var sentences = splitSentences(text);
    var out = [], uncovered = [], hits = 0, misses = 0;
    sentences.forEach(function (sent) {
      var res = (src === "en") ? translateSentenceEnToZh(sent) : translateSentenceZhToEn(sent);
      out.push(res.text);
      uncovered = uncovered.concat(res.uncovered);
      hits += res.hits; misses += res.misses;
    });
    var translation = out.join(" ");
    if (src === "zh") translation = cleanEnText(translation);
    var coverage = (hits + misses) > 0 ? hits / (hits + misses) : 0;
    return {
      translation: translation, source: src, target: tgt, engine: "local",
      coverage: Math.round(coverage * 1000) / 1000,
      uncovered: uncovered.filter(function (v, i, a) { return a.indexOf(v) === i; }),
      warning: null, error: null
    };
  };

  if (useOnline) {
    return translateOnline(text, src === "zh" ? "zh-CN" : "en", tgt === "zh" ? "zh-CN" : "en")
      .then(function (tr) {
        return { translation: tr, source: src, target: tgt, engine: "online",
                 coverage: 1, uncovered: [], warning: null, error: null };
      })
      .catch(function () { return doLocal(); });
  }
  return Promise.resolve(doLocal());
}
