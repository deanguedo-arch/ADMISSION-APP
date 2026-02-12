/**
 * Admissions Checker Workbook/Admin Setup
 */

const DATASET_RAW_URL_PROPERTY = "DATASET_RAW_URL";
const GITHUB_TOKEN_PROPERTY = "GITHUB_TOKEN";
const SETTINGS_SHEET_NAME = "Settings";
const COURSE_CATALOG_SHEET_NAME = "CourseCatalog";
const PROGRAMS_BACKUP_SHEET_NAME = "Programs_BACKUP";

function setupWorkbookForStaff_(opts) {
  const ss = SpreadsheetApp.getActive();
  ensureSheet_(ss, "Programs");
  const studentSheet = ensureSheet_(ss, "Student");
  ensureSheet_(ss, "Results");
  ensureSheet_(ss, "Eligible");
  ensureSheet_(ss, "Ineligible");
  ensureSheet_(ss, "Uncheckable");
  ensureSheet_(ss, "ElectiveRules");

  const studentHeaders = studentSheet.getRange(1, 1, 1, 2).getValues()[0];
  const hasStudentHeaders =
    String(studentHeaders[0] || "").trim() !== "" || String(studentHeaders[1] || "").trim() !== "";
  if (!hasStudentHeaders) {
    studentSheet.getRange(1, 1, 1, 2).setValues([["Course", "Mark"]]);
  }

  const studentSetupMsg = setupStudentElectiveInputs_({ quiet: true });
  const rulesSetupMsg = setupElectiveRulesTemplate_({ quiet: true });
  const message = `Workbook setup complete. ${studentSetupMsg} ${rulesSetupMsg} Enter marks in Student, then run Check Eligibility.`;
  if (!isQuietSetup_(opts)) notifyStudentSetupComplete_(ss, message);
  return message;
}

function ensureSheet_(ss, name) {
  let sheet = ss.getSheetByName(name);
  if (!sheet) sheet = ss.insertSheet(name);
  return sheet;
}

function isStaffEditableSheet_(name) {
  const t = String(name || "").trim();
  return STAFF_EDITABLE_SHEET_NAMES.indexOf(t) >= 0;
}

function isQuietSetup_(opts) {
  return !!(opts && typeof opts === "object" && opts.quiet === true);
}

function assertAdminRunner_(ss) {
  const owner = ss && ss.getOwner ? ss.getOwner() : null;
  const ownerEmail = owner && owner.getEmail ? String(owner.getEmail() || "").toLowerCase() : "";
  const me = Session.getEffectiveUser();
  const meEmail = me && me.getEmail ? String(me.getEmail() || "").toLowerCase() : "";
  if (ownerEmail && meEmail && ownerEmail !== meEmail) {
    throw new Error(`Admin action blocked. Run this as sheet owner (${ownerEmail}).`);
  }
}

function removeManagedSheetProtection_(sheet) {
  const protections = sheet.getProtections(SpreadsheetApp.ProtectionType.SHEET) || [];
  protections.forEach((p) => {
    const desc = String((p && p.getDescription && p.getDescription()) || "").trim();
    if (desc !== MANAGED_INTERNAL_PROTECTION_DESC) return;
    try {
      p.remove();
    } catch (err) {}
  });
}

function ensureManagedSheetProtection_(sheet, ss) {
  const protections = sheet.getProtections(SpreadsheetApp.ProtectionType.SHEET) || [];
  let protection = null;
  protections.forEach((p) => {
    if (protection) return;
    const desc = String((p && p.getDescription && p.getDescription()) || "").trim();
    if (desc === MANAGED_INTERNAL_PROTECTION_DESC) protection = p;
  });
  if (!protection) {
    protection = sheet.protect();
    protection.setDescription(MANAGED_INTERNAL_PROTECTION_DESC);
  }

  protection.setWarningOnly(false);
  try {
    if (protection.canDomainEdit()) protection.setDomainEdit(false);
  } catch (err) {}

  const allowed = {};
  const owner = ss && ss.getOwner ? ss.getOwner() : null;
  const ownerEmail = owner && owner.getEmail ? String(owner.getEmail() || "").toLowerCase() : "";
  if (ownerEmail) allowed[ownerEmail] = true;
  const me = Session.getEffectiveUser();
  const meEmail = me && me.getEmail ? String(me.getEmail() || "").toLowerCase() : "";
  if (meEmail) allowed[meEmail] = true;

  const editors = protection.getEditors() || [];
  editors.forEach((u) => {
    const email = u && u.getEmail ? String(u.getEmail() || "").toLowerCase() : "";
    if (!email || allowed[email]) return;
    try {
      protection.removeEditor(u);
    } catch (err) {}
  });

  if (meEmail) {
    try {
      protection.addEditor(meEmail);
    } catch (err) {}
  }
}

