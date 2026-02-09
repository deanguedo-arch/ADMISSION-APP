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

function onOpen() {
  // onOpen can be invoked from contexts where Spreadsheet UI is unavailable (for example,
  // running onOpen directly from the Apps Script editor). In that case, skip menu creation.
  try {
    SpreadsheetApp.getUi()
      .createMenu("Admissions Checker")
      .addItem("Check Eligibility", "runEligibility")
      .addItem("One-Time Setup (Recommended)", "setupWorkbookForStaff")
      .addItem("Setup Student Elective Dropdowns", "setupStudentElectiveInputs")
      .addItem("Setup ElectiveRules Template", "setupElectiveRulesTemplate")
      .addSeparator()
      .addItem("Admin: Apply Staff Lockdown", "applyStaffLockdown")
      .addItem("Admin: Show All Tabs", "adminShowAllTabs")
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
  const groups = unique(
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

function runEligibility() {
  const ss = SpreadsheetApp.getActive();
  const programsSheet = ss.getSheetByName("Programs");
  const studentSheet = ss.getSheetByName("Student");
  const resultsSheet = ss.getSheetByName("Results");
  const eligibleSheet = ss.getSheetByName("Eligible") || ss.insertSheet("Eligible");
  const ineligibleSheet = ss.getSheetByName("Ineligible") || ss.insertSheet("Ineligible");
  const uncheckableSheet = ss.getSheetByName("Uncheckable") || ss.insertSheet("Uncheckable");
  const avgRules = readAvgRules(ss);
  const electiveRuleOverrides = readElectiveRuleOverrides(ss);

  if (!programsSheet || !studentSheet || !resultsSheet) {
    throw new Error("Missing one of: Programs, Student, Results sheets");
  }

  const programsRange = programsSheet.getDataRange().getValues();
  if (!programsRange || programsRange.length < 2) {
    throw new Error("Programs tab is empty. Import/sync the dataset into the Programs tab first.");
  }

  // Be forgiving: read from row 2 down (row 1 is usually headers).
  const studentRows = studentSheet.getRange(2, 1, Math.max(0, studentSheet.getLastRow() - 1), 2).getValues();
  const courseMap = buildCourseMap(studentRows);
  const electivesRows = studentSheet
    .getRange(MANUAL_ELECTIVE_START_ROW, MANUAL_ELECTIVE_COL, MANUAL_ELECTIVE_SLOTS, MANUAL_ELECTIVE_WIDTH)
    .getValues();
  const manualElectives = buildElectives(electivesRows, { source: "manual", rowOffset: MANUAL_ELECTIVE_START_ROW });
  const autoElectives = buildAutoElectivesFromCourseMap(courseMap);
  const electives = mergeElectiveCandidates_(autoElectives, manualElectives);

  if (Object.keys(courseMap).length === 0 && manualElectives.length === 0) {
    const manualRange = `D${MANUAL_ELECTIVE_START_ROW}:F${MANUAL_ELECTIVE_START_ROW + MANUAL_ELECTIVE_SLOTS - 1}`;
    throw new Error(`No student data found. Enter Course+Mark in Student!A2:B and/or manual overrides in Student!${manualRange}.`);
  }

  const header = programsRange[0].map(String);
  const rows = programsRange.slice(1);

  const idx = indexHeader(header);
  requireProgramsColumns(idx);

  const out = [];
  out.push([
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
  ]);

  rows.forEach((r) => {
    const institution = getStr(r, idx, "Institution");
    const program = getStr(r, idx, "Program");
    const credential = getStr(r, idx, "Credential_Type");
    const status = getStr(r, idx, "Status");

    if (!institution || !program) return;
    // Keep only active programs when status is provided.
    if (status && status.toLowerCase() !== "active") return;

    const reasons = [];
    const notes = [];
    const advisories = [];

    const requirementType = getStr(r, idx, "Requirement_Type");
    const requirementTypeOverride = resolveElectiveRuleOverrideText_(
      electiveRuleOverrides,
      institution,
      program
    );
    const requirementTypeEffective = combineRuleText_(requirementType, requirementTypeOverride);
    const competitiveGuidance = normalizeCompetitive(getStr(r, idx, "Competitive_Final"));
    appendDatasetNotes_(requirementTypeEffective, notes, advisories);

    const englishReq = unifyEnglishReq(r, idx);
    const englishMin = toNumber(unifyEnglishMin(r, idx));
    const englishEval = evalSubject(courseMap, "english", englishReq, englishMin);
    appendEval(englishEval, "English", reasons, notes, advisories);

    const mathReq = getStr(r, idx, "Math_Req");
    const mathMin = toNumber(getStr(r, idx, "Math_Min"));
    const mathEval = evalSubject(courseMap, "math", mathReq, mathMin);
    appendEval(mathEval, "Math", reasons, notes, advisories);

    const socialReq = getStr(r, idx, "Social_Req");
    const socialMin = toNumber(getStr(r, idx, "Social_Min"));
    const socialEval = evalSubject(courseMap, "social", socialReq, socialMin);
    appendEval(socialEval, "Social Studies", reasons, notes, advisories);

    const sciMin = toNumber(getStr(r, idx, "Science_Min"));
    const scienceReq = buildScienceReq(r, idx);
    const scienceEval = evalScience(courseMap, scienceReq, sciMin);
    appendEval(scienceEval, "Science", reasons, notes, advisories);

    const electiveQty = getStr(r, idx, "Elective_Qty");
    const electiveNeedParsed = parseElectiveQty(electiveQty);
    const electivePool = getStr(r, idx, "Elective_Pool");
    const allowedGroups = parseAllowedGroups(electivePool);
    const electiveRules = parseElectiveRules_(requirementTypeEffective);

    const avgMin = toNumber(getStr(r, idx, "Min_Avg_Final"));
    const avgTotalFromData = toNumber(getStr(r, idx, "Avg_Total"));
    // Average rule:
    // - If the program specifies an elective quantity (e.g., "Three"), average uses:
    //   required named courses + that many electives.
    // - Otherwise, use AvgRules overrides (per-program or per-institution wildcard). If still missing and the program
    //   has a minimum average, fall back to 5 but mark as not fully checkable.
    const requiredMarks = collectRequiredMarks([englishEval, mathEval, socialEval, scienceEval]);
    const requiredSlots = countRequiredSlots([englishEval, mathEval, socialEval, scienceEval]);
    const assumedTarget = 5;
    const avgTotal = resolveAvgTotal({
      institution,
      program,
      avgMin,
      electiveNeedParsed,
      requiredSlots,
      avgRules,
      fallbackTarget: assumedTarget,
      notes,
      avgTotalFromData,
    });

    const electiveNeededForAvg = Math.max(0, avgTotal - requiredSlots);

    const avg = computeStudentAverage({
      requiredItems: requiredMarks,
      electives,
      allowedGroups,
      electiveNeeded: electiveNeededForAvg,
      totalNeeded: avgTotal,
      electiveRules,
    });

    if (isFinite(avgMin)) {
      const avgComplete = isFinite(avgTotal) && avgTotal > 0 && avg.usedCount >= avgTotal;
      if (!avgComplete) {
        reasons.push(`Average incomplete (need ${avgTotal} marks; have ${avg.usedCount})`);
      } else if (isFinite(avg.value) && avg.value < avgMin) {
        reasons.push(`Admission average too low (${avg.value.toFixed(1)} < ${avgMin})`);
      }

      const missingElectivesForAvg = Math.max(0, electiveNeededForAvg - (avg.selectedElectives || []).length);
      if (missingElectivesForAvg > 0) {
        const usable = (avg.usableElectives || []).slice().sort((a, b) => b.mark - a.mark);
        const ruleSummary = formatElectiveRuleSummary_(electiveRules);
        const have = usable
          .slice(0, 8)
          .map((e) => `${e.group}${e.name ? ` (${e.name})` : ""}=${e.mark}`)
          .join(", ");

        // Only compute "what do I need on the remaining electives?" once all required (named) slots are filled.
        const usedRequiredCount = (avg.usedRequired || []).length;
        const missingRequiredSlots = Math.max(0, requiredSlots - usedRequiredCount);
        let needHint = "";
        if (missingRequiredSlots === 0 && isFinite(avgTotal) && avgTotal > 0 && isFinite(avg.sumUsed)) {
          const remaining = missingElectivesForAvg;
          const needTotal = avgMin * avgTotal - avg.sumUsed;
          const needAvg = remaining > 0 ? needTotal / remaining : NaN;
          if (isFinite(needAvg)) {
            const clamped = Math.max(0, needAvg);
            needHint = `; to meet ${avgMin}, remaining elective(s) need avg >= ${clamped.toFixed(1)}` + (clamped > 100 ? " (not possible)" : "");
          }
        }

        reasons.push(
          `Need ${missingElectivesForAvg} more elective mark(s) for average (allowed groups: ${allowedGroups.join("/")}` +
            `${ruleSummary ? `; ${ruleSummary}` : ""}` +
            `)` +
            (have ? `; current elective marks: ${have}` : "") +
            needHint
        );
      }
    }

    out.push([
      institution,
      program,
      credential,
      isFinite(avgMin) ? avgMin : "",
      isFinite(avgMin) && isFinite(avgTotal) && avgTotal > 0 && avg.usedCount >= avgTotal && isFinite(avg.value)
        ? Number(avg.value.toFixed(1))
        : "",
      avgTotal || "",
      formatAvgUsed_(avg),
      competitiveGuidance,
      (reasons || []).join(" | "),
      buildNotes_(notes, advisories),
    ]);
  });

  // Sort: Institution, Program, Credential
  const body = out.slice(1);
  body.sort((a, b) => {
    const i = String(a[0]).localeCompare(String(b[0]));
    if (i !== 0) return i;
    const p = String(a[1]).localeCompare(String(b[1]));
    if (p !== 0) return p;
    return String(a[2]).localeCompare(String(b[2]));
  });

  const finalOut = [out[0]].concat(body);
  resultsSheet.clearContents();
  resultsSheet.getRange(1, 1, finalOut.length, finalOut[0].length).setValues(finalOut);
  resultsSheet.setFrozenRows(1);
  applyCompetitiveHighlight_(resultsSheet, finalOut);

  // Split views
  const eligibleRows = [out[0]].concat(
    body.filter((r) => {
      const missing = String(r[8] || "").trim();
      const notes = String(r[9] || "").trim();
      return missing === "" && !isUncheckable_(notes);
    })
  );
  const ineligibleRows = [out[0]].concat(body.filter((r) => String(r[8] || "").trim() !== ""));
  const uncheckableRows = [out[0]].concat(
    body.filter((r) => {
      const missing = String(r[8] || "").trim();
      const notes = String(r[9] || "").trim();
      return missing === "" && isUncheckable_(notes);
    })
  );

  eligibleSheet.clearContents();
  eligibleSheet.getRange(1, 1, eligibleRows.length, eligibleRows[0].length).setValues(eligibleRows);
  eligibleSheet.setFrozenRows(1);
  applyCompetitiveHighlight_(eligibleSheet, eligibleRows);

  ineligibleSheet.clearContents();
  ineligibleSheet.getRange(1, 1, ineligibleRows.length, ineligibleRows[0].length).setValues(ineligibleRows);
  ineligibleSheet.setFrozenRows(1);
  applyCompetitiveHighlight_(ineligibleSheet, ineligibleRows);

  uncheckableSheet.clearContents();
  uncheckableSheet.getRange(1, 1, uncheckableRows.length, uncheckableRows[0].length).setValues(uncheckableRows);
  uncheckableSheet.setFrozenRows(1);
  applyCompetitiveHighlight_(uncheckableSheet, uncheckableRows);
}

function indexHeader(header) {
  const idx = {};
  header.forEach((h, i) => {
    const key = normHeaderKey(h);
    if (!key) return;
    // Keep the first occurrence.
    if (idx[key] === undefined) idx[key] = i;
  });
  return idx;
}

function normHeaderKey(h) {
  return String(h || "")
    .replace(/^\uFEFF/, "") // BOM
    .trim()
    .toLowerCase();
}

function requireProgramsColumns(idx) {
  const required = ["institution", "program", "credential_type", "status"];
  const missing = required.filter((k) => idx[k] === undefined);
  if (missing.length) {
    throw new Error(
      `Programs tab is not the admissions dataset (missing columns: ${missing.join(
        ", "
      )}). Import/sync data/ALBERTA_ADMISSIONS_MASTER_CANONICAL.csv into the Programs tab.`
    );
  }
}

function readAvgRules(ss) {
  const sheet = ss.getSheetByName("AvgRules");
  if (!sheet) return { byKey: {}, byInstitution: {} };
  const values = sheet.getDataRange().getValues();
  if (!values || values.length < 2) return { byKey: {}, byInstitution: {} };

  const header = values[0].map((x) => String(x || "").trim());
  const idx = {};
  header.forEach((h, i) => (idx[normHeaderKey(h)] = i));

  const byKey = {};
  const byInstitution = {};

  for (let i = 1; i < values.length; i++) {
    const row = values[i];
    const institution = String(row[idx["institution"]] || "").trim();
    const program = String(row[idx["program"]] || "").trim();
    const avgTotal = toNumber(row[idx["avg_total"]]);
    if (!institution || !isFinite(avgTotal) || avgTotal <= 0) continue;

    if (program === "*" || !program) {
      byInstitution[institution] = Math.round(avgTotal);
      continue;
    }
    byKey[`${institution}||${program}`] = Math.round(avgTotal);
  }

  return { byKey, byInstitution };
}

function readElectiveRuleOverrides(ss) {
  const sheet = ss.getSheetByName("ElectiveRules");
  if (!sheet) return { byKey: {}, byInstitution: {} };

  const values = sheet.getDataRange().getValues();
  if (!values || values.length < 2) return { byKey: {}, byInstitution: {} };

  const header = values[0].map((x) => String(x || "").trim());
  const idx = {};
  header.forEach((h, i) => (idx[normHeaderKey(h)] = i));

  const institutionCol = idx["institution"];
  const programCol = idx["program"];
  const ruleColCandidates = ["rule_text", "requirement_type", "elective_rule", "rule", "rules"];
  const ruleCol = ruleColCandidates.find((k) => idx[k] !== undefined);
  if (institutionCol === undefined || programCol === undefined || ruleCol === undefined) {
    return { byKey: {}, byInstitution: {} };
  }

  const byKey = {};
  const byInstitution = {};
  for (let i = 1; i < values.length; i++) {
    const row = values[i];
    const institution = String(row[institutionCol] || "").trim();
    const program = String(row[programCol] || "").trim();
    const ruleText = String(row[idx[ruleCol]] || "").trim();
    if (!institution || !ruleText) continue;

    if (program === "*" || !program) {
      if (!byInstitution[institution]) byInstitution[institution] = [];
      byInstitution[institution].push(ruleText);
      continue;
    }

    const key = `${institution}||${program}`;
    if (!byKey[key]) byKey[key] = [];
    byKey[key].push(ruleText);
  }

  return { byKey, byInstitution };
}

function resolveElectiveRuleOverrideText_(overrides, institution, program) {
  if (!overrides) return "";
  const parts = [];
  if (overrides.byInstitution && overrides.byInstitution[institution]) {
    parts.push(...overrides.byInstitution[institution]);
  }
  const key = `${institution}||${program}`;
  if (overrides.byKey && overrides.byKey[key]) {
    parts.push(...overrides.byKey[key]);
  }
  return unique(parts.map((x) => String(x || "").trim()).filter(Boolean)).join("; ");
}

function combineRuleText_(baseText, overrideText) {
  const a = String(baseText || "").trim();
  const b = String(overrideText || "").trim();
  if (a && b) return `${a}; ${b}`;
  return a || b || "";
}

function resolveAvgTotal(opts) {
  const {
    institution,
    program,
    avgMin,
    electiveNeedParsed,
    requiredSlots,
    avgRules,
    fallbackTarget,
    notes,
    avgTotalFromData,
  } = opts;

  // 0) If the dataset already contains Avg_Total, use it.
  if (isFinite(avgTotalFromData) && avgTotalFromData > 0) return Math.round(avgTotalFromData);

  // 1) If electives explicitly specified in dataset, total courses is required slots + electives.
  if (electiveNeedParsed !== null) return Math.max(0, requiredSlots + electiveNeedParsed);

  // 2) Explicit per-program override.
  const key = `${institution}||${program}`;
  if (avgRules && avgRules.byKey && avgRules.byKey[key]) return avgRules.byKey[key];

  // 3) Institution wildcard default (Program="*").
  if (avgRules && avgRules.byInstitution && avgRules.byInstitution[institution]) {
    return avgRules.byInstitution[institution];
  }

  // 3.5) NAIT is overwhelmingly a 5-course admission average for high-school entry.
  // Treat this as the default so it doesn't feel "random" or require maintaining AvgRules.
  const inst = String(institution || "").trim().toUpperCase();
  if (inst === "NAIT" && isFinite(avgMin)) {
    return 5;
  }

  // 3.6) UAlberta first-year admission averages are typically calculated on 5 admission subjects.
  // Default to 5 when a minimum average is specified.
  if (inst === "UALBERTA" && isFinite(avgMin)) {
    return 5;
  }

  // 4) If program requires a minimum average but we don't know the course count, fall back but flag.
  if (isFinite(avgMin)) {
    (notes || []).push(`Avg course-count defaulted to ${fallbackTarget}; set AvgRules to be exact`);
    return fallbackTarget || 5;
  }

  // No minimum average; average isn't needed.
  return 0;
}

function getStr(row, idx, col) {
  const i = idx[normHeaderKey(col)];
  if (i === undefined) return "";
  const v = row[i];
  if (v === null || v === undefined) return "";
  return String(v).trim();
}

function unifyEnglishReq(row, idx) {
  const a = getStr(row, idx, "English_Req");
  if (a) return a;
  const b = getStr(row, idx, "Eng_Req");
  return b;
}

function unifyEnglishMin(row, idx) {
  const a = getStr(row, idx, "English_Min");
  if (a) return a;
  const b = getStr(row, idx, "Eng_Min");
  return b;
}

function toNumber(v) {
  if (v === null || v === undefined) return NaN;
  const s = String(v).trim();
  if (!s) return NaN;
  const n = Number(s);
  return isFinite(n) ? n : NaN;
}

function canonKey(s) {
  return String(s || "")
    .trim()
    .toUpperCase()
    .replace(/\./g, "")
    .replace(/\s+/g, " ");
}

function buildCourseMap(studentRows) {
  const map = {};
  const alias = courseAliases();
  studentRows.forEach(([course, mark]) => {
    const c = String(course || "").trim();
    const m = toNumber(mark);
    if (!c || !isFinite(m)) return;
    const k0 = canonKey(c);
    const k = alias[k0] || k0;
    map[k] = m;
  });
  return map;
}

function courseAliases() {
  // Map student-entered course strings to canonical keys.
  const pairs = [
    ["ENGLISH LANGUAGE ARTS 30-1", "ENGLISH 30-1"],
    ["ENGLISH LANGUAGE ARTS 30-2", "ENGLISH 30-2"],
    ["ENGLISH LANGUAGE ARTS 20-1", "ENGLISH 20-1"],
    ["ENGLISH LANGUAGE ARTS 20-2", "ENGLISH 20-2"],
    ["FRENCH LANGUAGE ARTS 30-1", "FRENCH LANGUAGE ARTS 30-1"],
    ["FRENCH LANGUAGE ARTS 30-2", "FRENCH LANGUAGE ARTS 30-2"],
    ["BIO 30", "BIOLOGY 30"],
    ["BIOLOGY 30", "BIOLOGY 30"],
    ["CHEM 30", "CHEMISTRY 30"],
    ["CHEMISTRY 30", "CHEMISTRY 30"],
    ["PHYS 30", "PHYSICS 30"],
    ["PHYSICS 30", "PHYSICS 30"],
    ["SCI 30", "SCIENCE 30"],
    ["SCIENCE 30", "SCIENCE 30"],
    ["MATH 30-1", "MATH 30-1"],
    ["MATH 30-2", "MATH 30-2"],
    ["MATHEMATICS 30-1", "MATH 30-1"],
    ["MATHEMATICS 30-2", "MATH 30-2"],
    ["MATH 20-1", "MATH 20-1"],
    ["MATH 20-2", "MATH 20-2"],
    ["MATH 31", "MATH 31"],
    ["MATHEMATICS 20-1", "MATH 20-1"],
    ["MATHEMATICS 20-2", "MATH 20-2"],
    ["MATHEMATICS 31", "MATH 31"],
    ["SOCIAL 30-1", "SOCIAL STUDIES 30-1"],
    ["SOCIAL STUDIES 30-1", "SOCIAL STUDIES 30-1"],
    ["SOCIAL 30-2", "SOCIAL STUDIES 30-2"],
    ["SOCIAL STUDIES 30-2", "SOCIAL STUDIES 30-2"],
    ["ABORIGINAL STUDIES 30", "ABORIGINAL STUDIES 30"],
    ["CANADIAN STUDIES 30", "CANADIAN STUDIES 30"],
    ["ECONOMICS 30", "ECONOMICS 30"],
    ["HISTORY 30", "HISTORY 30"],
    ["LAW 30", "LAW 30"],
    ["PHILOSOPHY 30", "PHILOSOPHY 30"],
    ["PSYCHOLOGY 30", "PSYCHOLOGY 30"],
    ["RELIGIOUS STUDIES 30", "RELIGIOUS STUDIES 30"],
    ["WORLD GEOGRAPHY 30", "WORLD GEOGRAPHY 30"],
    ["WORLD HISTORY 30", "WORLD HISTORY 30"],
    ["ART 30", "ART 30"],
    ["ART 31", "ART 31"],
    ["CHORAL MUSIC 30", "CHORAL MUSIC 30"],
    ["INSTRUMENTAL MUSIC 30", "INSTRUMENTAL MUSIC 30"],
    ["GENERAL MUSIC 30", "GENERAL MUSIC 30"],
    ["JAZZ 30", "JAZZ 30"],
    ["DRAMA 30", "DRAMA 30"],
    ["MUSIC 30", "MUSIC 30"],
    ["DANCE 35", "DANCE 35"],
    ["PHYSICAL EDUCATION 30", "PHYSICAL EDUCATION 30"],
    ["RECREATION LEADERSHIP 30", "RECREATION LEADERSHIP 30"],
    ["RECREATION LEADERSHIP (ADVANCED LEVEL CTS)", "RECREATION LEADERSHIP 30"],
    ["COMPUTING SCIENCE ADVANCED CTS", "COMPUTER SCIENCE ADVANCED CTS"],
    ["COMPUTER SCIENCE ADVANCED CTS", "COMPUTER SCIENCE ADVANCED CTS"],
    ["COMMUNICATION TECHNOLOGY ADVANCED CTS", "COMMUNICATION TECHNOLOGY ADVANCED CTS"],
    ["CALCULUS 31", "CALCULUS 31"],
    ["AMERICAN SIGN LANGUAGE AND DEAF CULTURE 35", "AMERICAN SIGN LANGUAGE AND DEAF CULTURE 35"],
    ["ARABIC LANGUAGE AND CULTURE 30", "ARABIC LANGUAGE AND CULTURE 30"],
    ["ARABIC LANGUAGE AND CULTURE 35", "ARABIC LANGUAGE AND CULTURE 35"],
    ["BLACKFOOT LANGUAGE AND CULTURE 30", "BLACKFOOT LANGUAGE AND CULTURE 30"],
    ["CHINESE LANGUAGE AND CULTURE 30", "CHINESE LANGUAGE AND CULTURE 30"],
    ["CHINESE LANGUAGE AND CULTURE 35", "CHINESE LANGUAGE AND CULTURE 35"],
    ["CREE LANGUAGE AND CULTURE 30", "CREE LANGUAGE AND CULTURE 30"],
    ["GERMAN LANGUAGE AND CULTURE 30", "GERMAN LANGUAGE AND CULTURE 30"],
    ["GERMAN LANGUAGE AND CULTURE 35", "GERMAN LANGUAGE AND CULTURE 35"],
    ["ITALIAN LANGUAGE AND CULTURE 30", "ITALIAN LANGUAGE AND CULTURE 30"],
    ["ITALIAN LANGUAGE AND CULTURE 35", "ITALIAN LANGUAGE AND CULTURE 35"],
    ["JAPANESE LANGUAGE AND CULTURE 30", "JAPANESE LANGUAGE AND CULTURE 30"],
    ["JAPANESE LANGUAGE AND CULTURE 35", "JAPANESE LANGUAGE AND CULTURE 35"],
    ["KOREAN LANGUAGE AND CULTURE 30", "KOREAN LANGUAGE AND CULTURE 30"],
    ["LATIN LANGUAGE AND CULTURE 30", "LATIN LANGUAGE AND CULTURE 30"],
    ["PUNJABI LANGUAGE AND CULTURE 30", "PUNJABI LANGUAGE AND CULTURE 30"],
    ["RUSSIAN LANGUAGE AND CULTURE 30", "RUSSIAN LANGUAGE AND CULTURE 30"],
    ["SPANISH LANGUAGE AND CULTURE 30", "SPANISH LANGUAGE AND CULTURE 30"],
    ["SPANISH LANGUAGE AND CULTURE 35", "SPANISH LANGUAGE AND CULTURE 35"],
    ["UKRAINIAN LANGUAGE AND CULTURE 30", "UKRAINIAN LANGUAGE AND CULTURE 30"],
  ];
  const map = {};
  pairs.forEach(([k, v]) => (map[k] = v));
  return map;
}

function evalSubject(courseMap, subject, reqText, minMark) {
  const t = String(reqText || "").trim();
  if (!t) return { kind: "none" };
  if (/^(See Degree|Refer to Degree)$/i.test(t)) return { kind: "unknown", reason: t };
  if (/(placement|assessment|test)/i.test(t)) return { kind: "assessment", reason: "assessment/placement mentioned" };
  if (/english language proficiency/i.test(t)) return { kind: "unknown", reason: "English language proficiency" };
  if (/\bunspecified\b/i.test(t)) return { kind: "unknown", reason: `${title(subject)} requirement unspecified` };

  // Support simple AND requirements like "Mathematics 30-1 and Mathematics 31".
  // Each AND-part can itself be an OR list (e.g., "30-1 or 30-2 and 31").
  const andParts = splitByAnd_(t);
  if (andParts.length > 1) {
    const parts = andParts.map((p) => {
      const courses = normalizeRequirementToCourses(subject, p);
      const best = bestMarkWithEquivalencies(courseMap, courses);
      return { courses, best };
    });
    const out = { kind: "all", parts };
    if (isFinite(minMark) && minMark > 0) out.minMark = minMark;
    return out;
  }

  const courses = normalizeRequirementToCourses(subject, t);
  const best = bestMarkWithEquivalencies(courseMap, courses);
  const out = { kind: "any", courses, best };
  if (isFinite(minMark) && minMark > 0) out.minMark = minMark;
  return out;
}

function evalScience(courseMap, scienceReq, minMark) {
  if (!scienceReq || scienceReq.kind === "none") return { kind: "none" };
  if (scienceReq.kind === "unknown") return { kind: "unknown", reason: scienceReq.reason };

  if (scienceReq.kind === "all") {
    const courses = scienceReq.courses || [];
    const checks = courses.map((c) => {
      const best = bestMarkWithEquivalencies(courseMap, [c]);
      if (!best) return { course: c, ok: false, reason: `Missing ${c}` };
      if (isFinite(minMark) && minMark > 0 && best.mark < minMark) {
        return { course: c, ok: false, reason: `${c} mark too low: ${best.mark} < ${minMark}`, mark: best.mark, key: best.key };
      }
      return { course: c, ok: true, mark: best.mark, key: best.key };
    });
    return { kind: "all", courses, checks, minMark };
  }

  if (scienceReq.kind === "all_plus_any") {
    const allCourses = unique(scienceReq.allCourses || []);
    const anyCourses = unique(scienceReq.anyCourses || []);

    const checksAll = allCourses.map((c) => {
      const best = bestMarkWithEquivalencies(courseMap, [c]);
      if (!best) return { course: c, ok: false, reason: `Missing ${c}` };
      if (isFinite(minMark) && minMark > 0 && best.mark < minMark) {
        return { course: c, ok: false, reason: `${c} mark too low: ${best.mark} < ${minMark}`, mark: best.mark, key: best.key };
      }
      return { course: c, ok: true, mark: best.mark, key: best.key };
    });

    const bestAny = bestMarkWithEquivalencies(courseMap, anyCourses);
    let anyOk = true;
    let anyReason = "";
    if (!bestAny) {
      anyOk = false;
      anyReason = `Missing one of: ${anyCourses.join(" OR ")}`;
    } else if (isFinite(minMark) && minMark > 0 && bestAny.mark < minMark) {
      anyOk = false;
      anyReason = `Science mark too low: ${bestAny.course}=${bestAny.mark} < ${minMark}`;
    }

    return {
      kind: "all_plus_any",
      allCourses,
      anyCourses,
      checksAll,
      bestAny,
      anyOk,
      anyReason,
      minMark,
    };
  }

  if (scienceReq.kind === "kof") {
    const courses = unique(scienceReq.courses || []);
    const k = Math.max(0, Math.round(scienceReq.k || 0));

    const candidates = [];
    courses.forEach((c) => {
      const best = bestMarkWithEquivalencies(courseMap, [c]);
      if (!best) return;
      if (isFinite(minMark) && minMark > 0 && best.mark < minMark) return;
      candidates.push({ course: c, mark: best.mark, key: best.key });
    });

    candidates.sort((a, b) => b.mark - a.mark);
    const selected = candidates.slice(0, k);
    const ok = selected.length >= k;

    return { kind: "kof", courses, k, selected, candidates, minMark, ok };
  }

  // Default: any-of list
  const courses = scienceReq.courses || [];
  const best = bestMarkWithEquivalencies(courseMap, courses);
  const out = { kind: "any", courses, best };
  if (isFinite(minMark) && minMark > 0) out.minMark = minMark;
  return out;
}

function appendEval(ev, label, reasons, notes, advisories) {
  if (!ev || ev.kind === "none") return;
  if (ev.kind === "unknown") {
    notes.push(`${label}: ${ev.reason}`);
    return;
  }
  if (ev.kind === "assessment") {
    advisories.push(`${label}: assessment/placement required`);
    return;
  }
  if (ev.kind === "all") {
    // Used for Science (checks array) and for AND-required subjects (parts array).
    if (ev.checks && ev.checks.length) {
      const checks = ev.checks || [];
      checks.forEach((c) => {
        if (c && c.ok === false && c.reason) reasons.push(c.reason);
      });
      return;
    }

    const parts = ev.parts || [];
    parts.forEach((p) => {
      if (!p) return;
      const courses = p.courses || [];
      const best = p.best || null;
      if (!best) {
        if (courses.length) reasons.push(`Missing ${label} (${courses.join(" OR ")})`);
        return;
      }
      if (isFinite(ev.minMark) && ev.minMark > 0 && best.mark < ev.minMark) {
        reasons.push(`${label} mark too low: ${best.course}=${best.mark} < ${ev.minMark}`);
      }
    });
    return;
  }

  if (ev.kind === "all_plus_any") {
    (ev.checksAll || []).forEach((c) => {
      if (c && c.ok === false && c.reason) reasons.push(c.reason);
    });
    if (ev.anyOk === false && ev.anyReason) reasons.push(ev.anyReason);
    return;
  }

  if (ev.kind === "kof") {
    if (!ev.ok) {
      reasons.push(`Missing ${label} (need ${ev.k} of: ${String((ev.courses || []).join(", "))})`);
      return;
    }
    return;
  }

  if (ev.kind === "any") {
    if (!ev.best) {
      // Only fail if the program actually lists courses.
      if (ev.courses && ev.courses.length) reasons.push(`Missing ${label} (${ev.courses.join(" OR ")})`);
      return;
    }
    if (isFinite(ev.minMark) && ev.best.mark < ev.minMark) {
      reasons.push(`${label} mark too low: ${ev.best.course}=${ev.best.mark} < ${ev.minMark}`);
    }
  }
}

function buildScienceReq(row, idx) {
  // Prefer NAIT-style flags when present.
  const flagPairs = [
    ["Bio_30_Req", "Biology 30"],
    ["Chem_30_Req", "Chemistry 30"],
    ["Phys_30_Req", "Physics 30"],
    ["Sci_30_Req", "Science 30"],
  ];
  const flagCourses = [];
  flagPairs.forEach(([flag, course]) => {
    const v = getStr(row, idx, flag);
    if (/^yes$/i.test(v)) flagCourses.push(course);
  });

  const t = getStr(row, idx, "Science_Req");
  if (!t && !flagCourses.length) return { kind: "none" };
  if (!t && flagCourses.length) return { kind: "all", courses: flagCourses };
  if (/^(See Degree|Refer to Degree)$/i.test(t)) return { kind: "unknown", reason: t };

  const parsed = parseScienceRequirementText_(t);
  if (flagCourses.length && parsed.kind === "any" && parsed.courses && parsed.courses.length) {
    // Used for patterns like: Bio 30 required + (Chem 30 OR Sci 30).
    return { kind: "all_plus_any", allCourses: flagCourses, anyCourses: parsed.courses };
  }
  if (flagCourses.length) return { kind: "all", courses: flagCourses };
  return parsed;
}

function parseAlternatives(subject, text) {
  const norm = String(text || "")
    .replace(/\//g, " or ")
    .replace(/\s+/g, " ")
    .trim();

  // If we have course codes, prefer extracting them.
  const codes = extractCourseCodes(norm);
  if (codes.length) {
    const prefix =
      subject === "english" ? "English " :
      subject === "math" ? "Math " :
      subject === "social" ? "Social Studies " :
      "";
    return unique(codes.map((c) => prefix + c));
  }

  const parts = norm.split(/\s+or\s+/i).map((x) => x.trim()).filter(Boolean);
  const prefix =
    subject === "english" ? "English " :
    subject === "math" ? "Math " :
    subject === "social" ? "Social Studies " :
    "";

  return parts.map((p) => {
    const q = p.replace(/^(English|Math|Social Studies|Social)\s+/i, "");
    if (/^\d{2}-\d$/.test(q)) return prefix + q;
    return p;
  });
}

function normalizeRequirementToCourses(subject, rawText) {
  const t = String(rawText || "").trim();
  if (!t) return [];

  // Handle NAIT-style: "English (Grade 10-12 Equivalent)" / "Math (Grade 10 Equivalent)".
  if (/grade\s*10\s*-\s*12\s*equivalent|grade\s*10\s*equivalent/i.test(t)) {
    if (subject === "english") {
      return ["English 30-1", "English 30-2", "English 20-1", "English 20-2"];
    }
    if (subject === "math") {
      return ["Math 30-1", "Math 30-2", "Math 20-1", "Math 20-2"];
    }
    if (subject === "social") {
      return ["Social Studies 30-1", "Social Studies 30-2"];
    }
  }

  const courses = parseAlternatives(subject, t);
  // Handle Math 31-style requirements (no dash).
  if (subject === "math" && /(?:math|mathematics)\s*31\b/i.test(t)) {
    courses.push("Math 31");
  }
  return unique(courses);
}

function bestMarkWithEquivalencies(courseMap, courses) {
  let best = null;
  courses.forEach((c) => {
    const alias = courseAliases();
    const keys = expandEquivalencies(c).map((x) => {
      const k0 = canonKey(x);
      return alias[k0] || k0;
    });
    keys.forEach((k, i) => {
      const m = courseMap[k];
      if (m === undefined) return;
      const shownCourse = i === 0 ? c : keys[0];
      if (!best || m > best.mark) best = { course: shownCourse, mark: m, key: k };
    });
  });
  return best;
}

function expandEquivalencies(course) {
  const s = String(course || "").trim();
  if (!s) return [];

  const t = canonKey(s);
  const m = /^(ENGLISH|MATH|SOCIAL STUDIES)\s+(20|30)-([12])$/.exec(t);
  if (!m) return [s];

  const subj = m[1];
  const level = Number(m[2]);
  const stream = m[3]; // "1" or "2"

  const out = [];
  const label = subj === "SOCIAL STUDIES" ? "Social Studies" : title(subj.toLowerCase());

  // Exact requirement first.
  out.push(`${label} ${level}-${stream}`);

  // -1 can satisfy -2, not vice versa.
  if (stream === "2") out.push(`${label} ${level}-1`);

  // 30-level can satisfy 20-level (same stream), and 30-1 can satisfy 20-2 via the -2 rule.
  if (level === 20) {
    out.push(`${label} 30-${stream}`);
    if (stream === "2") out.push(`${label} 30-1`);
  }

  return unique(out);
}

function extractCourseCodes(text) {
  const t = String(text || "").replace(/\//g, " ");
  const out = [];
  const re = /\b(\d{2}-[12])\b/g;
  let m;
  while ((m = re.exec(t))) out.push(m[1]);
  return unique(out);
}

function unique(arr) {
  const seen = {};
  const out = [];
  arr.forEach((x) => {
    const k = String(x);
    if (seen[k]) return;
    seen[k] = true;
    out.push(x);
  });
  return out;
}

function buildElectives(rows, opts) {
  const source = String((opts && opts.source) || "manual").trim().toLowerCase();
  const rowOffset = Math.max(1, Math.round(toNumber((opts && opts.rowOffset) || 1) || 1));
  const electives = [];
  (rows || []).forEach(([name, group, mark], i) => {
    const m = toNumber(mark);
    if (!isFinite(m)) return;

    const label = String(name || "").trim();
    const key = label ? normalizeCourseKey_(label) : "";
    const overrideGroup = String(group || "").trim().toUpperCase();
    let groups = [];
    if (["A", "B", "C", "D"].includes(overrideGroup)) groups = [overrideGroup];
    else if (key) groups = electiveGroupsForCourseKey_(key);
    if (!groups.length) return;

    groups = unique(groups.filter((g) => ["A", "B", "C", "D"].includes(String(g || "").toUpperCase())));
    if (!groups.length) return;

    groups.forEach((resolvedGroup) => {
      electives.push({
        name: label,
        group: String(resolvedGroup).toUpperCase(),
        mark: m,
        source,
        key,
        sourceKey: `${source.toUpperCase()}_ROW_${rowOffset + i}`,
      });
    });
  });
  return electives;
}

function listElectiveCourseOptions_() {
  const options = Object.keys(courseGroupMap_())
    .map((k) => formatCourseName_(k))
    .filter(Boolean);
  return unique(options).sort((a, b) => String(a).localeCompare(String(b)));
}

function setupWorkbookForStaff(opts) {
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

  const studentSetupMsg = setupStudentElectiveInputs({ quiet: true });
  const rulesSetupMsg = setupElectiveRulesTemplate({ quiet: true });
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

function applyStaffLockdown() {
  const ss = SpreadsheetApp.getActive();
  assertAdminRunner_(ss);
  setupWorkbookForStaff({ quiet: true });

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

function adminShowAllTabs() {
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

function setupStudentElectiveInputs(opts) {
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

function setupElectiveRulesTemplate(opts) {
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

function buildAutoElectivesFromCourseMap(courseMap) {
  const out = [];
  Object.keys(courseMap || {}).forEach((courseKey) => {
    const mark = toNumber(courseMap[courseKey]);
    if (!isFinite(mark)) return;
    const groups = electiveGroupsForCourseKey_(courseKey);
    if (!groups.length) return;
    groups.forEach((group) => {
      out.push({
        name: formatCourseName_(courseKey),
        group,
        mark,
        source: "auto",
        key: courseKey,
        sourceKey: `AUTO_${courseKey}`,
      });
    });
  });
  return out;
}

function mergeElectiveCandidates_(autoElectives, manualElectives) {
  const merged = {};
  const all = (autoElectives || []).concat(manualElectives || []);
  all.forEach((item, idx) => {
    if (!item) return;
    const group = String(item.group || "").trim().toUpperCase();
    const mark = toNumber(item.mark);
    if (!["A", "B", "C", "D"].includes(group)) return;
    if (!isFinite(mark)) return;

    const name = String(item.name || "").trim();
    const source = String(item.source || "").trim().toLowerCase() || "manual";
    const key = String(item.key || "").trim().toUpperCase();
    const sourceKey = String(item.sourceKey || `${source.toUpperCase()}_${idx}`).trim();
    const unitKey = key || sourceKey;
    const dedupeKey = `${unitKey}||${group}`;
    const prev = merged[dedupeKey];

    if (!prev || mark > prev.mark) {
      merged[dedupeKey] = {
        name,
        group,
        mark,
        source,
        key,
        sourceKey,
      };
    }
  });
  return Object.keys(merged).map((k) => merged[k]);
}

function normalizeCourseKey_(course) {
  const k0 = canonKey(course);
  const alias = courseAliases();
  return alias[k0] || k0;
}

function formatCourseName_(courseKey) {
  const pretty = {
    "ENGLISH 30-1": "English 30-1",
    "ENGLISH 30-2": "English 30-2",
    "ENGLISH 20-1": "English 20-1",
    "ENGLISH 20-2": "English 20-2",
    "SOCIAL STUDIES 30-1": "Social Studies 30-1",
    "SOCIAL STUDIES 30-2": "Social Studies 30-2",
    "SOCIAL STUDIES 20-1": "Social Studies 20-1",
    "SOCIAL STUDIES 20-2": "Social Studies 20-2",
    "MATH 30-1": "Math 30-1",
    "MATH 30-2": "Math 30-2",
    "MATH 20-1": "Math 20-1",
    "MATH 20-2": "Math 20-2",
    "MATH 31": "Math 31",
    "BIOLOGY 30": "Biology 30",
    "CHEMISTRY 30": "Chemistry 30",
    "PHYSICS 30": "Physics 30",
    "SCIENCE 30": "Science 30",
  };
  const key = String(courseKey || "").trim().toUpperCase();
  if (pretty[key]) return pretty[key];
  return key
    .split(" ")
    .map((w) => (/^\d/.test(w) ? w : w.charAt(0) + w.slice(1).toLowerCase()))
    .join(" ");
}

function electiveGroupsForCourseKey_(courseKey) {
  const key = String(courseKey || "").trim().toUpperCase();
  if (!key) return [];

  const map = courseGroupMap_();
  if (map[key] && map[key].length) return unique(map[key]);

  const inferred = [];
  if (isLikelyLanguageCourse_(key)) inferred.push("A");
  if (/(ENGLISH|SOCIAL STUDIES|HISTORY|GEOGRAPHY|PSYCHOLOGY|PHILOSOPHY|LAW|RELIGION|ABORIGINAL|NATIVE STUDIES|CANADIAN STUDIES|ECONOMICS)/.test(key)) {
    inferred.push("A");
  }
  if (/(MATH|MATHEMATICS|BIOLOGY|CHEMISTRY|PHYSICS|SCIENCE|CALCULUS|STATISTICS)/.test(key)) {
    inferred.push("C");
  }
  if (/(ART|DRAMA|MUSIC|DANCE|PHYSICAL EDUCATION|RECREATION|COMMUNICATION TECHNOLOGY|CTS|COMPUTER SCIENCE|DESIGN STUDIES|CHORAL|INSTRUMENTAL|JAZZ)/.test(key)) {
    inferred.push("B");
  }
  if (/(WELD|MECHANIC|CONSTRUCTION|CARPENTRY|AUTOMOTIVE|FOODS|FASHION|COSMETOLOGY|ESTHETICS|ENTERPRISE|TRADES)/.test(key)) {
    inferred.push("D");
  }
  if (!inferred.length && isLikelyGroupDAdmissionSubject_(key)) inferred.push("D");
  return unique(inferred);
}

function isLikelyLanguageCourse_(key) {
  return /(LANGUAGE|FRANCAIS|FRENCH|SPANISH|GERMAN|JAPANESE|CHINESE|MANDARIN|CANTONESE|KOREAN|ARABIC|PUNJABI|HINDI|URDU|TAGALOG|ITALIAN|PORTUGUESE|RUSSIAN|UKRAINIAN|CREE|BLACKFOOT|LATIN|SIGN LANGUAGE|ASL|BILINGUAL|LANGUAGE AND CULTURE)/.test(
    String(key || "").toUpperCase()
  );
}

function isSeniorHighAdmissionLevel_(key) {
  const t = String(key || "").toUpperCase();
  if (!t) return false;
  if (/\b31\b/.test(t)) return true;
  if (/\b(30|35)(?:-[0-9A-Z]+)?\b/.test(t)) return true;
  return false;
}

function isExcludedFromGroupDFallback_(key) {
  const t = String(key || "").toUpperCase();
  return (
    /RAP|REGISTERED APPRENTICESHIP|WORK EXPERIENCE|GREEN CERTIFICATE|SPECIAL PROJECT|K AND E|KNOWLEDGE AND EMPLOYABILITY|LOCALLY DEVELOPED|LDC/.test(
      t
    ) || /\bCALM\b/.test(t)
  );
}

function isLikelyGroupDAdmissionSubject_(key) {
  const t = String(key || "").toUpperCase();
  if (!isSeniorHighAdmissionLevel_(t)) return false;
  if (isExcludedFromGroupDFallback_(t)) return false;
  return true;
}

function courseGroupMap_() {
  return {
    "ENGLISH 30-1": ["A"],
    "ENGLISH 30-2": ["A"],
    "ENGLISH 20-1": ["A"],
    "ENGLISH 20-2": ["A"],
    "SOCIAL STUDIES 30-1": ["A"],
    "SOCIAL STUDIES 30-2": ["A"],
    "SOCIAL STUDIES 20-1": ["A"],
    "SOCIAL STUDIES 20-2": ["A"],
    "WORLD GEOGRAPHY 30": ["A"],
    "WORLD HISTORY 30": ["A"],
    "HISTORY 30": ["A"],
    "ABORIGINAL STUDIES 30": ["A"],
    "CANADIAN STUDIES 30": ["A"],
    "PSYCHOLOGY 30": ["A"],
    "PHILOSOPHY 30": ["A"],
    "RELIGIOUS STUDIES 30": ["A"],
    "LAW 30": ["A"],
    "ECONOMICS 30": ["A"],
    "AMERICAN SIGN LANGUAGE AND DEAF CULTURE 35": ["A"],
    "ARABIC LANGUAGE AND CULTURE 30": ["A"],
    "ARABIC LANGUAGE AND CULTURE 35": ["A"],
    "BLACKFOOT LANGUAGE AND CULTURE 30": ["A"],
    "CHINESE LANGUAGE AND CULTURE 30": ["A"],
    "CHINESE LANGUAGE AND CULTURE 35": ["A"],
    "CREE LANGUAGE AND CULTURE 30": ["A"],
    "FRENCH LANGUAGE ARTS 30-1": ["A"],
    "FRENCH LANGUAGE ARTS 30-2": ["A"],
    "GERMAN LANGUAGE AND CULTURE 30": ["A"],
    "GERMAN LANGUAGE AND CULTURE 35": ["A"],
    "ITALIAN LANGUAGE AND CULTURE 30": ["A"],
    "ITALIAN LANGUAGE AND CULTURE 35": ["A"],
    "JAPANESE LANGUAGE AND CULTURE 30": ["A"],
    "JAPANESE LANGUAGE AND CULTURE 35": ["A"],
    "KOREAN LANGUAGE AND CULTURE 30": ["A"],
    "LATIN 30": ["A"],
    "LATIN LANGUAGE AND CULTURE 30": ["A"],
    "PUNJABI LANGUAGE AND CULTURE 30": ["A"],
    "RUSSIAN LANGUAGE AND CULTURE 30": ["A"],
    "SPANISH LANGUAGE AND CULTURE 30": ["A"],
    "SPANISH LANGUAGE AND CULTURE 35": ["A"],
    "UKRAINIAN LANGUAGE AND CULTURE 30": ["A"],
    "FRENCH 30": ["A"],
    "FRANCAIS 30": ["A"],
    "SPANISH 30": ["A"],
    "GERMAN 30": ["A"],
    "CHINESE 30": ["A"],
    "JAPANESE 30": ["A"],
    "MATH 30-1": ["C"],
    "MATH 30-2": ["C"],
    "MATH 20-1": ["C"],
    "MATH 20-2": ["C"],
    "MATH 31": ["C"],
    "BIOLOGY 30": ["C"],
    "BIOLOGY 20": ["C"],
    "CHEMISTRY 30": ["C"],
    "CHEMISTRY 20": ["C"],
    "PHYSICS 30": ["C"],
    "PHYSICS 20": ["C"],
    "SCIENCE 30": ["C"],
    "SCIENCE 20": ["C"],
    "CALCULUS 31": ["C"],
    "COMPUTER SCIENCE ADVANCED CTS": ["B", "C"],
    "COMPUTING SCIENCE ADVANCED CTS": ["B", "C"],
    "ART 30": ["B"],
    "ART 31": ["B"],
    "DRAMA 30": ["B"],
    "CHORAL MUSIC 30": ["B"],
    "INSTRUMENTAL MUSIC 30": ["B"],
    "GENERAL MUSIC 30": ["B"],
    "JAZZ 30": ["B"],
    "MUSIC 30": ["B"],
    "DANCE 35": ["B"],
    "PHYSICAL EDUCATION 30": ["B"],
    "RECREATION LEADERSHIP 30": ["B"],
    "COMMUNICATION TECHNOLOGY ADVANCED CTS": ["B"],
    "DESIGN STUDIES 30": ["B"],
    "ACCOUNTING 30": ["D"],
    "AGRICULTURE 30": ["D"],
    "AVIATION 30": ["D"],
    "AUTOMOTIVE SERVICE TECHNICIAN 30": ["D"],
    "BROADCASTING 30": ["D"],
    "CARPENTRY 30": ["D"],
    "CHILD DEVELOPMENT 30": ["D"],
    "COMMUNITY HEALTH 30": ["D"],
    "CONSTRUCTION 30": ["D"],
    "COSMETOLOGY 30": ["D"],
    "DRAFTING 30": ["D"],
    "EARLY LEARNING AND CHILD CARE 30": ["D"],
    "ELECTRO-TECHNOLOGIES 30": ["D"],
    "ENERGY AND MINES 30": ["D"],
    "ENTREPRENEURSHIP 30": ["D"],
    "ESTHETICS 30": ["D"],
    "FABRICATION 30": ["D"],
    "FASHION STUDIES 30": ["D"],
    "FINANCIAL MANAGEMENT 30": ["D"],
    "FOOD STUDIES 30": ["D"],
    "FOODS 30": ["D"],
    "FORESTRY 30": ["D"],
    "HEALTH CARE AIDE 30": ["D"],
    "HEAVY EQUIPMENT 30": ["D"],
    "HORTICULTURE 30": ["D"],
    "MARKETING 30": ["D"],
    "MECHANICS 30": ["D"],
    "MULTIMEDIA 30": ["D"],
    "NETWORK SYSTEMS 30": ["D"],
    "OUTDOOR PURSUITS 30": ["D"],
    "PHOTOGRAPHY 30": ["D"],
    "PLUMBING 30": ["D"],
    "ROBOTICS 30": ["D"],
    "TOURISM 30": ["D"],
    "WORKPLACE SAFETY 30": ["D"],
    "WELDING 30": ["D"],
  };
}

function parseElectiveQty(text) {
  const t = String(text || "").trim();
  if (!t) return null;
  if (/^(See Degree|Refer to Degree|Check Notes)$/i.test(t)) return null;
  if (/^0$/i.test(t)) return 0;
  const word = t.toLowerCase();
  const map = {
    one: 1,
    two: 2,
    three: 3,
    four: 4,
    five: 5,
    six: 6,
    seven: 7,
    eight: 8,
    nine: 9,
    ten: 10,
  };
  if (map[word] !== undefined) return map[word];
  const n = Number(t);
  return isFinite(n) ? n : null;
}

function parseAllowedGroups(poolText) {
  const t = String(poolText || "").toUpperCase();
  const m = t.match(/\b[ABCD]\b/g);
  if (!m || !m.length) return ["A", "B", "C", "D"];
  return unique(m);
}

function parseElectiveRules_(requirementTypeText) {
  const rules = { maxByGroup: {}, minFromSets: [], minMark: NaN };
  const text = String(requirementTypeText || "");
  if (!text) return rules;

  let m;
  const countToken = "(one|two|three|four|five|six|seven|eight|nine|ten|\\d+)";
  const applyMaxRule = (groupRaw, countRaw) => {
    const count = parseCountToken_(countRaw);
    const group = String(groupRaw || "").toUpperCase();
    if (!isFinite(count) || count < 0 || !group) return;
    if (rules.maxByGroup[group] === undefined) rules.maxByGroup[group] = count;
    else rules.maxByGroup[group] = Math.min(rules.maxByGroup[group], count);
  };

  // Examples:
  // - "max two Group B"
  // - "maximum of two Group B subjects"
  // - "at most 2 option C"
  // - "up to 1 admission subject from group D"
  const maxReForward = new RegExp(
    "(?:max(?:imum)?(?:\\s+of)?|at\\s+most|up\\s+to)\\s+" +
      countToken +
      "\\s+(?:(?:admission\\s+)?(?:subjects?|courses?|electives?)\\s+from\\s+|from\\s+)?" +
      "(?:groups?|options?)\\s+([abcd])(?:'s)?(?:\\s+(?:subjects?|courses?|electives?))?",
    "ig"
  );
  while ((m = maxReForward.exec(text))) {
    applyMaxRule(m[2], m[1]);
  }

  // Also support reversed phrasing:
  // - "Group B maximum of two subjects"
  // - "Option C max 1"
  const maxReReverse = new RegExp(
    "(?:groups?|options?)\\s+([abcd])(?:'s)?(?:\\s+(?:subjects?|courses?|electives?))?" +
      "\\s*[:,-]?\\s*(?:max(?:imum)?(?:\\s+of)?|at\\s+most|up\\s+to)\\s+" +
      countToken,
    "ig"
  );
  while ((m = maxReReverse.exec(text))) {
    applyMaxRule(m[1], m[2]);
  }

  const minCandidates = [];
  const minRe = /((?:one|two|three|four|five|six|seven|eight|nine|ten|\d+))\s+admission\s+subjects?\s+must\s+be\s+from\s+groups?\s+([abcd](?:\s*(?:\/|or|,)\s*[abcd])*)/ig;
  while ((m = minRe.exec(text))) {
    const count = parseCountToken_(m[1]);
    const groups = parseGroupsFromText_(m[2]);
    if (isFinite(count) && count > 0 && groups.length) minCandidates.push({ count, groups });
  }

  const additionalRe = /((?:one|two|three|four|five|six|seven|eight|nine|ten|\d+))\s+(?:more|additional(?:\s+admission\s+subject)?)\s+from\s+groups?\s+([abcd](?:\s*(?:\/|or|,)\s*[abcd])*)/ig;
  while ((m = additionalRe.exec(text))) {
    const count = parseCountToken_(m[1]);
    const groups = parseGroupsFromText_(m[2]);
    if (isFinite(count) && count > 0 && groups.length) minCandidates.push({ count, groups });
  }

  const seen = {};
  minCandidates.forEach((rule) => {
    const key = `${rule.count}||${rule.groups.join("/")}`;
    if (seen[key]) return;
    seen[key] = true;
    rules.minFromSets.push(rule);
  });

  const markRe = /each\s+subject\s+must\s+be\s*>=?\s*(\d+)/i;
  const markMatch = markRe.exec(text);
  if (markMatch) {
    const minMark = toNumber(markMatch[1]);
    if (isFinite(minMark)) rules.minMark = minMark;
  }

  return rules;
}

function formatElectiveRuleSummary_(rules) {
  if (!rules) return "";
  const parts = [];
  const maxByGroup = rules.maxByGroup || {};
  Object.keys(maxByGroup)
    .sort()
    .forEach((group) => {
      parts.push(`max ${maxByGroup[group]} from Group ${group}`);
    });

  (rules.minFromSets || []).forEach((rule) => {
    const groups = (rule.groups || []).join("/");
    parts.push(`need ${rule.count} from Groups ${groups}`);
  });

  if (isFinite(rules.minMark)) parts.push(`subject marks >= ${rules.minMark}`);
  return parts.join("; ");
}

function runElectiveRuleSelfTest_() {
  const parsed = parseElectiveRules_("Maximum of two Group B subjects; at most 1 option C");
  if ((parsed.maxByGroup || {}).B !== 2) throw new Error("Elective rule parse failed: expected max Group B = 2");
  if ((parsed.maxByGroup || {}).C !== 1) throw new Error("Elective rule parse failed: expected max Group C = 1");

  const parsedVariants = parseElectiveRules_(
    "Maximum two from Group B electives; Options C: max 1 course; up to 1 from Group D's courses"
  );
  if ((parsedVariants.maxByGroup || {}).B !== 2) throw new Error("Variant parse failed: expected max Group B = 2");
  if ((parsedVariants.maxByGroup || {}).C !== 1) throw new Error("Variant parse failed: expected max Group C = 1");
  if ((parsedVariants.maxByGroup || {}).D !== 1) throw new Error("Variant parse failed: expected max Group D = 1");

  const candidates = [
    { group: "B", mark: 92, key: "B1", sourceKey: "B1" },
    { group: "B", mark: 91, key: "B2", sourceKey: "B2" },
    { group: "B", mark: 90, key: "B3", sourceKey: "B3" },
    { group: "A", mark: 86, key: "A1", sourceKey: "A1" },
  ];
  const selected = selectBestElectives_(candidates, 3, parsed);
  const bCount = selected.filter((x) => String(x.group || "").toUpperCase() === "B").length;
  if (selected.length !== 3) throw new Error(`Elective selection failed: expected 3 selected, got ${selected.length}`);
  if (bCount > 2) throw new Error(`Elective cap failed: expected max 2 from Group B, got ${bCount}`);
}

function parseCountToken_(token) {
  const t = String(token || "").trim().toLowerCase();
  if (!t) return NaN;
  const map = {
    one: 1,
    two: 2,
    three: 3,
    four: 4,
    five: 5,
    six: 6,
    seven: 7,
    eight: 8,
    nine: 9,
    ten: 10,
  };
  if (map[t] !== undefined) return map[t];
  return toNumber(t);
}

function parseGroupsFromText_(text) {
  const m = String(text || "").toUpperCase().match(/[ABCD]/g);
  return m ? unique(m) : [];
}

function collectRequiredMarks(evals) {
  const out = [];
  const seen = {};
  const pushRequired = (label, mark, key) => {
    const k = String(key || "").trim().toUpperCase();
    const dedupeKey = k ? `KEY:${k}` : `LABEL:${String(label || "").trim()}`;
    if (!isFinite(mark) || !dedupeKey) return;
    if (seen[dedupeKey]) return;
    seen[dedupeKey] = true;
    out.push({ label, mark, key: k });
  };

  (evals || []).forEach((ev) => {
    if (!ev) return;
    if (ev.kind === "any" && ev.best) pushRequired(ev.best.course, ev.best.mark, ev.best.key);

    if (ev.kind === "all") {
      // Science kind=all provides checks; AND-required subjects provide parts.
      if (ev.checks && ev.checks.length) {
        ev.checks.forEach((c) => {
          if (c && c.ok === true && isFinite(c.mark)) pushRequired(c.course, c.mark, c.key);
        });
      } else if (ev.parts && ev.parts.length) {
        ev.parts.forEach((p) => {
          if (!p || !p.best) return;
          const best = p.best;
          if (best && isFinite(best.mark)) pushRequired(best.course, best.mark, best.key);
        });
      }
    }

    if (ev.kind === "all_plus_any") {
      (ev.checksAll || []).forEach((c) => {
        if (c && c.ok === true && isFinite(c.mark)) pushRequired(c.course, c.mark, c.key);
      });
      if (ev.anyOk === true && ev.bestAny && isFinite(ev.bestAny.mark)) {
        pushRequired(ev.bestAny.course, ev.bestAny.mark, ev.bestAny.key);
      }
    }

    if (ev.kind === "kof") {
      (ev.selected || []).forEach((s) => {
        if (!s) return;
        const label = String(s.course || "").trim();
        const mark = s.mark;
        if (!label || !isFinite(mark)) return;
        pushRequired(label, mark, s.key);
      });
    }
  });
  return out;
}

function countRequiredSlots(evals) {
  let n = 0;
  (evals || []).forEach((ev) => {
    if (!ev) return;
    if (ev.kind === "any") n += 1;
    if (ev.kind === "all") n += (ev.parts ? ev.parts.length : (ev.courses || []).length);
    if (ev.kind === "kof") n += Math.max(0, Math.round(ev.k || 0));
    if (ev.kind === "all_plus_any") n += (ev.allCourses || []).length + 1;
  });
  return n;
}

function splitByAnd_(text) {
  const t = String(text || "").trim();
  if (!t) return [];
  // Avoid splitting "and/or".
  const parts = t.split(/\s+and\s+/i).map((x) => x.trim()).filter(Boolean);
  return parts.length ? parts : [t];
}

function parseScienceRequirementText_(rawText) {
  const t0 = String(rawText || "").trim();
  if (!t0) return { kind: "any", courses: [] };

  let k = null;
  let t = t0;
  const m = /^\s*(Two|2)\s+of\b/i.exec(t);
  if (m) {
    k = 2;
    t = t.replace(/^\s*(Two|2)\s+of\b/i, "").trim();
  }

  // Normalize separators.
  t = t.replace(/;/g, ",").replace(/\s+/g, " ");

  const parts = t
    .split(",")
    .map((x) => x.trim())
    .filter(Boolean);

  const courses = unique(
    parts.map((p) => {
      const q = p.replace(/\s+/g, " ");
      if (/^Bio\s*30$/i.test(q)) return "Biology 30";
      if (/^Chem\s*30$/i.test(q)) return "Chemistry 30";
      if (/^Phys\s*30$/i.test(q)) return "Physics 30";
      if (/^Sci\s*30$/i.test(q)) return "Science 30";
      if (/(?:math|mathematics)\s*31\b/i.test(q)) return "Math 31";
      if (/recreation leadership/i.test(q)) return "Recreation Leadership 30";
      if (/(computing|computer)\s+science\s+advanced\s+cts/i.test(q)) return "Computer Science Advanced CTS";
      return q;
    })
  );

  if (k !== null) return { kind: "kof", k, courses };
  return { kind: "any", courses };
}

function computeStudentAverage(opts) {
  const { requiredItems, electives, allowedGroups, electiveNeeded, totalNeeded, electiveRules } = opts;

  const reqItems = (requiredItems || [])
    .filter((x) => x && isFinite(x.mark))
    .map((x) => ({
      label: String(x.label || "").trim(),
      mark: Number(x.mark),
      key: String(x.key || "").trim().toUpperCase(),
    }));

  const requiredCount = isFinite(totalNeeded)
    ? Math.max(0, Math.round(totalNeeded))
    : reqItems.length + Math.max(0, electiveNeeded || 0);

  const coreUsedKeys = new Set(reqItems.map((x) => x.key).filter(Boolean));
  const allowed = new Set((allowedGroups || ["A", "B", "C", "D"]).map((g) => String(g).toUpperCase()));
  const minElectiveMark = electiveRules && isFinite(electiveRules.minMark) ? Number(electiveRules.minMark) : NaN;

  const usableElectives = (electives || [])
    .filter((e) => e && isFinite(e.mark))
    .map((e, idx) => ({
      name: String(e.name || "").trim(),
      group: String(e.group || "").trim().toUpperCase(),
      mark: Number(e.mark),
      source: String(e.source || "").trim().toLowerCase(),
      key: String(e.key || "").trim().toUpperCase(),
      sourceKey: String(e.sourceKey || `SRC_${idx}`).trim(),
    }))
    .filter((e) => allowed.has(e.group))
    .filter((e) => (!e.key ? true : !coreUsedKeys.has(e.key)))
    .filter((e) => (isFinite(minElectiveMark) ? e.mark >= minElectiveMark : true));

  const selected = selectBestElectives_(
    usableElectives,
    Math.max(0, Math.round(toNumber(electiveNeeded) || 0)),
    electiveRules
  );

  const usedCount = reqItems.length + selected.length;
  const missingCount = Math.max(0, requiredCount - usedCount);

  if (requiredCount === 0) {
    return {
      value: NaN,
      requiredCount: 0,
      usedCount: 0,
      missingCount: 0,
      sumUsed: 0,
      usedRequired: [],
      selectedElectives: [],
      usableElectives: [],
    };
  }

  const sumUsed = reqItems.reduce((s, x) => s + x.mark, 0) + selected.reduce((s, e) => s + e.mark, 0);
  const value = usedCount ? sumUsed / usedCount : NaN;

  return {
    value,
    requiredCount,
    usedCount,
    missingCount,
    sumUsed,
    usedRequired: reqItems.map((x) => ({ label: x.label, mark: x.mark, key: x.key })),
    selectedElectives: selected.map((e) => ({ group: e.group, mark: e.mark, name: e.name, key: e.key })),
    usableElectives: usableElectives.map((e) => ({ group: e.group, mark: e.mark, name: e.name, key: e.key })),
  };
}

function selectBestElectives_(candidates, neededCount, rules) {
  const needed = Math.max(0, Math.round(toNumber(neededCount) || 0));
  const sorted = (candidates || []).slice().sort((a, b) => b.mark - a.mark);

  if (needed === 0) return [];

  for (let target = needed; target >= 1; target--) {
    const best = pickBestElectiveSet_(sorted, target, rules || {});
    if (best) return best;
  }

  // Graceful fallback: if note-derived constraints are impossible, still use the best available electives.
  for (let target = needed; target >= 0; target--) {
    const best = pickBestElectiveSet_(sorted, target, { maxByGroup: {}, minFromSets: [] });
    if (best) return best;
  }

  return [];
}

function pickBestElectiveSet_(candidates, targetCount, rules) {
  const target = Math.max(0, Math.round(toNumber(targetCount) || 0));
  if (target === 0) return [];

  const maxByGroup = (rules && rules.maxByGroup) || {};
  const minFromSets = (rules && rules.minFromSets) || [];
  if (minFromSets.some((r) => (toNumber(r.count) || 0) > target)) return null;

  let best = null;
  let bestSum = -Infinity;

  const chosen = [];
  const usedUnits = {};
  const groupCounts = {};

  const meetsMinGroupRules = () =>
    minFromSets.every((rule) => {
      const groups = rule.groups || [];
      const minCount = Math.max(0, Math.round(toNumber(rule.count) || 0));
      if (!groups.length || minCount === 0) return true;
      let count = 0;
      groups.forEach((g) => {
        const group = String(g || "").toUpperCase();
        count += groupCounts[group] || 0;
      });
      return count >= minCount;
    });

  function dfs(index, sum) {
    const needed = target - chosen.length;
    if (needed === 0) {
      if (!meetsMinGroupRules()) return;
      if (sum > bestSum) {
        best = chosen.slice();
        bestSum = sum;
      }
      return;
    }

    if (index >= candidates.length) return;
    if (candidates.length - index < needed) return;

    const candidate = candidates[index];
    const group = String(candidate.group || "").toUpperCase();
    const maxForGroup = toNumber(maxByGroup[group]);
    const unitKey = candidate.key ? `KEY:${candidate.key}` : `SRC:${candidate.sourceKey}`;

    const canUseUnit = !usedUnits[unitKey];
    const canUseGroup = !isFinite(maxForGroup) || (groupCounts[group] || 0) < maxForGroup;

    if (canUseUnit && canUseGroup) {
      chosen.push(candidate);
      usedUnits[unitKey] = true;
      groupCounts[group] = (groupCounts[group] || 0) + 1;
      dfs(index + 1, sum + candidate.mark);
      chosen.pop();
      groupCounts[group] = groupCounts[group] - 1;
      if (!groupCounts[group]) delete groupCounts[group];
      delete usedUnits[unitKey];
    }

    dfs(index + 1, sum);
  }

  dfs(0, 0);
  return best;
}

function normalizeCompetitive(text) {
  const t = String(text || "").trim();
  if (!t) return "";
  if (/^Minimum Only$/i.test(t)) return "";
  if (/^(See Degree|Refer to Degree)$/i.test(t)) return "";
  return t;
}

function buildNotes_(notes, advisories) {
  const parts = [];
  // Put advisories (assessment/placement) first, as requested.
  if (advisories && advisories.length) parts.push(advisories.join(" | "));
  if (notes && notes.length) parts.push(notes.join(" | "));
  return parts.join(" | ");
}

function title(s) {
  const t = String(s || "");
  return t.charAt(0).toUpperCase() + t.slice(1);
}

function boolCmp(a, b) {
  const ax = a ? 1 : 0;
  const bx = b ? 1 : 0;
  return ax - bx;
}

function applyCompetitiveHighlight_(sheet, values) {
  if (!values || values.length < 2) return;
  const header = (values[0] || []).map((x) => String(x || "").trim().toLowerCase());
  const compIdx = header.indexOf("competitive guidance");
  if (compIdx < 0) return;

  const n = values.length - 1;
  const yellow = "#fff2cc";
  const white = null; // keep default background

  const bg = [];
  for (let i = 1; i < values.length; i++) {
    const competitive = String(values[i][compIdx] || "").trim();
    const color = competitive ? yellow : white;
    bg.push([color, color]);
  }

  // Apply only to Min Avg + Student Avg cells (rows 2..)
  sheet.getRange(2, 4, n, 2).setBackgrounds(bg);
}

function isUncheckable_(notesText) {
  const t = String(notesText || "").toLowerCase();
  if (!t.trim()) return false;
  // These indicate we don't have enough structured info to evaluate eligibility from marks alone.
  return (
    t.includes("see degree") ||
    t.includes("refer to degree") ||
    t.includes("requirement unspecified")
  );
}

function formatAvgUsed_(avg) {
  if (!avg) return "";
  const parts = [];
  (avg.usedRequired || []).forEach((x) => {
    if (!x) return;
    const label = String(x.label || "").trim();
    const mark = isFinite(x.mark) ? Number(x.mark) : NaN;
    if (!label || !isFinite(mark)) return;
    parts.push(`${label}=${mark}`);
  });
  (avg.selectedElectives || []).forEach((e) => {
    if (!e) return;
    const g = String(e.group || "").trim();
    const name = String(e.name || "").trim();
    const mark = isFinite(e.mark) ? Number(e.mark) : NaN;
    if (!g || !isFinite(mark)) return;
    parts.push(`Elective ${g}${name ? ` (${name})` : ""}=${mark}`);
  });
  return parts.join(", ");
}

function appendDatasetNotes_(requirementTypeText, notes, advisories) {
  const t = String(requirementTypeText || "").trim();
  if (!t) return;
  const lower = t.toLowerCase();

  const m = /^notes?\s*:\s*(.+)$/i.exec(t);
  if (m && m[1] && m[1].trim()) notes.push(m[1].trim());

  const specialKeywords = [
    "audition",
    "portfolio",
    "casper",
    "interview",
    "questionnaire",
  ];
  const found = specialKeywords.filter((k) => lower.includes(k));
  if (found.length) {
    advisories.push(`Other requirements: ${unique(found).join(", ")}`);
  }
}
