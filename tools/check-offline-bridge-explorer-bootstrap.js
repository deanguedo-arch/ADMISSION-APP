const assert = require("assert");
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const repoRoot = path.resolve(__dirname, "..");
const sourcePath = path.join(repoRoot, "offline_snapshot", "src", "offline_bridge.js");
const source = fs.readFileSync(sourcePath, "utf8");

const delegatedRows = [
  {
    key: "ualberta_education_r1",
    institution: "UAlberta",
    program: "Education (First-Year)",
    credential: "Degree",
    minAvg: 70,
    competitiveGuidance: "Competitive varies by year",
    requirementType:
      "alberta_high_school_courses; notes: 3 admission subjects must be from Groups A or C (UAlberta chart)",
    sourceUrl:
      "https://www.ualberta.ca/en/education/programs/undergraduate-programs/admission-requirements.html",
    datasetDate: "2026-04-16",
    avgTotal: 5,
    englishRequirement: "English 30-1",
    englishRequirementMode: "course",
    englishMin: 50,
    allowedGroups: ["A", "B", "C"],
  },
];

const context = {
  console,
  setTimeout(fn) {
    fn();
    return 1;
  },
  OFFLINE_SNAPSHOT: {
    programsRange: [
      ["Institution", "Program", "Credential_Type", "Status", "Program_URL", "Min_Avg_Final", "Requirement_Type"],
      [
        "UAlberta",
        "Education (First-Year)",
        "Degree",
        "Active",
        "https://www.ualberta.ca/en/education/programs/undergraduate-programs/admission-requirements.html",
        "70",
        "alberta_high_school_courses",
      ],
    ],
    datasetDate: "2026-04-16",
    datasetStamp: "offline_test",
    confidenceStaleDays: 60,
    manualElectiveSlots: 5,
    avgRules: { byKey: {}, byInstitution: {} },
    electiveRuleOverrides: { byKey: {}, byInstitution: {} },
  },
  window: {
    OFFLINE_SNAPSHOT: null,
    RESULTS_HEADER_ROW: [],
    MANUAL_ELECTIVE_SLOTS: undefined,
    listNamedCourseOptions_() {
      return ["English 30-1"];
    },
    listElectiveCourseOptions_() {
      return [];
    },
    listExplorerProgramsForWeb_(programsRange, fallbackDateValue) {
      assert.strictEqual(Array.isArray(programsRange), true, "Expected programsRange to be forwarded");
      assert.strictEqual(fallbackDateValue, "2026-04-16", "Expected dataset date to be forwarded");
      return delegatedRows;
    },
  },
};
context.window.OFFLINE_SNAPSHOT = context.OFFLINE_SNAPSHOT;
vm.createContext(context);
vm.runInContext(source, context);

assert(
  context.window.google &&
    context.window.google.script &&
    context.window.google.script.run &&
    typeof context.window.google.script.run.withSuccessHandler === "function",
  "Expected offline bridge to install google.script.run proxy"
);

let bootstrap = null;
context.window.google.script.run.withSuccessHandler((result) => {
  bootstrap = result;
}).getWebAppBootstrapData({});

assert(bootstrap, "Expected bootstrap response");
assert(Array.isArray(bootstrap.explorerPrograms), "Expected explorerPrograms in bootstrap");
assert.strictEqual(bootstrap.explorerPrograms.length, 1, "Expected one delegated explorer row");
assert.strictEqual(
  bootstrap.explorerPrograms[0].englishRequirement,
  "English 30-1",
  "Expected offline bridge to preserve delegated structured explorer requirements"
);
assert.strictEqual(
  bootstrap.explorerPrograms[0].avgTotal,
  5,
  "Expected offline bridge to preserve delegated Avg_Total"
);
assert.deepStrictEqual(
  Array.from(bootstrap.explorerPrograms[0].allowedGroups || []),
  ["A", "B", "C"],
  "Expected offline bridge to preserve delegated elective groups"
);

console.log("check-offline-bridge-explorer-bootstrap: PASS");