function applyStaffLockdown_() {
  const ss = SpreadsheetApp.getActive();
  assertAdminRunner_(ss);
  setupWorkbookForStaff_({ quiet: true });

  const studentSheet = ss.getSheetByName("Student");
  if (studentSheet) ss.setActiveSheet(studentSheet);

  let hiddenCount = 0;
  let protectedCount = 0;
  (ss.getSheets() || []).forEach((sheet) => {
    const name = sheet.getName();
    if (isStaffEditableSheet_(name)) {
      if (sheet.isSheetHidden()) sheet.showSheet();
      removeManagedSheetProtection_(sheet);
      return;
    }

    ensureManagedSheetProtection_(sheet, ss);
    protectedCount += 1;
    if (!sheet.isSheetHidden()) {
      sheet.hideSheet();
      hiddenCount += 1;
    }
  });

  notifyStudentSetupComplete_(
    ss,
    `Staff lockdown applied. Protected ${protectedCount} internal tab(s), hid ${hiddenCount} tab(s).`
  );
}

function adminShowAllTabs_() {
  const ss = SpreadsheetApp.getActive();
  assertAdminRunner_(ss);
  let shownCount = 0;
  (ss.getSheets() || []).forEach((sheet) => {
    if (!sheet.isSheetHidden()) return;
    sheet.showSheet();
    shownCount += 1;
  });
  notifyStudentSetupComplete_(ss, `Shown ${shownCount} hidden tab(s).`);
}

function setupStudentElectiveInputs_(opts) {
  const ss = SpreadsheetApp.getActive();
  const studentSheet = ss.getSheetByName("Student");
  if (!studentSheet) throw new Error("Missing Student sheet.");

  const options = listElectiveCourseOptions_();
  if (!options.length) throw new Error("No elective course options are available.");

  const courseValidation = SpreadsheetApp.newDataValidation()
    .requireValueInList(options, true)
    .setAllowInvalid(false)
    .build();
  const groupValidation = SpreadsheetApp.newDataValidation()
    .requireValueInList(["A", "B", "C", "D"], true)
    .setAllowInvalid(false)
    .build();

  const courseRange = studentSheet.getRange(MANUAL_ELECTIVE_START_ROW, MANUAL_ELECTIVE_COL, MANUAL_ELECTIVE_SLOTS, 1);
  const groupRange = studentSheet.getRange(MANUAL_ELECTIVE_START_ROW, MANUAL_ELECTIVE_COL + 1, MANUAL_ELECTIVE_SLOTS, 1);
  const markRange = studentSheet.getRange(MANUAL_ELECTIVE_START_ROW, MANUAL_ELECTIVE_COL + 2, MANUAL_ELECTIVE_SLOTS, 1);

  courseRange.clearDataValidations().clearContent().setDataValidation(courseValidation);
  groupRange.clearDataValidations().clearContent().setDataValidation(groupValidation);
  markRange.clearDataValidations().clearContent();
  studentSheet
    .getRange(1, MANUAL_ELECTIVE_COL, 1, MANUAL_ELECTIVE_WIDTH)
    .setValues([["Elective Course (Dropdown)", "Group Override (Optional)", "Mark"]]);

  const message = `Configured Student elective inputs in D${MANUAL_ELECTIVE_START_ROW}:F${MANUAL_ELECTIVE_START_ROW + MANUAL_ELECTIVE_SLOTS - 1}.`;
  if (!isQuietSetup_(opts)) notifyStudentSetupComplete_(ss, message);
  return message;
}

