/* test_js_engine.js — 验证纯前端翻译引擎 (Node 环境)
 * 运行: node tests/test_js_engine.js
 */
"use strict";
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const ROOT = path.join(__dirname, "..");
const ctx = { console };
vm.createContext(ctx);

// 加载词典数据与翻译引擎
vm.runInContext(fs.readFileSync(path.join(ROOT, "static-demo", "js", "dict.js"), "utf8"), ctx);
vm.runInContext(fs.readFileSync(path.join(ROOT, "static-demo", "js", "translator.js"), "utf8"), ctx);

const CASES = [
  "hello world",
  "I like reading books",
  "Thank you very much",
  "Good morning, nice to meet you.",
  "你好世界",
  "我今天很高兴见到你。",
  "我的书。",
  "苹果很好吃。",
];

let failed = 0;
(async function () {
  for (const c of CASES) {
    const r = await vm.runInContext(
      `translate(${JSON.stringify(c)}, "auto", "auto", false)`,
      ctx
    );
    console.log(`${c}  ->  ${r.translation}`);
  }

  // 断言
  const asserts = [
    ["hello world", (r) => r.translation.includes("你好") && r.translation.includes("世界")],
    ["I like reading books", (r) => r.translation.includes("读") && r.translation.includes("书")],
    ["Thank you very much", (r) => r.translation.includes("谢谢")],
    ["你好世界", (r) => r.translation.toLowerCase().includes("hello")],
    ["我的书。", (r) => r.translation.toLowerCase().includes("my") && r.translation.toLowerCase().includes("book")],
  ];
  for (const [input, check] of asserts) {
    const r = await vm.runInContext(
      `translate(${JSON.stringify(input)}, "auto", "auto", false)`,
      ctx
    );
    if (!check(r)) {
      failed++;
      console.log(`FAIL: ${input} -> ${r.translation}`);
    } else {
      console.log(`PASS: ${input}`);
    }
  }
  console.log(failed === 0 ? "\n全部断言通过 ✓" : `\n${failed} 项断言失败 ✗`);
  process.exit(failed === 0 ? 0 : 1);
})();
