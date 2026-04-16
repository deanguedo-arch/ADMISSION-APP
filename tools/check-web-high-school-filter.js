const assert = require("assert");
const crypto = require("crypto");
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
  Utilities: {
    DigestAlgorithm: { SHA_256: "sha256" },
    computeDigest(algorithm, value) {
      const algo = algorithm === "sha256" ? "sha256" : String(algorithm || "sha256").toLowerCase();
      return Array.from(crypto.createHash(algo).update(String(value || ""), "utf8").digest());
    },
    base64EncodeWebSafe(bytes) {
      return Buffer.from(Uint8Array.from(bytes || []))
        .toString("base64")
        .replace(/\+/g, "-")
        .replace(/\//g, "_");
    },
  },
});

[
  "apps_script/Code.gs",
  "apps_script/EligibilityShared.gs",
  "apps_script/EligibilityProgramsData.gs",
  "apps_script/EligibilitySubjects.gs",
  "apps_script/EligibilityElectives.gs",
  "apps_script/EligibilityEngine.gs",
].forEach((relativePath) => {
  const fullPath = path.join(repoRoot, relativePath);
  const code = fs.readFileSync(fullPath, "utf8");
  vm.runInContext(code, context, { filename: relativePath });
});

assert.strictEqual(typeof context.listExplorerProgramsForWeb_, "function", "Missing listExplorerProgramsForWeb_");
assert.strictEqual(typeof context.evaluateProgramsForStudent_, "function", "Missing evaluateProgramsForStudent_");

const header = [
  "Institution",
  "Program",
  "Credential_Type",
  "Status",
  "Program_URL",
  "Min_Avg_Final",
  "Competitive_Final",
  "Avg_Total",
  "English_Req",
  "English_Requirement_Mode",
  "English_Min",
  "Math_Req",
  "Math_Requirement_Mode",
  "Math_Min",
  "Social_Req",
  "Social_Min",
  "Science_Req",
  "Science_Min",
  "Elective_Qty",
  "Elective_Pool",
  "Requirement_Type",
  "HS_Diploma_Req",
  "Math_Assessment_Flag",
  "Display_For_High_School",
  "dataset_date",
];

const hiddenRow = [
  "MacEwan",
  "Behaviour Analysis",
  "Other",
  "Active",
  "https://www.macewan.ca/academics/programs/behaviour-analysis/admissions/requirements/index.html",
  "65",
  "",
  "",
  "English language proficiency",
  "elp",
  "",
  "",
  "",
  "",
  "",
  "",
  "",
  "",
  "",
  "",
  "regular_admission; notes: regular admission",
  "Yes",
  "",
  "No",
  "2026-04-16",
];

const visibleRow = [
  "UAlberta",
  "Education (First-Year)",
  "Degree",
  "Active",
  "https://www.ualberta.ca/en/education/programs/undergraduate-programs/admission-requirements.html",
  "70",
  "",
  "5",
  "English 30-1",
  "course",
  "50",
  "",
  "",
  "",
  "",
  "",
  "",
  "",
  "4",
  "A,B,C",
  "alberta_high_school_courses; notes: 3 admission subjects must be from Groups A or C (UAlberta chart); 1 more from Groups A/B/C (some substitutions may apply)",
  "Yes",
  "No",
  "Yes",
  "2026-04-16",
];

const programsRange = [header, hiddenRow, visibleRow];

const explorerRows = context.listExplorerProgramsForWeb_(programsRange, "2026-04-16T00:00:00Z");
assert.strictEqual(explorerRows.length, 1, "Explorer should default-hide non-high-school rows");
assert.strictEqual(explorerRows[0].program, "Education (First-Year)");

const courseMap = context.buildCourseMap_([
  ["English 30-1", 95],
  ["Math 30-1", 95],
  ["Biology 30", 95],
  ["Chemistry 30", 95],
  ["Physics 30", 95],
]);

const evaluation = context.evaluateProgramsForStudent_({
  programsRange,
  courseMap,
  manualElectives: [],
  avgRules: { byKey: {}, byInstitution: {} },
  electiveRuleOverrides: { byKey: {}, byInstitution: {} },
  datasetDate: "2026-04-16T00:00:00Z",
  staleDaysCap: 60,
});

assert(evaluation && Array.isArray(evaluation.finalOut), "Expected evaluation payload");
assert.strictEqual(evaluation.finalOut.length - 1, 1, "Eligibility results should skip non-high-school rows");
assert.strictEqual(String(evaluation.finalOut[1][1] || ""), "Education (First-Year)");

console.log("check-web-high-school-filter: PASS");
