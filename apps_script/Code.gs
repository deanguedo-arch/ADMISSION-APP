/**
 * Alberta Admissions Checker (MVP)
 *
 * Expected tabs:
 * - Programs: canonical CSV imported (headers in row 1)
 * - Student:
 *   - Rows 3+ (A:B): Course / Mark (for named courses like English 30-1, Math 30-2, Biology 30, etc.)
 *   - Rows 3-12 (D:F): Elective (optional name) / Group (A/B/C/D) / Mark (up to 10 electives)
 * - Results: output written here
 */

function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu("Admissions Checker")
    .addItem("Check Eligibility", "runEligibility")
    .addToUi();
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
  const electivesRows = studentSheet.getRange(2, 4, 11, 3).getValues(); // D2:F12 (headers usually in row 1)
  const electives = buildElectives(electivesRows);

  if (Object.keys(courseMap).length === 0 && electives.length === 0) {
    throw new Error("No student data found. Enter Course+Mark in Student!A2:B and/or electives in Student!D2:F12.");
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

    const competitiveGuidance = normalizeCompetitive(getStr(r, idx, "Competitive_Final"));
    appendDatasetNotes_(r, idx, notes, advisories);

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
        const usable = electives
          .filter((e) => allowedGroups.includes(e.group))
          .sort((a, b) => b.mark - a.mark);
        const have = usable.map((e) => `${e.group}=${e.mark}`).join(", ");

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
          `Need ${missingElectivesForAvg} more elective mark(s) for average (allowed groups: ${allowedGroups.join("/")})` +
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
        return { course: c, ok: false, reason: `${c} mark too low: ${best.mark} < ${minMark}`, mark: best.mark };
      }
      return { course: c, ok: true, mark: best.mark };
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
        return { course: c, ok: false, reason: `${c} mark too low: ${best.mark} < ${minMark}`, mark: best.mark };
      }
      return { course: c, ok: true, mark: best.mark };
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
      candidates.push({ course: c, mark: best.mark });
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
      if (!best || m > best.mark) best = { course: shownCourse, mark: m };
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

function buildElectives(rows) {
  // rows: [name, group, mark]
  const electives = [];
  rows.forEach(([name, group, mark]) => {
    const g = String(group || "").trim().toUpperCase();
    const m = toNumber(mark);
    if (!["A", "B", "C", "D"].includes(g)) return;
    if (!isFinite(m)) return;
    electives.push({ name: String(name || "").trim(), group: g, mark: m });
  });
  return electives;
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

function collectRequiredMarks(evals) {
  const out = [];
  (evals || []).forEach((ev) => {
    if (!ev) return;
    if (ev.kind === "any" && ev.best) out.push({ label: ev.best.course, mark: ev.best.mark });

    if (ev.kind === "all") {
      // Science kind=all provides checks; AND-required subjects provide parts.
      if (ev.checks && ev.checks.length) {
        ev.checks.forEach((c) => {
          if (c && c.ok === true && isFinite(c.mark)) out.push({ label: c.course, mark: c.mark });
        });
      } else if (ev.parts && ev.parts.length) {
        ev.parts.forEach((p) => {
          if (!p || !p.best) return;
          const best = p.best;
          if (best && isFinite(best.mark)) out.push({ label: best.course, mark: best.mark });
        });
      }
    }

    if (ev.kind === "all_plus_any") {
      (ev.checksAll || []).forEach((c) => {
        if (c && c.ok === true && isFinite(c.mark)) out.push({ label: c.course, mark: c.mark });
      });
      if (ev.anyOk === true && ev.bestAny && isFinite(ev.bestAny.mark)) {
        out.push({ label: ev.bestAny.course, mark: ev.bestAny.mark });
      }
    }

    if (ev.kind === "kof") {
      (ev.selected || []).forEach((s) => {
        if (!s) return;
        const label = String(s.course || "").trim();
        const mark = s.mark;
        if (!label || !isFinite(mark)) return;
        out.push({ label, mark });
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
      return q;
    })
  );

  if (k !== null) return { kind: "kof", k, courses };
  return { kind: "any", courses };
}

function computeStudentAverage(opts) {
  const { requiredItems, electives, allowedGroups, electiveNeeded, totalNeeded } = opts;

  const reqItems = (requiredItems || []).filter((x) => x && isFinite(x.mark));
  const requiredCount = isFinite(totalNeeded) ? Math.max(0, Math.round(totalNeeded)) : reqItems.length + Math.max(0, electiveNeeded || 0);

  const allowed = new Set((allowedGroups || ["A", "B", "C", "D"]).map(String));
  const usableElectives = (electives || []).filter((e) => allowed.has(e.group) && isFinite(e.mark));
  usableElectives.sort((a, b) => b.mark - a.mark);

  const selected = usableElectives.slice(0, Math.max(0, electiveNeeded || 0));
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
    usedRequired: reqItems.map((x) => ({ label: x.label, mark: x.mark })),
    selectedElectives: selected.map((e) => ({ group: e.group, mark: e.mark, name: e.name })),
  };
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

function appendDatasetNotes_(row, idx, notes, advisories) {
  const reqType = getStr(row, idx, "Requirement_Type");
  if (!reqType) return;

  const t = String(reqType).trim();
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
