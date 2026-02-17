/**
 * Admissions Checker Eligibility Engine + Domain Helpers
 */

/**
 * Admissions Checker Eligibility Engine Orchestration
 */

function evaluateProgramsForStudent_(opts) {
  const programsRange = (opts && opts.programsRange) || [];
  const courseMap = (opts && opts.courseMap) || {};
  const manualElectives = (opts && opts.manualElectives) || [];
  const avgRules = (opts && opts.avgRules) || { byKey: {}, byInstitution: {} };
  const electiveRuleOverrides = (opts && opts.electiveRuleOverrides) || { byKey: {}, byInstitution: {} };

  if (!programsRange || programsRange.length < 2) {
    throw new Error("Programs tab is empty. Import/sync the dataset into the Programs tab first.");
  }
  if (Object.keys(courseMap).length === 0 && manualElectives.length === 0) {
    throw new Error("No student data found. Add at least one course mark.");
  }

  const autoElectives = buildAutoElectivesFromCourseMap_(courseMap);
  const electives = mergeElectiveCandidates_(autoElectives, manualElectives);

  const header = programsRange[0].map(String);
  const rows = programsRange.slice(1);
  const idx = indexHeader_(header);
  requireProgramsColumns_(idx);

  const rowRecords = [];
  const detailsByKey = {};
  const rowKeyCounts = {};

  rows.forEach((r, rowIndex) => {
    const institution = getStr_(r, idx, "Institution");
    const program = getStr_(r, idx, "Program");
    const credential = getStr_(r, idx, "Credential_Type");
    const status = getStr_(r, idx, "Status");
    const programUrl = getStr_(r, idx, "Program_URL");

    if (!institution || !program) return;
    if (status && status.toLowerCase() !== "active") return;

    const reasons = [];
    const notes = [];
    const advisories = [];

    const requirementType = getStr_(r, idx, "Requirement_Type");
    const requirementTypeOverride = resolveElectiveRuleOverrideText_(
      electiveRuleOverrides,
      institution,
      program
    );
    const requirementTypeEffective = combineRuleText_(requirementType, requirementTypeOverride);
    const competitiveGuidance = normalizeCompetitive_(getStr_(r, idx, "Competitive_Final"));
    appendDatasetNotes_(requirementTypeEffective, notes, advisories);

    const englishReq = unifyEnglishReq_(r, idx);
    const englishMin = toNumber_(unifyEnglishMin_(r, idx));
    const englishEval = evalSubject_(courseMap, "english", englishReq, englishMin);
    appendEval_(englishEval, "English", reasons, notes, advisories);

    const mathReq = getStr_(r, idx, "Math_Req");
    const mathMin = toNumber_(getStr_(r, idx, "Math_Min"));
    const mathEval = evalSubject_(courseMap, "math", mathReq, mathMin);
    appendEval_(mathEval, "Math", reasons, notes, advisories);

    const socialReq = getStr_(r, idx, "Social_Req");
    const socialMin = toNumber_(getStr_(r, idx, "Social_Min"));
    const socialEval = evalSubject_(courseMap, "social", socialReq, socialMin);
    appendEval_(socialEval, "Social Studies", reasons, notes, advisories);

    const sciMin = toNumber_(getStr_(r, idx, "Science_Min"));
    const scienceReq = buildScienceReq_(r, idx);
    const scienceEval = evalScience_(courseMap, scienceReq, sciMin);
    appendEval_(scienceEval, "Science", reasons, notes, advisories);

    const electiveQty = getStr_(r, idx, "Elective_Qty");
    const electiveNeedParsed = parseElectiveQty_(electiveQty);
    const electivePool = getStr_(r, idx, "Elective_Pool");
    const allowedGroups = parseAllowedGroups_(electivePool);
    const electiveRules = parseElectiveRules_(requirementTypeEffective);

    const avgMin = toNumber_(getStr_(r, idx, "Min_Avg_Final"));
    const avgTotalFromData = toNumber_(getStr_(r, idx, "Avg_Total"));
    const requiredMarks = collectRequiredMarks_([englishEval, mathEval, socialEval, scienceEval]);
    const requiredSlots = countRequiredSlots_([englishEval, mathEval, socialEval, scienceEval]);
    const assumedTarget = 5;
    const avgTotal = resolveAvgTotal_({
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

    const avg = computeStudentAverage_({
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

        const usedRequiredCount = (avg.usedRequired || []).length;
        const missingRequiredSlots = Math.max(0, requiredSlots - usedRequiredCount);
        let needHint = "";
        if (missingRequiredSlots === 0 && isFinite(avgTotal) && avgTotal > 0 && isFinite(avg.sumUsed)) {
          const remaining = missingElectivesForAvg;
          const needTotal = avgMin * avgTotal - avg.sumUsed;
          const needAvg = remaining > 0 ? needTotal / remaining : NaN;
          if (isFinite(needAvg)) {
            const clamped = Math.max(0, needAvg);
            needHint =
              `; to meet ${avgMin}, remaining elective(s) need avg >= ${clamped.toFixed(1)}` +
              (clamped > 100 ? " (not possible)" : "");
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

    const rowBaseKey = makeProgramKey_(institution, program, credential, r);
    const programKey = claimProgramKey_(rowBaseKey, rowKeyCounts);
    const requirementSummaries = [
      summarizeEvalForWebDetails_("English", englishEval),
      summarizeEvalForWebDetails_("Math", mathEval),
      summarizeEvalForWebDetails_("Social Studies", socialEval),
      summarizeEvalForWebDetails_("Science", scienceEval),
    ];
    const studentAvgValue =
      isFinite(avgMin) && isFinite(avgTotal) && avgTotal > 0 && avg.usedCount >= avgTotal && isFinite(avg.value)
        ? Number(avg.value.toFixed(1))
        : "";
    const missingText = (reasons || []).join(" | ");
    const notesText = buildNotes_(notes, advisories);

    const row = [
      institution,
      program,
      credential,
      isFinite(avgMin) ? avgMin : "",
      studentAvgValue,
      avgTotal || "",
      formatAvgUsed_(avg),
      competitiveGuidance,
      missingText,
      notesText,
    ];

    rowRecords.push({
      key: programKey,
      row,
      missing: missingText,
      notes: notesText,
      rowIndex,
    });

    detailsByKey[programKey] = buildProgramDetailsForWeb_({
      programKey,
      institution,
      program,
      credential,
      programUrl,
      competitiveGuidance,
      requirementTypeEffective,
      requirementSummaries,
      avgMin,
      studentAvg: studentAvgValue,
      avgTotal,
      avg,
      electiveNeededForAvg,
      allowedGroups,
      electiveRules,
      reasons,
      notes,
      advisories,
    });
  });

  rowRecords.sort((a, b) => {
    const ar = a.row || [];
    const br = b.row || [];
    const i = String(ar[0]).localeCompare(String(br[0]));
    if (i !== 0) return i;
    const p = String(ar[1]).localeCompare(String(br[1]));
    if (p !== 0) return p;
    return String(ar[2]).localeCompare(String(br[2]));
  });

  const body = rowRecords.map((x) => x.row);
  const finalOut = [RESULTS_HEADER_ROW.slice()].concat(body);
  const eligibleRecords = rowRecords.filter((r) => {
    const missing = String(r.missing || "").trim();
    const notes = String(r.notes || "").trim();
    return missing === "" && !isUncheckable_(notes);
  });
  const ineligibleRecords = rowRecords.filter((r) => String(r.missing || "").trim() !== "");
  const uncheckableRecords = rowRecords.filter((r) => {
    const missing = String(r.missing || "").trim();
    const notes = String(r.notes || "").trim();
    return missing === "" && isUncheckable_(notes);
  });

  const eligibleRows = [RESULTS_HEADER_ROW.slice()].concat(eligibleRecords.map((r) => r.row));
  const ineligibleRows = [RESULTS_HEADER_ROW.slice()].concat(ineligibleRecords.map((r) => r.row));
  const uncheckableRows = [RESULTS_HEADER_ROW.slice()].concat(uncheckableRecords.map((r) => r.row));

  return {
    finalOut,
    eligibleRows,
    ineligibleRows,
    uncheckableRows,
    rowKeysByView: {
      all: rowRecords.map((r) => r.key),
      eligible: eligibleRecords.map((r) => r.key),
      ineligible: ineligibleRecords.map((r) => r.key),
      uncheckable: uncheckableRecords.map((r) => r.key),
    },
    detailsByKey,
  };
}

function makeProgramKey_(institution, program, credential, row) {
  const parts = [institution, program, credential]
    .map((x) => slugProgramKeyPart_(x))
    .filter(Boolean);
  const base = parts.length ? parts.join("__") : "program";

  const rowSignature = (row || [])
    .map((x) => String(x === null || x === undefined ? "" : x).trim())
    .join("|");
  const fingerprint = `${institution || ""}||${program || ""}||${credential || ""}||${rowSignature}`;

  const digest = Utilities.base64EncodeWebSafe(
    Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, fingerprint)
  )
    .replace(/=+$/g, "")
    .toLowerCase();

  return `${base}_${digest.slice(0, 12)}`;
}

function slugProgramKeyPart_(value) {
  return String(value || "")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .slice(0, 60);
}

function claimProgramKey_(baseKey, counts) {
  const map = counts || {};
  const base = String(baseKey || "program").trim() || "program";
  const n = (map[base] || 0) + 1;
  map[base] = n;
  return n === 1 ? base : `${base}_${n}`;
}

function summarizeEvalForWebDetails_(label, ev) {
  const out = {
    label: String(label || "").trim(),
    status: "not_required",
    requirement: "Not required",
    minMark: "",
    matched: "",
    issues: [],
  };
  if (!ev || ev.kind === "none") return out;
  if (isFinite(ev.minMark) && ev.minMark > 0) out.minMark = Number(ev.minMark);

  if (ev.kind === "unknown") {
    out.status = "unknown";
    out.requirement = String(ev.reason || "See degree").trim();
    return out;
  }
  if (ev.kind === "assessment") {
    out.status = "assessment";
    out.requirement = String(ev.reason || "Assessment/placement required").trim();
    return out;
  }

  if (ev.kind === "any") {
    const courses = ev.courses || [];
    out.requirement = courses.length ? courses.join(" OR ") : "Required";
    if (!ev.best) {
      out.status = "missing";
      if (courses.length) out.issues.push(`Missing one of: ${courses.join(" OR ")}`);
      return out;
    }
    out.matched = `${ev.best.course}=${ev.best.mark}`;
    if (isFinite(ev.minMark) && ev.minMark > 0 && ev.best.mark < ev.minMark) {
      out.status = "low_mark";
      out.issues.push(`${ev.best.course}=${ev.best.mark} < ${ev.minMark}`);
      return out;
    }
    out.status = "met";
    return out;
  }

  if (ev.kind === "all") {
    const checks = ev.checks || [];
    if (checks.length) {
      out.requirement = (ev.courses || []).join(" + ");
      const matched = [];
      checks.forEach((c) => {
        if (c && c.ok === true && isFinite(c.mark)) matched.push(`${c.course}=${c.mark}`);
        else if (c && c.reason) out.issues.push(c.reason);
      });
      out.matched = matched.join(", ");
      out.status = classifyEvalIssuesForWeb_(out.issues);
      return out;
    }

    const parts = ev.parts || [];
    out.requirement = parts
      .map((p) => ((p && p.courses && p.courses.length) ? p.courses.join(" OR ") : "Required"))
      .join(" + ");
    const matched = [];
    parts.forEach((p) => {
      if (!p || !p.best) {
        const courses = (p && p.courses) || [];
        if (courses.length) out.issues.push(`Missing one of: ${courses.join(" OR ")}`);
        return;
      }
      matched.push(`${p.best.course}=${p.best.mark}`);
      if (isFinite(ev.minMark) && ev.minMark > 0 && p.best.mark < ev.minMark) {
        out.issues.push(`${p.best.course}=${p.best.mark} < ${ev.minMark}`);
      }
    });
    out.matched = matched.join(", ");
    out.status = classifyEvalIssuesForWeb_(out.issues);
    return out;
  }

  if (ev.kind === "all_plus_any") {
    const allCourses = ev.allCourses || [];
    const anyCourses = ev.anyCourses || [];
    out.requirement = `${allCourses.join(" + ")} + one of (${anyCourses.join(" OR ")})`;
    const matched = [];
    (ev.checksAll || []).forEach((c) => {
      if (c && c.ok === true && isFinite(c.mark)) matched.push(`${c.course}=${c.mark}`);
      else if (c && c.reason) out.issues.push(c.reason);
    });
    if (ev.bestAny && ev.anyOk === true && isFinite(ev.bestAny.mark)) {
      matched.push(`${ev.bestAny.course}=${ev.bestAny.mark}`);
    } else if (ev.anyReason) {
      out.issues.push(ev.anyReason);
    }
    out.matched = matched.join(", ");
    out.status = classifyEvalIssuesForWeb_(out.issues);
    return out;
  }

  if (ev.kind === "kof") {
    const courses = ev.courses || [];
    out.requirement = `Need ${ev.k} of: ${courses.join(", ")}`;
    const selected = (ev.selected || []).map((s) => `${s.course}=${s.mark}`);
    out.matched = selected.join(", ");
    if (!ev.ok) out.issues.push(`Only ${selected.length} of ${ev.k} required subjects present.`);
    out.status = classifyEvalIssuesForWeb_(out.issues);
    return out;
  }

  out.status = "unknown";
  out.requirement = "Requirement could not be summarized.";
  return out;
}

function classifyEvalIssuesForWeb_(issues) {
  const list = (issues || []).map((x) => String(x || "")).filter(Boolean);
  if (!list.length) return "met";
  if (list.some((x) => /too low|<\s*\d+/.test(x.toLowerCase()))) return "low_mark";
  return "missing";
}

function buildProgramDetailsForWeb_(opts) {
  const avg = (opts && opts.avg) || {};
  const avgMin = toNumber_(opts && opts.avgMin);
  const studentAvg = toNumber_(opts && opts.studentAvg);
  const avgTotal = toNumber_(opts && opts.avgTotal);
  const usedCount = toNumber_(avg.usedCount);

  const averageComplete = isFinite(avgTotal) && avgTotal > 0 && isFinite(usedCount) && usedCount >= avgTotal;
  const averageMeetsMinimum = isFinite(avgMin)
    ? (averageComplete && isFinite(studentAvg) && studentAvg >= avgMin)
    : null;

  const selectedElectives = (Array.isArray(avg.selectedElectives) ? avg.selectedElectives : []).map((e) => ({
    group: String((e && e.group) || "").trim().toUpperCase(),
    name: String((e && e.name) || "").trim(),
    mark: isFinite(toNumber_(e && e.mark)) ? Number(toNumber_(e && e.mark)) : "",
  }));

  const usableTop = (Array.isArray(avg.usableElectives) ? avg.usableElectives : [])
    .slice()
    .sort((a, b) => toNumber_(b && b.mark) - toNumber_(a && a.mark))
    .slice(0, 10)
    .map((e) => ({
      group: String((e && e.group) || "").trim().toUpperCase(),
      name: String((e && e.name) || "").trim(),
      mark: isFinite(toNumber_(e && e.mark)) ? Number(toNumber_(e && e.mark)) : "",
    }));

  return {
    programKey: String((opts && opts.programKey) || "").trim(),
    institution: String((opts && opts.institution) || "").trim(),
    program: String((opts && opts.program) || "").trim(),
    credential: String((opts && opts.credential) || "").trim(),
    programUrl: (() => {
      const raw = String((opts && opts.programUrl) || "").trim();
      return /^https?:\/\//i.test(raw) ? raw : "";
    })(),
    competitiveGuidance: String((opts && opts.competitiveGuidance) || "").trim(),
    requirementText: String((opts && opts.requirementTypeEffective) || "").trim(),
    requirements: (Array.isArray(opts && opts.requirementSummaries) ? opts.requirementSummaries : []).map((x) => ({
      label: String((x && x.label) || "").trim(),
      status: String((x && x.status) || "").trim(),
      requirement: String((x && x.requirement) || "").trim(),
      minMark: isFinite(toNumber_(x && x.minMark)) ? Number(toNumber_(x && x.minMark)) : "",
      matched: String((x && x.matched) || "").trim(),
      issues: (Array.isArray(x && x.issues) ? x.issues : []).map((s) => String(s || "").trim()).filter(Boolean),
    })),
    average: {
      min: isFinite(avgMin) ? Number(avgMin) : "",
      student: isFinite(studentAvg) ? Number(studentAvg) : "",
      totalCourses: isFinite(avgTotal) ? Number(avgTotal) : "",
      usedCourses: isFinite(usedCount) ? Number(usedCount) : 0,
      complete: averageComplete,
      meetsMinimum: averageMeetsMinimum,
      neededElectivesForAverage: Math.max(0, Math.round(toNumber_(opts && opts.electiveNeededForAvg) || 0)),
      avgUsed: formatAvgUsed_(avg),
    },
    electives: {
      allowedGroups: (Array.isArray(opts && opts.allowedGroups) ? opts.allowedGroups : []).map((g) =>
        String(g || "").trim().toUpperCase()
      ),
      ruleSummary: formatElectiveRuleSummary_((opts && opts.electiveRules) || {}),
      selected: selectedElectives,
      usableTop,
    },
    missingReasons: (Array.isArray(opts && opts.reasons) ? opts.reasons : []).map((x) => String(x || "").trim()).filter(Boolean),
    notes: (Array.isArray(opts && opts.notes) ? opts.notes : []).map((x) => String(x || "").trim()).filter(Boolean),
    advisories: (Array.isArray(opts && opts.advisories) ? opts.advisories : [])
      .map((x) => String(x || "").trim())
      .filter(Boolean),
  };
}

function writeResultRowsToSheet_(sheet, rows) {
  const safeRows = rows && rows.length ? rows : [RESULTS_HEADER_ROW.slice()];
  sheet.clearContents();
  sheet.getRange(1, 1, safeRows.length, safeRows[0].length).setValues(safeRows);
  sheet.setFrozenRows(1);
  applyCompetitiveHighlight_(sheet, safeRows);
}

function normalizeCompetitive_(text) {
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

function boolCmp_(a, b) {
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
    advisories.push(`Other requirements: ${unique_(found).join(", ")}`);
  }
}

