/**
 * Alberta Admissions Checker (MVP)
 *
 * Expected tabs:
 * - Programs: canonical CSV imported (headers in row 1)
 * - Student:
 *   - Rows 3+ (A:B): Course / Mark (for named courses like English 30-1, Math 30-2, Biology 30, etc.)
 *   - Rows 2-6 (D:F): Optional manual elective overrides (dropdown course) / Group override (A/B/C/D) / Mark
 * - Results: output written here
 */

/**
 * Admissions Checker App Shell
 *
 * Keep this file thin: entrypoints + constants + top-level orchestration only.
 */

function onOpen() {
  // onOpen can be invoked from contexts where Spreadsheet UI is unavailable (for example,
  // running onOpen directly from the Apps Script editor). In that case, skip menu creation.
  try {
    SpreadsheetApp.getUi()
      .createMenu("Admissions Checker")
      .addItem("Check Eligibility", "runEligibility_")
      .addItem("One-Time Setup (Recommended)", "setupWorkbookForStaff_")
      .addItem("Setup Student Elective Dropdowns", "setupStudentElectiveInputs_")
      .addItem("Setup ElectiveRules Template", "setupElectiveRulesTemplate_")
      .addSeparator()
      .addItem("Admin: Apply Staff Lockdown", "applyStaffLockdown_")
      .addItem("Admin: Show All Tabs", "adminShowAllTabs_")
      .addToUi();
  } catch (err) {
    Logger.log("onOpen skipped: Spreadsheet UI is not available in this execution context.");
  }
}

const MANUAL_ELECTIVE_START_ROW = 2;
const MANUAL_ELECTIVE_SLOTS = 5;
const MANUAL_ELECTIVE_COL = 4; // D
const MANUAL_GROUP_COL = 5; // E
const MANUAL_ELECTIVE_WIDTH = 3; // D:F
const STAFF_EDITABLE_SHEET_NAMES = ["Student", "Eligible", "Ineligible", "Uncheckable", "Results"];
const MANAGED_INTERNAL_PROTECTION_DESC = "Admissions Checker: managed internal sheet protection";
const ADMISSIONS_SHEET_ID_PROPERTY = "ADMISSIONS_SHEET_ID";
const DEFAULT_ADMISSIONS_SHEET_ID = "1QSp9ufon8isEuaBjqoH-8xh5F9vjG94PSsBoZgTPAvU";
const WEBAPP_ALLOWED_DOMAIN_SUFFIX = "@eips.ca";
const WEBAPP_ALLOWED_DOMAIN = "eips.ca";
const WEBAPP_GOOGLE_CLIENT_ID_PROPERTY = "WEBAPP_GOOGLE_CLIENT_ID";
const WEBAPP_ALLOWED_GOOGLE_CLIENT_IDS_PROPERTY = "WEBAPP_ALLOWED_GOOGLE_CLIENT_IDS";
const WEBAPP_GOOGLE_TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo?id_token=";
const WEBAPP_ID_TOKEN_CACHE_SECONDS = 300;
const WEBAPP_MAX_ID_TOKEN_LENGTH = 4096;
const WEBAPP_RATE_LIMIT_MIN_INTERVAL_MS = 2000;
const WEBAPP_RATE_LIMIT_WINDOW_SECONDS = 60;
const WEBAPP_RATE_LIMIT_MAX_PER_WINDOW = 30;
const RESULTS_HEADER_ROW = [
  "Institution",
  "Program",
  "Credential",
  "Min Avg",
  "Student Avg",
  "Avg Courses",
  "Avg Used",
  "Competitive Guidance",
  "Missing",
  "Notes",
];

function onEdit(e) {
  autoFillManualElectiveGroupsFromEdit_(e);
}

function autoFillManualElectiveGroupsFromEdit_(e) {
  if (!e || !e.range) return;
  const range = e.range;
  const sheet = range.getSheet();
  if (!sheet || sheet.getName() !== "Student") return;

  const editRowStart = range.getRow();
  const editRowEnd = editRowStart + range.getNumRows() - 1;
  const editColStart = range.getColumn();
  const editColEnd = editColStart + range.getNumColumns() - 1;

  const manualRowStart = MANUAL_ELECTIVE_START_ROW;
  const manualRowEnd = MANUAL_ELECTIVE_START_ROW + MANUAL_ELECTIVE_SLOTS - 1;
  const touchesCourseCol = editColStart <= MANUAL_ELECTIVE_COL && editColEnd >= MANUAL_ELECTIVE_COL;

  if (!touchesCourseCol) return;

  const rowStart = Math.max(editRowStart, manualRowStart);
  const rowEnd = Math.min(editRowEnd, manualRowEnd);
  if (rowEnd < rowStart) return;

  for (let row = rowStart; row <= rowEnd; row++) {
    autoFillManualElectiveGroupRow_(sheet, row);
  }
}