function setupElectiveRulesTemplate_(opts) {
  const ss = SpreadsheetApp.getActive();
  const sheet = ss.getSheetByName("ElectiveRules") || ss.insertSheet("ElectiveRules");

  sheet.getRange(1, 1, 1, 3).setValues([["Institution", "Program", "Rule_Text"]]);
  const existingRow2 = sheet.getRange(2, 1, 1, 3).getValues()[0];
  const row2HasContent = existingRow2.some((x) => String(x || "").trim() !== "");
  if (!row2HasContent) {
    sheet
      .getRange(2, 1, 1, 3)
      .setValues([["MacEwan", "Bachelor of Arts Undeclared", "Maximum of two Group B subjects"]]);
  }
  sheet.setFrozenRows(1);

  const message =
    "Configured ElectiveRules template (Institution, Program, Rule_Text). Add rows for any program-specific elective caps.";
  if (!isQuietSetup_(opts)) notifyStudentSetupComplete_(ss, message);
  return message;
}

function notifyStudentSetupComplete_(ss, message) {
  try {
    SpreadsheetApp.getUi().alert(message);
    return;
  } catch (err) {}

  try {
    if (ss && ss.toast) {
      ss.toast(message, "Admissions Checker", 8);
      return;
    }
  } catch (err) {}

  Logger.log(message);
}

function adminSyncProgramsFromGitHub_() {
  const ss = SpreadsheetApp.getActive();
  assertAdminRunner_(ss);

  const props = PropertiesService.getScriptProperties();
  const rawUrl = String(props.getProperty(DATASET_RAW_URL_PROPERTY) || "").trim();
  if (!rawUrl) {
    throw new Error(
      `Missing Script Property ${DATASET_RAW_URL_PROPERTY}. Set it to the GitHub raw CSV URL for data/ALBERTA_ADMISSIONS_MASTER_CANONICAL.csv.`
    );
  }

  const token = String(props.getProperty(GITHUB_TOKEN_PROPERTY) || "").trim();
  const headers = { Accept: "text/csv" };
  if (token) headers.Authorization = `Bearer ${token}`;

  const resp = UrlFetchApp.fetch(rawUrl, { muteHttpExceptions: true, headers });
  const code = resp.getResponseCode();
  if (code < 200 || code >= 300) {
    const snippet = String(resp.getContentText() || "").slice(0, 400);
    throw new Error(`GitHub fetch failed (HTTP ${code}). Check ${DATASET_RAW_URL_PROPERTY}. Snippet: ${snippet}`);
  }

  const csvText = String(resp.getContentText() || "");
  const parsed = Utilities.parseCsv(csvText);
  const values = normalizeCsvGrid_(parsed);
  if (!values || values.length < 2) {
    throw new Error("Fetched CSV parsed empty. Confirm the raw URL points directly to a CSV file.");
  }

  const header = values[0] || [];
  const idx = indexHeader_(header);
  requireProgramsColumns_(idx);

  const programsSheet = ss.getSheetByName("Programs") || ss.insertSheet("Programs");
  const backup = backupSheetSnapshot_(ss, programsSheet, PROGRAMS_BACKUP_SHEET_NAME, "Programs");

  programsSheet.clearContents();
  programsSheet.getRange(1, 1, values.length, values[0].length).setValues(values);
  programsSheet.setFrozenRows(1);

  const stampUtc = Utilities.formatDate(new Date(), "Etc/UTC", "yyyy-MM-dd HH:mm:ss'Z'");
  props.setProperty(LAST_PROGRAMS_SYNC_UTC_PROPERTY, stampUtc);

  writeSettingsStamp_(ss, {
    lastProgramsSyncUtc: stampUtc,
    programsRows: Math.max(0, values.length - 1),
    datasetRawUrl: rawUrl,
  });

  notifyStudentSetupComplete_(
    ss,
    `Programs synced from GitHub. Rows: ${Math.max(0, values.length - 1)}. Backup: ${backup.name} (${backup.rows} rows).`
  );
}

function adminInstallNightlyProgramsSync_() {
  const ss = SpreadsheetApp.getActive();
  assertAdminRunner_(ss);

  const handler = "adminSyncProgramsFromGitHub_";
  removeTriggersByHandler_(handler);

  ScriptApp.newTrigger(handler).timeBased().everyDays(1).atHour(2).create();
  notifyStudentSetupComplete_(ss, "Installed nightly Programs sync (daily at ~02:00).");
}

