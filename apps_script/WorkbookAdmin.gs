/**
 * Admissions Checker Workbook/Admin Setup
 */

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

