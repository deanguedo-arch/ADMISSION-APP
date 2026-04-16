const assert = require("assert");
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const repoRoot = path.resolve(__dirname, "..");
const sourcePath = path.join(repoRoot, "apps_script", "WebAppScriptFunctions.html");
const source = fs.readFileSync(sourcePath, "utf8");

function extractFunction(name) {
  const needle = `function ${name}(`;
  const start = source.indexOf(needle);
  assert(start >= 0, `Missing function ${name}`);

  let braceIndex = source.indexOf("{", start);
  assert(braceIndex >= 0, `Missing opening brace for ${name}`);

  let depth = 0;
  let inSingle = false;
  let inDouble = false;
  let inTemplate = false;
  let inLineComment = false;
  let inBlockComment = false;

  for (let i = braceIndex; i < source.length; i++) {
    const ch = source[i];
    const next = source[i + 1];
    const prev = source[i - 1];

    if (inLineComment) {
      if (ch === "\n") inLineComment = false;
      continue;
    }
    if (inBlockComment) {
      if (prev === "*" && ch === "/") inBlockComment = false;
      continue;
    }
    if (inSingle) {
      if (ch === "'" && prev !== "\\") inSingle = false;
      continue;
    }
    if (inDouble) {
      if (ch === '"' && prev !== "\\") inDouble = false;
      continue;
    }
    if (inTemplate) {
      if (ch === "`" && prev !== "\\") inTemplate = false;
      continue;
    }

    if (ch === "/" && next === "/") {
      inLineComment = true;
      i += 1;
      continue;
    }
    if (ch === "/" && next === "*") {
      inBlockComment = true;
      i += 1;
      continue;
    }
    if (ch === "'") {
      inSingle = true;
      continue;
    }
    if (ch === '"') {
      inDouble = true;
      continue;
    }
    if (ch === "`") {
      inTemplate = true;
      continue;
    }

    if (ch === "{") depth += 1;
    if (ch === "}") {
      depth -= 1;
      if (depth === 0) return source.slice(start, i + 1);
    }
  }

  throw new Error(`Unclosed function ${name}`);
}

function makeInput(value) {
  return {
    value,
    setAttribute() {},
    classList: { toggle() {} },
  };
}

function makeErrorEl() {
  return { textContent: "" };
}

function makeNamedRow(course, mark) {
  const courseInput = makeInput(course);
  const markInput = makeInput(mark);
  const errorEl = makeErrorEl();
  const row = {
    removed: false,
    querySelector(selector) {
      if (selector === 'td:nth-child(1) input') return courseInput;
      if (selector === "input.mark-input") return markInput;
      if (selector === ".cell-error") return errorEl;
      return null;
    },
    remove() {
      this.removed = true;
    },
  };
  return { row, courseInput, markInput, errorEl };
}

const statusCalls = [];
const context = {
  console,
  state: {
    boot: {
      namedCourseOptions: ["English 30-1"],
      electiveCourseOptions: [],
    },
  },
  ui: {
    namedBody: {
      rows: [],
      querySelectorAll() {
        return this.rows.filter((row) => !row.removed);
      },
    },
  },
  setStatus(message) {
    statusCalls.push(String(message || ""));
  },
};
vm.createContext(context);

[
  "formatMarkDisplay",
  "normalizeCourseToken",
  "parseMarkInput",
  "validateMarkField",
  "buildCourseLookup",
  "resolveCourseLabel",
  "syncNamedRowMark_",
  "dedupeNamedRowsForActiveRow_",
].forEach((name) => {
  vm.runInContext(extractFunction(name), context);
});

const { row: existingRow, markInput: existingMark, errorEl: existingError } = makeNamedRow("English 30-1", "72");
const { row: duplicateRow, markInput: duplicateMark } = makeNamedRow("English 30-1", "88");
context.ui.namedBody.rows = [existingRow, duplicateRow];

context.dedupeNamedRowsForActiveRow_(duplicateRow);

assert.strictEqual(existingRow.removed, false, "Existing row should be preserved");
assert.strictEqual(duplicateRow.removed, true, "New duplicate row should be removed after upsert");
assert.strictEqual(existingMark.value, "88", "Existing row should receive the latest entered mark");
assert.strictEqual(existingError.textContent, "", "Existing row should remain valid after mark upsert");
assert(
  statusCalls.some((message) => /updated the existing course/i.test(message)),
  "Expected duplicate upsert to tell the user the existing course was updated"
);

console.log("check-course-input-upsert: PASS");