function adminRemoveNightlyProgramsSync_() {
  const ss = SpreadsheetApp.getActive();
  assertAdminRunner_(ss);

  const handler = "adminSyncProgramsFromGitHub_";
  const removed = removeTriggersByHandler_(handler);
  notifyStudentSetupComplete_(ss, `Removed ${removed} nightly Programs sync trigger(s).`);
}

function removeTriggersByHandler_(handlerName) {
  const handler = String(handlerName || "").trim();
  if (!handler) return 0;
  let removed = 0;
  (ScriptApp.getProjectTriggers() || []).forEach((t) => {
    try {
      if (t.getHandlerFunction && t.getHandlerFunction() === handler) {
        ScriptApp.deleteTrigger(t);
        removed += 1;
      }
    } catch (err) {}
  });
  return removed;
}

function adminRebuildCourseCatalog_() {
  const ss = SpreadsheetApp.getActive();
  assertAdminRunner_(ss);
  setupWorkbookForStaff_({ quiet: true });

  const named = listNamedCourseOptions_();
  const electives = listElectiveCourseOptions_();

  const catalog = ss.getSheetByName(COURSE_CATALOG_SHEET_NAME) || ss.insertSheet(COURSE_CATALOG_SHEET_NAME);
  catalog.clearContents();
  catalog.getRange(1, 1, 1, 2).setValues([["Named Courses", "Elective Courses"]]);

  const maxLen = Math.max(named.length, electives.length, 1);
  const grid = [];
  for (let i = 0; i < maxLen; i++) {
    grid.push([named[i] || "", electives[i] || ""]);
  }
  catalog.getRange(2, 1, grid.length, 2).setValues(grid);
  catalog.setFrozenRows(1);

  try {
    if (!catalog.isSheetHidden()) catalog.hideSheet();
  } catch (err) {}
  try {
    ensureManagedSheetProtection_(catalog, ss);
  } catch (err) {}

  const namedRange = catalog.getRange(2, 1, Math.max(1, named.length), 1);
  const electiveRange = catalog.getRange(2, 2, Math.max(1, electives.length), 1);

  const student = ss.getSheetByName("Student");
  if (!student) throw new Error("Missing Student sheet.");

  const namedCourseValidation = SpreadsheetApp.newDataValidation()
    .requireValueInRange(namedRange, true)
    .setAllowInvalid(false)
    .build();
  const electiveCourseValidation = SpreadsheetApp.newDataValidation()
    .requireValueInRange(electiveRange, true)
    .setAllowInvalid(false)
    .build();
  const groupValidation = SpreadsheetApp.newDataValidation()
    .requireValueInList(["A", "B", "C", "D"], true)
    .setAllowInvalid(false)
    .build();

  const namedRows = 80;
  student.getRange(2, 1, namedRows, 1).setDataValidation(namedCourseValidation);
  student.getRange(2, 2, namedRows, 1).setDataValidation(markValidationForCell_("B2"));

  student.getRange(MANUAL_ELECTIVE_START_ROW, MANUAL_ELECTIVE_COL, MANUAL_ELECTIVE_SLOTS, 1).setDataValidation(electiveCourseValidation);
  student.getRange(MANUAL_ELECTIVE_START_ROW, MANUAL_ELECTIVE_COL + 1, MANUAL_ELECTIVE_SLOTS, 1).setDataValidation(groupValidation);
  student.getRange(MANUAL_ELECTIVE_START_ROW, MANUAL_ELECTIVE_COL + 2, MANUAL_ELECTIVE_SLOTS, 1).setDataValidation(markValidationForCell_("F2"));

  notifyStudentSetupComplete_(
    ss,
    `CourseCatalog rebuilt and validations applied (Student named courses A2:B${namedRows + 1}, electives D${MANUAL_ELECTIVE_START_ROW}:F${MANUAL_ELECTIVE_START_ROW + MANUAL_ELECTIVE_SLOTS - 1}).`
  );
}

