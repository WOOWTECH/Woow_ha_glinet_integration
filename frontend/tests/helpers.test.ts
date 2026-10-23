// Unit tests for the panel's pure helpers and for the contract between the panel's strings and the backend.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import { en, explain, formatBytes, formatDuration, formatRate, makeTranslate, zh } from "../src/i18n.ts";
import { niceCeil } from "../src/util.ts";

const backend = (file: string) => readFileSync(new URL(`../../custom_components/woow_glinet/${file}`, import.meta.url), "utf8");

test("formatBytes uses decimal prefixes and carries on rounding", () => {
  assert.equal(formatBytes(0), "0 B");
  assert.equal(formatBytes(-5), "0 B");
  assert.equal(formatBytes(999), "999 B");
  assert.equal(formatBytes(999.6), "1.00 kB");
  assert.equal(formatBytes(1000), "1.00 kB");
  assert.equal(formatBytes(12345), "12.3 kB");
  assert.equal(formatBytes(999_500), "1.00 MB");
  assert.equal(formatBytes(1_234_000_000), "1.23 GB");
  assert.equal(formatBytes(5e15), "5000 TB");
  assert.equal(formatRate(2500), "2.50 kB/s");
});

test("formatDuration", () => {
  assert.equal(formatDuration(0), "0m");
  assert.equal(formatDuration(125), "2m");
  assert.equal(formatDuration(3700), "1h 1m");
  assert.equal(formatDuration(90061), "1d 1h");
  assert.equal(formatDuration(-3), "0m");
});

test("niceCeil picks 1 / 2 / 5 x 10^k", () => {
  assert.equal(niceCeil(0), 1);
  assert.equal(niceCeil(1), 1);
  assert.equal(niceCeil(1.1), 2);
  assert.equal(niceCeil(3), 5);
  assert.equal(niceCeil(7), 10);
  assert.equal(niceCeil(1234), 2000);
  assert.equal(niceCeil(99999), 100000);
});

test("both languages have the same keys and the same {placeholders}", () => {
  assert.deepEqual(Object.keys(en).sort(), Object.keys(zh).sort());
  const holes = (text: string) => [...text.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort();
  for (const key of Object.keys(en) as (keyof typeof en)[]) {
    assert.ok(en[key].trim() && zh[key].trim(), `${key} is empty`);
    assert.deepEqual(holes(en[key]), holes(zh[key]), `placeholders differ in ${key}`);
  }
});

test("every error code the backend can send has a translated message", () => {
  const codes = new Set<string>();
  for (const m of backend("actions.py").matchAll(/ActionError\(\s*"(\w+)"/g)) codes.add(m[1]);
  for (const m of backend("websocket_api.py").matchAll(/send_error\(msg\["id"\],\s*"(\w+)"/g)) codes.add(m[1]);
  for (const code of ["api_error", "failed", "not_loaded"]) codes.add(code);
  assert.ok(codes.size >= 12, `found only ${[...codes]}`);
  for (const code of codes) {
    for (const [lang, dict] of [["en", en], ["zh", zh]] as const) {
      assert.ok(`err_${code}` in dict, `no err_${code} in ${lang}`);
    }
  }
});

test("every activity message the backend writes has a translation", () => {
  const block = backend("activity.py").split("MESSAGES = {")[1].split("\n}")[0];
  const msgs = [...block.matchAll(/^\s+"(\w+)":/gm)].map((m) => m[1]);
  assert.ok(msgs.length >= 12);
  for (const msg of msgs) {
    assert.ok(`log_${msg}` in en && `log_${msg}` in zh, `log_${msg} is missing`);
  }
});

test("explain() shows the translated text for known codes and the raw message otherwise", () => {
  const t = makeTranslate("en");
  assert.equal(explain({ code: "invalid_mac", message: "x" }, t), en.err_invalid_mac);
  assert.ok(explain({ code: "api_error", message: "router said no" }, t).endsWith(": router said no"));
  assert.equal(explain({ code: "something_new", message: "odd" }, t), "Error: odd");
  assert.equal(explain(new Error("plain"), makeTranslate("zh-Hant")), "錯誤：plain");
});

test("translations of the backend and the panel agree on Chinese vs English selection", () => {
  assert.equal(makeTranslate("zh-TW")("tab_overview"), "總覽");
  assert.equal(makeTranslate("zh-Hant")("tab_overview"), "總覽");
  assert.equal(makeTranslate("en-GB")("tab_overview"), "Overview");
  assert.equal(makeTranslate("de")("tab_overview"), "Overview");
});
