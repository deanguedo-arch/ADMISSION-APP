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
    const ui = SpreadsheetApp.getUi();
    const menu = ui
      .createMenu("Admissions Checker")
      .addItem("Check Eligibility", "runEligibility_")
      .addItem("One-Time Setup (Recommended)", "setupWorkbookForStaff_")
      .addItem("Setup Student Elective Dropdowns", "setupStudentElectiveInputs_")
      .addItem("Setup ElectiveRules Template", "setupElectiveRulesTemplate_")
      .addSeparator();

    try {
      menu.addSubMenu(
        ui
          .createMenu("Admissions Admin")
          .addItem("Sync Programs from GitHub", "adminSyncProgramsFromGitHub_")
          .addItem("Install Nightly Programs Sync", "adminInstallNightlyProgramsSync_")
          .addItem("Remove Nightly Programs Sync", "adminRemoveNightlyProgramsSync_")
          .addSeparator()
          .addItem("Rebuild CourseCatalog + Validations", "adminRebuildCourseCatalog_")
      );
    } catch (submenuErr) {
      menu
        .addItem("Admin: Sync Programs from GitHub", "adminSyncProgramsFromGitHub_")
        .addItem("Admin: Install Nightly Programs Sync", "adminInstallNightlyProgramsSync_")
        .addItem("Admin: Remove Nightly Programs Sync", "adminRemoveNightlyProgramsSync_")
        .addItem("Admin: Rebuild CourseCatalog + Validations", "adminRebuildCourseCatalog_");
    }

    menu
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
const WEBAPP_DEV_OPEN_ACCESS_PROPERTY = "WEBAPP_DEV_OPEN_ACCESS";
const WEBAPP_GOOGLE_CLIENT_ID_PROPERTY = "WEBAPP_GOOGLE_CLIENT_ID";
const WEBAPP_ALLOWED_GOOGLE_CLIENT_IDS_PROPERTY = "WEBAPP_ALLOWED_GOOGLE_CLIENT_IDS";
const WEBAPP_GOOGLE_TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo?id_token=";
const WEBAPP_ID_TOKEN_CACHE_SECONDS = 300;
const WEBAPP_MAX_ID_TOKEN_LENGTH = 4096;
const WEBAPP_RATE_LIMIT_MIN_INTERVAL_MS = 2000;
const WEBAPP_RATE_LIMIT_WINDOW_SECONDS = 60;
const WEBAPP_RATE_LIMIT_MAX_PER_WINDOW = 30;
const WEBAPP_RESULT_CACHE_SECONDS = 180;
const WEBAPP_RESULT_CACHE_MAX_CHARS = 95000;
const WEBAPP_DATASET_STAMP_VERSION = "v1";
const WEBAPP_AUDIT_SHEET_NAME = "WebAudit";
const WEBAPP_AUDIT_MAX_DATA_ROWS = 2000;
const LAST_PROGRAMS_SYNC_UTC_PROPERTY = "LAST_PROGRAMS_SYNC_UTC";
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
  return HtmlService.createTemplateFromFile("WebApp")
    .evaluate()
    .setTitle("Next Step Admissions Checker")
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL);
}

function includeHtml_(name) {
  const file = String(name || "").trim();
  if (!file) throw new Error("Web app include name is empty.");
  return HtmlService.createHtmlOutputFromFile(file).getContent();
}

