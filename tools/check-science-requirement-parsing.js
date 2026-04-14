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
  "apps_script/EligibilitySubjects.gs",
].forEach((relativePath) => {
  const fullPath = path.join(repoRoot, relativePath);
  const code = fs.readFileSync(fullPath, "utf8");
  vm.runInContext(code, context, { filename: relativePath });
});

function makeScienceRow(fields) {
  const header = [
    "Science_Req",
    "Science_Min",
    "Bio_30_Req",
    "Chem_30_Req",
    "Phys_30_Req",
    "Sci_30_Req",
  ];
  const idx = context.indexHeader_(header);
  const row = header.map((h) => (fields && fields[h] !== undefined ? fields[h] : ""));
  return { row, idx };
}

function evaluateScience(fields, courses) {
  const { row, idx } = makeScienceRow(fields);
  const courseMap = context.buildCourseMap_(Object.entries(courses || {}));
  const scienceReq = context.buildScienceReq_(row, idx);
  const scienceEval = context.evalScience_(courseMap, scienceReq, Number(fields.Science_Min || NaN));
  const reasons = [];
  context.appendEval_(scienceEval, "Science", reasons, [], []);
  return { scienceReq, scienceEval, reasons };
}

function main() {
  const parsed = context.parseScienceRequirementText_("Biology 30 or Chemistry 30 or Physics 30");
  assert.deepStrictEqual(
    Array.from(parsed.courses || []),
    ["Biology 30", "Chemistry 30", "Physics 30"],
    "science OR lists should split into separate alternatives"
  );

  const psychology = evaluateScience(
    {
      Science_Req: "Biology 30 or Chemistry 30 or Physics 30",
      Science_Min: "50",
      Bio_30_Req: "Yes",
      Chem_30_Req: "Yes",
      Phys_30_Req: "Yes",
    },
    { "Biology 30": 95 }
  );
  assert.deepStrictEqual(
    psychology.reasons,
    [],
    "one listed science alternative should satisfy Biology/Chemistry/Physics rows"
  );

  const educationalAssistant = evaluateScience(
    {
      Science_Req: "Biology 30 or Chemistry 30 or Physics 30 or Science 30",
      Science_Min: "50",
      Bio_30_Req: "Yes",
      Chem_30_Req: "Yes",
      Phys_30_Req: "Yes",
      Sci_30_Req: "Yes",
    },
    { "Physics 30": 95 }
  );
  assert.deepStrictEqual(
    educationalAssistant.reasons,
    [],
    "one listed science alternative should satisfy rows that include Science 30 as an option"
  );

  const nursing = evaluateScience(
    {
      Science_Req: "Chemistry 30 or Science 30",
      Science_Min: "50",
      Bio_30_Req: "Yes",
    },
    { "Biology 30": 95 }
  );
  assert.match(
    nursing.reasons.join(" | "),
    /Chemistry 30 OR Science 30/,
    "extra science flags not present in Science_Req should remain required alongside the alternatives"
  );

  const nursingComplete = evaluateScience(
    {
      Science_Req: "Chemistry 30 or Science 30",
      Science_Min: "50",
      Bio_30_Req: "Yes",
    },
    { "Biology 30": 95, "Chemistry 30": 95 }
  );
  assert.deepStrictEqual(
    nursingComplete.reasons,
    [],
    "required science flag plus one listed alternative should satisfy combined science rules"
  );

  console.log("check-science-requirement-parsing: PASS");
}

try {
  main();
} catch (err) {
  console.error("check-science-requirement-parsing: FAIL");
  console.error(err && err.stack ? err.stack : err);
  process.exit(1);
}
