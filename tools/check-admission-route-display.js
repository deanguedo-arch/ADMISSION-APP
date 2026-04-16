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

const context = {
  console,
  uniqueStrings(values) {
    const seen = new Set();
    const out = [];
    for (const value of values || []) {
      const key = String(value || "");
      if (!key || seen.has(key)) continue;
      seen.add(key);
      out.push(key);
    }
    return out;
  },
};
vm.createContext(context);

[
  "normalizeDisplayCopy_",
  "ensureSentenceDisplay_",
  "sentenceCaseDisplay_",
  "requirementTypeBaseLabel_",
  "requirementTypeNoteLabel_",
  "formatRequirementTypeForDisplay_",
  "admissionRouteNoteBullet_",
  "buildAdmissionRouteDisplay_",
].forEach((name) => {
  vm.runInContext(extractFunction(name), context);
});

const buildAdmissionRouteDisplay_ = context.buildAdmissionRouteDisplay_;

const albertaHs = buildAdmissionRouteDisplay_({
  requirementType: "alberta_high_school_courses; notes: max 1 group b; notes: regular admission",
  requirements: [{ label: "English", requirement: "English 30-1", minMark: 50 }],
  average: { totalCourses: 5 },
  electives: { allowedGroups: ["A", "B", "C"] },
});

assert.strictEqual(albertaHs.summary, "Alberta high school course requirements");
assert(
  albertaHs.bullets.includes("Admission average uses 5 subjects"),
  "Expected average-course-count bullet"
);
assert(
  albertaHs.bullets.includes("English: English 30-1"),
  "Expected English requirement bullet"
);
assert(
  albertaHs.bullets.includes("Remaining 4 subjects can come from Groups A/B/C"),
  "Expected remaining-group bullet"
);
assert(
  albertaHs.bullets.includes("Maximum 1 subject from Group B"),
  "Expected group-limit bullet"
);
assert(
  albertaHs.bullets.includes("Minimum 50% in each listed subject"),
  "Expected minimum-mark bullet"
);

const placement = buildAdmissionRouteDisplay_({
  requirementType: "placement_assessment",
  requirements: [],
  average: {},
  electives: {},
});

assert.strictEqual(placement.summary, "Placement assessment required");
assert(
  placement.bullets.includes("Confirm required assessment steps on the official program page"),
  "Expected placement guidance bullet"
);

console.log("check-admission-route-display: PASS");