function getWebAppBootstrapData(authPayload) {
  const clientConfig = getWebAppClientConfig_();
  const auth = sanitizeWebAuthPayload_(authPayload);
  let identity = null;
  try {
    // Allow session/domain auth when GIS token is unavailable.
    identity = assertAuthorizedWebUser_(auth);
    assertWebRateLimit_(identity, "bootstrap");
  } catch (err) {
    return {
      generatedAt: new Date().toISOString(),
      requiresAuth: true,
      auth: {
        googleClientId: clientConfig.googleClientId,
        allowedDomainSuffix: WEBAPP_ALLOWED_DOMAIN_SUFFIX,
        message: sanitizeWebMessage_(err && err.message ? err.message : "Sign in with your school account and retry."),
      },
    };
  }

  return {
    generatedAt: new Date().toISOString(),
    requiresAuth: false,
    auth: {
      email: identity.email || "",
      googleClientId: clientConfig.googleClientId,
      allowedDomainSuffix: WEBAPP_ALLOWED_DOMAIN_SUFFIX,
    },
    dataset: {
      lastProgramsSyncUtc: String(
        PropertiesService.getScriptProperties().getProperty(LAST_PROGRAMS_SYNC_UTC_PROPERTY) || ""
      ).trim(),
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
  const digestToken_ = (value, prefix, length) => {
    const src = String(value || "");
    const digest = Utilities.base64EncodeWebSafe(
      Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, src)
    )
      .replace(/=+$/g, "")
      .toLowerCase();
    const size = Math.max(8, Number(length) || 20);
    return `${prefix}${digest.slice(0, size)}`;
  };
  const datasetStamp = digestToken_(
    JSON.stringify({
      programsRange,
      avgRules,
      electiveRuleOverrides,
    }),
    `${WEBAPP_DATASET_STAMP_VERSION}_`,
    24
  );
  const requestStamp = digestToken_(
    JSON.stringify({
      namedRows,
      manualRows,
    }),
    "r_",
    24
  );
  const cacheKey = `WEBAPP_RUN_${datasetStamp}_${requestStamp}`;
  const cache = CacheService.getScriptCache();
  const decodeCachePayload_ = (raw) => {
    if (!raw) return null;
    const outer = JSON.parse(String(raw || "{}"));
    if (!outer || typeof outer !== "object") return null;
    if (outer.encoding === "json") {
      return JSON.parse(String(outer.payload || "{}"));
    }
    if (outer.encoding === "gzip-base64") {
      const bytes = Utilities.base64DecodeWebSafe(String(outer.payload || ""));
      const json = Utilities.ungzip(Utilities.newBlob(bytes)).getDataAsString("utf-8");
      return JSON.parse(String(json || "{}"));
    }
    return null;
  };
  const encodeCachePayload_ = (obj) => {
    const json = JSON.stringify(obj || {});
    if (!json) return "";
    const plain = JSON.stringify({ encoding: "json", payload: json });
    if (plain.length <= WEBAPP_RESULT_CACHE_MAX_CHARS) {
      return plain;
    }
    const zipped = Utilities.gzip(Utilities.newBlob(json, "application/json", "web-result"));
    const b64 = Utilities.base64EncodeWebSafe(zipped.getBytes());
    if (!b64) return "";
    const packed = JSON.stringify({ encoding: "gzip-base64", payload: b64 });
    return packed.length <= WEBAPP_RESULT_CACHE_MAX_CHARS ? packed : "";
  };
  const appendAuditEntry_ = (opts) => {
    try {
      const payloadObj = opts && typeof opts === "object" ? opts : {};
      const summary = payloadObj.summary && typeof payloadObj.summary === "object" ? payloadObj.summary : {};
      const identityRaw = String(
        (payloadObj.identity && (payloadObj.identity.key || payloadObj.identity.email || payloadObj.identity.tempKey)) ||
          "unknown"
      )
        .trim()
        .toLowerCase();
      const identityKey = digestToken_(identityRaw || "unknown", "sha256:", 24);
      const sheet = ss.getSheetByName(WEBAPP_AUDIT_SHEET_NAME) || ss.insertSheet(WEBAPP_AUDIT_SHEET_NAME);
      const header = [
        "Timestamp_UTC",
        "Identity_Key",
        "Total_Programs",
        "Eligible",
        "Missing",
        "Uncheckable",
        "Cache_Hit",
        "Dataset_Stamp",
      ];

      if (sheet.getLastRow() < 1) {
        sheet.getRange(1, 1, 1, header.length).setValues([header]);
        sheet.setFrozenRows(1);
      }

      sheet.appendRow([
        new Date().toISOString(),
        identityKey,
        Math.max(0, Number(summary.totalPrograms || 0)),
        Math.max(0, Number(summary.eligible || 0)),
        Math.max(0, Number(summary.missing || 0)),
        Math.max(0, Number(summary.uncheckable || 0)),
        payloadObj.cacheHit ? "yes" : "no",
        String(payloadObj.datasetStamp || ""),
      ]);

      const dataRows = Math.max(0, sheet.getLastRow() - 1);
      if (dataRows > WEBAPP_AUDIT_MAX_DATA_ROWS) {
        sheet.deleteRows(2, dataRows - WEBAPP_AUDIT_MAX_DATA_ROWS);
      }
    } catch (err) {
      Logger.log(`Web audit entry skipped: ${String(err && err.message ? err.message : err)}`);
    }
  };

  const cachedRaw = cache.get(cacheKey);
  if (cachedRaw) {
    try {
      const cached = decodeCachePayload_(cachedRaw);
      if (cached && typeof cached === "object") {
        const cachedMeta = cached.meta && typeof cached.meta === "object" ? cached.meta : {};
        const cachedRowKeys = cached.rowKeysByView && typeof cached.rowKeysByView === "object" ? cached.rowKeysByView : {};
          const responseFromCache = {
            generatedAt: String(cached.generatedAt || new Date().toISOString()),
            headers: Array.isArray(cached.headers) ? cached.headers.slice() : RESULTS_HEADER_ROW.slice(),
            meta: Object.assign({}, cachedMeta, {
              datasetRows: Math.max(0, programsRange.length - 1),
              activeProgramsEvaluated: Math.max(0, ((cachedRowKeys.all && cachedRowKeys.all.length) || 0)),
              rowKeyVersion: String(cachedMeta.rowKeyVersion || "v1"),
              datasetStamp,
              datasetStampVersion: WEBAPP_DATASET_STAMP_VERSION,
              cacheHit: true,
              lastProgramsSyncUtc: String(
                PropertiesService.getScriptProperties().getProperty(LAST_PROGRAMS_SYNC_UTC_PROPERTY) || ""
              ).trim(),
            }),
            summary: Object.assign({}, cached.summary || {}),
            rowKeysByView: {
            all: Array.isArray(cachedRowKeys.all) ? cachedRowKeys.all.slice() : [],
            eligible: Array.isArray(cachedRowKeys.eligible) ? cachedRowKeys.eligible.slice() : [],
            ineligible: Array.isArray(cachedRowKeys.ineligible) ? cachedRowKeys.ineligible.slice() : [],
            uncheckable: Array.isArray(cachedRowKeys.uncheckable) ? cachedRowKeys.uncheckable.slice() : [],
          },
          detailsByKey: copyWebDetailsByKey_(cached.detailsByKey || {}),
          results: {
            all: Array.isArray(cached.results && cached.results.all) ? cached.results.all.slice() : [],
            eligible: Array.isArray(cached.results && cached.results.eligible) ? cached.results.eligible.slice() : [],
            ineligible: Array.isArray(cached.results && cached.results.ineligible) ? cached.results.ineligible.slice() : [],
            uncheckable: Array.isArray(cached.results && cached.results.uncheckable)
              ? cached.results.uncheckable.slice()
              : [],
          },
        };
        appendAuditEntry_({
          identity,
          summary: responseFromCache.summary,
          cacheHit: true,
          datasetStamp,
        });
        return responseFromCache;
      }
    } catch (err) {
      Logger.log(`Web result cache parse skipped: ${String(err && err.message ? err.message : err)}`);
    }
  }

  const evaluation = evaluateProgramsForStudent_({
    programsRange,
    courseMap,
    manualElectives,
    avgRules,
    electiveRuleOverrides,
  });

  const generatedAt = new Date().toISOString();
  const response = {
    generatedAt,
    headers: RESULTS_HEADER_ROW.slice(),
    meta: {
      generatedAt,
      datasetRows: Math.max(0, programsRange.length - 1),
      activeProgramsEvaluated: Math.max(0, (evaluation.rowKeysByView && evaluation.rowKeysByView.all || []).length),
      rowKeyVersion: "v1",
      datasetStamp,
      datasetStampVersion: WEBAPP_DATASET_STAMP_VERSION,
      cacheHit: false,
      lastProgramsSyncUtc: String(
        PropertiesService.getScriptProperties().getProperty(LAST_PROGRAMS_SYNC_UTC_PROPERTY) || ""
      ).trim(),
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

  try {
    const encoded = encodeCachePayload_(response);
    if (encoded) {
      cache.put(cacheKey, encoded, WEBAPP_RESULT_CACHE_SECONDS);
    }
  } catch (err) {
    Logger.log(`Web result cache write skipped: ${String(err && err.message ? err.message : err)}`);
  }

  appendAuditEntry_({
    identity,
    summary: response.summary,
    cacheHit: false,
    datasetStamp,
  });

  return response;
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

