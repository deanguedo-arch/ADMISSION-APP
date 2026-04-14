const assert = require("assert");
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const repoRoot = path.resolve(__dirname, "..");
const context = vm.createContext({
  console,
  Date,
  Math,
  Number,
  String,
  Array,
  Object,
  RegExp,
  isFinite,
  NaN,
});

[
  "apps_script/EligibilityShared.gs",
  "apps_script/EligibilityProgramsData.gs",
  "apps_script/EligibilityEngine.gs",
].forEach((relativePath) => {
  const fullPath = path.join(repoRoot, relativePath);
  const code = fs.readFileSync(fullPath, "utf8");
  vm.runInContext(code, context, { filename: relativePath });
});

function evaluate(overrides) {
  const today = new Date().toISOString().slice(0, 10);
  return context.evaluateConfidenceForProgram_(
    Object.assign(
      {
        requirementTypeEffective: "alberta_high_school_courses",
        englishReq: "English 30-1",
        mathReq: "Math 30-1",
        socialReq: "",
        scienceReq: "",
        electiveQty: "3",
        avgMin: 60,
        avgTotalFromData: 5,
        avgTotalResolved: 5,
        notes: [],
        advisories: [],
        sourceUrl: "https://example.edu/program",
        datasetDate: today,
        staleDaysCap: 60,
      },
      overrides || {}
    )
  );
}

function main() {
  const high = evaluate();
  assert.strictEqual(high.confidence, "High", "course-only rows should remain high confidence");

  const token = evaluate({ requirementTypeEffective: "placement_assessment; notes: math placement test accepted" });
  assert.strictEqual(
    token.confidence,
    "Uncheckable",
    "placement_assessment rows must require manual review instead of Likely eligible"
  );
  assert.match(token.uncheckableReason, /placement|assessment/i);

  const advisory = evaluate({ advisories: ["Math: assessment/placement required"] });
  assert.strictEqual(
    advisory.confidence,
    "Uncheckable",
    "assessment advisories must require manual review instead of Likely eligible"
  );
  assert.match(advisory.uncheckableReason, /placement|assessment/i);

  console.log("check-placement-confidence: PASS");
}

try {
  main();
} catch (err) {
  console.error("check-placement-confidence: FAIL");
  console.error(err && err.stack ? err.stack : err);
  process.exit(1);
}