function autoFillManualElectiveGroupRow_(sheet, row) {
  const courseCell = sheet.getRange(row, MANUAL_ELECTIVE_COL);
  const groupCell = sheet.getRange(row, MANUAL_GROUP_COL);
  const courseLabel = String(courseCell.getValue() || "").trim();

  if (!courseLabel) {
    groupCell.clearContent();
    groupCell.clearNote();
    return;
  }

  const key = normalizeCourseKey_(courseLabel);
  const groups = unique_(
    (electiveGroupsForCourseKey_(key) || [])
      .map((g) => String(g || "").trim().toUpperCase())
      .filter((g) => ["A", "B", "C", "D"].includes(g))
  );

  if (!groups.length) {
    groupCell.clearContent();
    groupCell.setNote("Could not infer group from this course. Enter A/B/C/D manually if needed.");
    return;
  }

  if (groups.length === 1) {
    groupCell.setValue(groups[0]);
    groupCell.setNote("Auto-filled from selected course. You can override manually.");
    return;
  }

  groupCell.clearContent();
  groupCell.setNote(
    `This course maps to multiple groups (${groups.join("/")}). Leave blank to allow all mapped groups, or set one override.`
  );
}

function runEligibility_() {
  const ss = getAdmissionsSpreadsheet_();
  const programsSheet = ss.getSheetByName("Programs");
  const studentSheet = ss.getSheetByName("Student");
  const resultsSheet = ss.getSheetByName("Results");
  const eligibleSheet = ss.getSheetByName("Eligible") || ss.insertSheet("Eligible");
  const ineligibleSheet = ss.getSheetByName("Ineligible") || ss.insertSheet("Ineligible");
  const uncheckableSheet = ss.getSheetByName("Uncheckable") || ss.insertSheet("Uncheckable");
  const avgRules = readAvgRules_(ss);
  const electiveRuleOverrides = readElectiveRuleOverrides_(ss);

  if (!programsSheet || !studentSheet || !resultsSheet) {
    throw new Error("Missing one of: Programs, Student, Results sheets");
  }

  const programsRange = programsSheet.getDataRange().getValues();
  // Be forgiving: read from row 2 down (row 1 is usually headers).
  const studentRows = studentSheet.getRange(2, 1, Math.max(0, studentSheet.getLastRow() - 1), 2).getValues();
  const courseMap = buildCourseMap_(studentRows);
  const electivesRows = studentSheet
    .getRange(MANUAL_ELECTIVE_START_ROW, MANUAL_ELECTIVE_COL, MANUAL_ELECTIVE_SLOTS, MANUAL_ELECTIVE_WIDTH)
    .getValues();
  const manualElectives = buildElectives_(electivesRows, { source: "manual", rowOffset: MANUAL_ELECTIVE_START_ROW });

  if (Object.keys(courseMap).length === 0 && manualElectives.length === 0) {
    const manualRange = `D${MANUAL_ELECTIVE_START_ROW}:F${MANUAL_ELECTIVE_START_ROW + MANUAL_ELECTIVE_SLOTS - 1}`;
    throw new Error(`No student data found. Enter Course+Mark in Student!A2:B and/or manual overrides in Student!${manualRange}.`);
  }

  const evaluation = evaluateProgramsForStudent_({
    programsRange,
    courseMap,
    manualElectives,
    avgRules,
    electiveRuleOverrides,
  });

  writeResultRowsToSheet_(resultsSheet, evaluation.finalOut);
  writeResultRowsToSheet_(eligibleSheet, evaluation.eligibleRows);
  writeResultRowsToSheet_(ineligibleSheet, evaluation.ineligibleRows);
  writeResultRowsToSheet_(uncheckableSheet, evaluation.uncheckableRows);
}

function doGet(e) {
  return HtmlService.createHtmlOutput(renderWebAppHtml_())
    .setTitle("Next Step Admissions Checker")
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL);
}