function markValidationForCell_(a1Ref) {
  const cell = String(a1Ref || "").trim().toUpperCase();
  if (!cell) throw new Error("markValidationForCell_ missing cell reference.");
  const formula = `=OR(ISBLANK(${cell}), AND(ISNUMBER(${cell}), ${cell}>=0, ${cell}<=100))`;
  return SpreadsheetApp.newDataValidation()
    .requireFormulaSatisfied(formula)
    .setAllowInvalid(false)
    .setHelpText("Enter a mark from 0 to 100 (blank allowed).")
    .build();
}

function normalizeCsvGrid_(values) {
  const rows = Array.isArray(values) ? values : [];
  if (!rows.length) return [];
  let maxCols = 0;
  rows.forEach((r) => {
    const cols = Array.isArray(r) ? r.length : 0;
    if (cols > maxCols) maxCols = cols;
  });
  if (maxCols <= 0) return [];
  return rows.map((r) => {
    const row = Array.isArray(r) ? r.slice() : [];
    while (row.length < maxCols) row.push("");
    return row;
  });
}

function backupSheetSnapshot_(ss, sourceSheet, backupSheetName, sourceName) {
  const backupName = String(backupSheetName || "").trim() || "BACKUP";
  const sourceTab =
    String(sourceName || "").trim() ||
    (sourceSheet && sourceSheet.getName ? sourceSheet.getName() : "");

  let backupSheet = ss.getSheetByName(backupName);
  if (!backupSheet) backupSheet = ss.insertSheet(backupName);
  backupSheet.clearContents();

  const existing = sourceSheet.getDataRange().getValues();
  const hasData =
    !!existing &&
    existing.length > 0 &&
    existing.some((row) => row.some((cell) => String(cell === null || cell === undefined ? "" : cell).trim() !== ""));
  const existingRows = hasData ? existing.length : 0;

  const stampUtc = Utilities.formatDate(new Date(), "Etc/UTC", "yyyy-MM-dd HH:mm:ss'Z'");
  backupSheet.getRange(1, 1, 1, 3).setValues([["Meta_Key", "Meta_Value", "Source_Tab"]]);
  backupSheet.getRange(2, 1, 1, 3).setValues([["Backup_UTC", stampUtc, sourceTab]]);
  backupSheet.getRange(3, 1, 1, 3).setValues([["Source_Row_Count", String(existingRows), sourceTab]]);

  if (hasData) {
    backupSheet.getRange(4, 1, existing.length, existing[0].length).setValues(existing);
    backupSheet.setFrozenRows(4);
  } else {
    backupSheet.setFrozenRows(3);
  }

  try {
    ensureManagedSheetProtection_(backupSheet, ss);
  } catch (err) {}

  return { name: backupName, rows: existingRows };
}

function writeSettingsStamp_(ss, info) {
  const sheet = ss.getSheetByName(SETTINGS_SHEET_NAME) || ss.insertSheet(SETTINGS_SHEET_NAME);

  const header = sheet.getRange(1, 1, 1, 2).getValues()[0];
  const hasHeader = String(header[0] || "").trim() || String(header[1] || "").trim();
  if (!hasHeader) sheet.getRange(1, 1, 1, 2).setValues([["Meta_Key", "Meta_Value"]]);

  const last = Math.max(0, sheet.getLastRow() || 0);
  if (last > 1) {
    sheet.getRange(2, 1, last - 1, 2).clearContent();
  }

  const rows = [];
  if (info && typeof info === "object") {
    if (info.lastProgramsSyncUtc) rows.push(["LAST_PROGRAMS_SYNC_UTC", String(info.lastProgramsSyncUtc)]);
    if (isFinite(toNumber_(info.programsRows))) {
      rows.push(["PROGRAMS_ROW_COUNT", String(Math.round(toNumber_(info.programsRows)))]);
    }
    if (info.datasetRawUrl) rows.push(["DATASET_RAW_URL", String(info.datasetRawUrl)]);
  }

  if (rows.length) {
    sheet.getRange(2, 1, rows.length, 2).setValues(rows);
  }

  sheet.setFrozenRows(1);
  try {
    ensureManagedSheetProtection_(sheet, ss);
  } catch (err) {}
}

