const assert = require("assert");
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const repoRoot = path.resolve(__dirname, "..");
const sourcePath = path.join(repoRoot, "apps_script", "EligibilityProgramsData.gs");
const source = fs.readFileSync(sourcePath, "utf8");

const context = {
  console,
  Date,
  normalizeHttpUrlForOutput_(value) {
    return String(value || "").trim();
  },
  unique_(values) {
    return Array.from(new Set(Array.isArray(values) ? values : []));
  },
};
vm.createContext(context);
vm.runInContext(source, context);

assert.strictEqual(typeof context.listExplorerProgramsForWeb_, "function", "Missing listExplorerProgramsForWeb_");

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
  "Science_Req",
  "Science_Min",
  "Elective_Need",
  "Elective_Groups",
  "Requirement_Type",
];

const row = [
  "UAlberta",
  "Education (First-Year)",
  "Degree",
  "Active",
  "https://www.ualberta.ca/en/education/programs/undergraduate-programs/admission-requirements.html",
  "70",
  "Competitive varies by year",
  "5",
  "English 30-1",
  "course",
  "50",
  "",
  "",
  "",
  "",
  "",
  "Four",
  "Groups A, B, or C",
  "alberta_high_school_courses; notes: 3 admission subjects must be from Groups A or C (UAlberta chart); 1 more from Groups A/B/C (some substitutions may apply)",
];

const rows = context.listExplorerProgramsForWeb_([header, row], "2026-04-16T00:00:00Z");
assert.strictEqual(rows.length, 1, "Expected one explorer row");

const education = rows[0];
assert.strictEqual(education.program, "Education (First-Year)");
assert.strictEqual(education.minAvg, 70);
assert.strictEqual(education.avgTotal, 5, "Expected explorer row to carry Avg_Total");
assert.strictEqual(education.englishRequirement, "English 30-1", "Expected explorer row to carry English requirement");
assert.strictEqual(education.englishRequirementMode, "course", "Expected explorer row to carry English requirement mode");
assert.strictEqual(education.englishMin, 50, "Expected explorer row to carry English minimum");
assert.deepStrictEqual(
  Array.from(education.allowedGroups || []),
  ["A", "B", "C"],
  "Expected explorer row to carry allowed elective groups"
);

console.log("check-explorer-program-structure: PASS");
