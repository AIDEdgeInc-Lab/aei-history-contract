// The JavaScript port against fixtures/golden.json (the same file the Python reference is tested with). Run: node --test tests/
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("fs"), path = require("path");
const c = require("../js/aei_history_contract.js");
const gold = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "fixtures", "golden.json"), "utf8"));
const camel = (s) => s.replace(/_([a-z])/g, (_, ch) => ch.toUpperCase());
test("version matches the Python reference and pyproject", () => {
  assert.equal(c.VERSION, gold.version);
  assert.match(fs.readFileSync(path.join(__dirname, "..", "pyproject.toml"), "utf8"), new RegExp(`version = "${c.VERSION}"`));
});
for (const k of gold.cases) {
  test(k.name, () => {
    const out = c[camel(k.fn)](...structuredClone(k.args));
    assert.deepStrictEqual(JSON.parse(JSON.stringify(out)), k.expected);
  });
}
