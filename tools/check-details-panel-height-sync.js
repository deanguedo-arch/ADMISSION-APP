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

  for (let i = braceIndex; i < source.length; i += 1) {
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

const context = {
  console,
  ui: {
    resultsPanel: {
      offsetHeight: 840,
      getBoundingClientRect() {
        return { top: 140 };
      },
    },
    detailsPanel: {
      style: { height: "620px", minHeight: "" },
      getBoundingClientRect() {
        return { top: 144 };
      },
    },
  },
};
vm.createContext(context);
vm.runInContext(extractFunction("syncResultsDetailsPanelHeights"), context);

context.syncResultsDetailsPanelHeights();

assert.strictEqual(
  context.ui.detailsPanel.style.height,
  "",
  "Expected details panel fixed height to be cleared so long result detail content is not clipped"
);
assert.strictEqual(
  context.ui.detailsPanel.style.minHeight,
  "840px",
  "Expected side-by-side desktop layout to use a minimum height tied to the results column"
);

console.log("check-details-panel-height-sync: PASS");