function getWebAppBootstrapData(authPayload) {
  const clientConfig = getWebAppClientConfig_();
  const auth = sanitizeWebAuthPayload_(authPayload);

  if (!auth.idToken) {
    return {
      generatedAt: new Date().toISOString(),
      requiresAuth: true,
      auth: {
        googleClientId: clientConfig.googleClientId,
        allowedDomainSuffix: WEBAPP_ALLOWED_DOMAIN_SUFFIX,
      },
    };
  }

  const identity = assertAuthorizedWebUser_(auth);
  assertWebRateLimit_(identity, "bootstrap");

  return {
    generatedAt: new Date().toISOString(),
    requiresAuth: false,
    auth: {
      email: identity.email || "",
      googleClientId: clientConfig.googleClientId,
      allowedDomainSuffix: WEBAPP_ALLOWED_DOMAIN_SUFFIX,
    },
    namedCourseOptions: listNamedCourseOptions_(),
    electiveCourseOptions: listElectiveCourseOptions_(),
    manualElectiveSlots: MANUAL_ELECTIVE_SLOTS,
    groups: ["A", "B", "C", "D"],
  };
}

function runWebEligibility(payload) {
  const request = sanitizeWebPayload_(payload);
  const identity = assertAuthorizedWebUser_(request.auth);
  assertWebRateLimit_(identity, "run");

  const ss = getAdmissionsSpreadsheet_();
  const programsSheet = ss.getSheetByName("Programs");
  if (!programsSheet) {
    throw new Error("Admissions data is unavailable right now. Please contact support to check the Programs sheet.");
  }

  const programsRange = programsSheet.getDataRange().getValues();
  if (!programsRange || programsRange.length < 2) {
    throw new Error("Admissions data is empty. Refresh the Programs tab, then try again.");
  }

  const avgRules = readAvgRules_(ss);
  const electiveRuleOverrides = readElectiveRuleOverrides_(ss);
  const namedRows = sanitizeWebNamedCourses_(request.namedCourses);
  const courseMap = buildCourseMap_(namedRows);
  const manualRows = sanitizeWebManualElectives_(request.manualElectives);
  const manualElectives = buildElectives_(manualRows, { source: "manual-web", rowOffset: 1 });

  const evaluation = evaluateProgramsForStudent_({
    programsRange,
    courseMap,
    manualElectives,
    avgRules,
    electiveRuleOverrides,
  });

  const generatedAt = new Date().toISOString();

  return {
    generatedAt,
    headers: RESULTS_HEADER_ROW.slice(),
    meta: {
      generatedAt,
      datasetRows: Math.max(0, programsRange.length - 1),
      activeProgramsEvaluated: Math.max(0, (evaluation.rowKeysByView && evaluation.rowKeysByView.all || []).length),
      rowKeyVersion: "v1",
    },
    summary: {
      totalPrograms: Math.max(0, evaluation.finalOut.length - 1),
      eligible: Math.max(0, evaluation.eligibleRows.length - 1),
      missing: Math.max(0, evaluation.ineligibleRows.length - 1),
      uncheckable: Math.max(0, evaluation.uncheckableRows.length - 1),
    },
    rowKeysByView: {
      all: ((evaluation.rowKeysByView && evaluation.rowKeysByView.all) || []).slice(),
      eligible: ((evaluation.rowKeysByView && evaluation.rowKeysByView.eligible) || []).slice(),
      ineligible: ((evaluation.rowKeysByView && evaluation.rowKeysByView.ineligible) || []).slice(),
      uncheckable: ((evaluation.rowKeysByView && evaluation.rowKeysByView.uncheckable) || []).slice(),
    },
    detailsByKey: copyWebDetailsByKey_(evaluation.detailsByKey || {}),
    results: {
      all: evaluation.finalOut.slice(1),
      eligible: evaluation.eligibleRows.slice(1),
      ineligible: evaluation.ineligibleRows.slice(1),
      uncheckable: evaluation.uncheckableRows.slice(1),
    },
  };
}

function getAdmissionsSpreadsheet_() {
  try {
    const active = SpreadsheetApp.getActive();
    if (active) return active;
  } catch (err) {}

  const configuredId = String(
    PropertiesService.getScriptProperties().getProperty(ADMISSIONS_SHEET_ID_PROPERTY) || ""
  ).trim();
  const sheetId = configuredId || DEFAULT_ADMISSIONS_SHEET_ID;
  if (!sheetId) {
    throw new Error(
      "Admissions sheet ID is not configured. Set Script Property ADMISSIONS_SHEET_ID or bind this script to the sheet."
    );
  }
  return SpreadsheetApp.openById(sheetId);
}

