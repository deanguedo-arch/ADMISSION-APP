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
  const staleDaysCap = Math.max(1, Math.round(toNumber_((opts && opts.staleDaysCap) || 60) || 60));

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
  const datasetDate = resolveDatasetDateFromPrograms_(programsRange, (opts && opts.datasetDate) || new Date().toISOString());

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
    const sourceUrl = normalizeHttpUrlForOutput_(programUrl);
    const confidenceAssessment = evaluateConfidenceForProgram_({
      institution,
      program,
      credential,
      requirementTypeEffective,
      englishReq,
      mathReq,
      socialReq,
      scienceReq,
      electiveQty,
      avgMin,
      avgTotalFromData,
      avgTotalResolved: avgTotal,
      notes,
      advisories,
      missingText,
      sourceUrl,
      datasetDate,
      staleDaysCap,
    });
    const snapshotResult = deriveSnapshotResult_(missingText, confidenceAssessment.confidence);
    const sourceUrlText = sourceUrl || "Source link missing";

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
      snapshotResult,
      confidenceAssessment.confidence,
      confidenceAssessment.whyText,
      confidenceAssessment.uncheckableReason,
      confidenceAssessment.nextStep,
      sourceUrlText,
      datasetDate,
      programKey,
    ];

    rowRecords.push({
      key: programKey,
      row,
      missing: missingText,
      notes: notesText,
      confidence: confidenceAssessment.confidence,
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
      datasetDate,
      confidenceAssessment,
      snapshotResult,
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
  const uncheckableRecords = rowRecords.filter((r) => isConfidenceUncheckable_(r.confidence));
  const ineligibleRecords = rowRecords.filter(
    (r) => !isConfidenceUncheckable_(r.confidence) && String(r.missing || "").trim() !== ""
  );
  const eligibleRecords = rowRecords.filter(
    (r) => !isConfidenceUncheckable_(r.confidence) && String(r.missing || "").trim() === ""
  );

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
  const confidenceAssessment = (opts && opts.confidenceAssessment) || {};
  const confidence = normalizeConfidenceValue_(confidenceAssessment.confidence || "");
  const why = (Array.isArray(confidenceAssessment.why) ? confidenceAssessment.why : [])
    .map((x) => String(x || "").trim())
    .filter(Boolean);
  const whyText = String(confidenceAssessment.whyText || "").trim();
  const uncheckableReason = String(confidenceAssessment.uncheckableReason || "").trim();
  const nextStep = String(confidenceAssessment.nextStep || "").trim();
  const warning = buildConfidenceWarningPayload_(confidence, why, uncheckableReason, nextStep);

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
  const normalizedProgramUrl = normalizeHttpUrlForOutput_((opts && opts.programUrl) || "");

  return {
    programKey: String((opts && opts.programKey) || "").trim(),
    institution: String((opts && opts.institution) || "").trim(),
    program: String((opts && opts.program) || "").trim(),
    credential: String((opts && opts.credential) || "").trim(),
    programUrl: normalizedProgramUrl,
    sourceUrlMissing: !normalizedProgramUrl,
    datasetDate: normalizeDateYmd_((opts && opts.datasetDate) || ""),
    snapshotResult: String((opts && opts.snapshotResult) || "").trim(),
    confidence,
    why,
    whyText,
    uncheckableReason,
    nextStep,
    warning,
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

function readPinnedProgramKeysFromSheet_(sheet) {
  if (!sheet) return {};
  const range = sheet.getDataRange();
  const values = range && range.getValues ? range.getValues() : [];
  if (!values || values.length < 2) return {};

  const header = (values[0] || []).map((x) => String(x || "").trim().toLowerCase());
  const pinIdx = header.indexOf("pin");
  const keyIdx = header.indexOf("program_key");
  if (pinIdx < 0 || keyIdx < 0) return {};

  const out = {};
  for (let i = 1; i < values.length; i++) {
    const row = values[i] || [];
    const key = String(row[keyIdx] || "").trim();
    if (!key) continue;
    if (isTruthyPinValue_(row[pinIdx])) out[key] = true;
  }
  return out;
}

function isTruthyPinValue_(value) {
  if (value === true) return true;
  const t = String(value || "").trim().toLowerCase();
  if (!t) return false;
  return t === "true" || t === "yes" || t === "1" || t === "y";
}

function writeResultRowsToSheet_(sheet, rows, opts) {
  const safeRows = rows && rows.length ? rows : [RESULTS_HEADER_ROW.slice()];
  const options = opts && typeof opts === "object" ? opts : {};
  const withPins = options.enablePins === true;
  const pinnedByProgramKey = options.pinnedByProgramKey && typeof options.pinnedByProgramKey === "object"
    ? options.pinnedByProgramKey
    : {};

  const outputRows = withPins
    ? addPinColumnToRows_(safeRows, pinnedByProgramKey)
    : safeRows;

  sheet.clearContents();
  sheet.getRange(1, 1, outputRows.length, outputRows[0].length).setValues(outputRows);
  sheet.setFrozenRows(1);

  if (withPins && outputRows.length > 1) {
    const pinRange = sheet.getRange(2, 1, outputRows.length - 1, 1);
    pinRange.insertCheckboxes();
    const pinValues = outputRows
      .slice(1)
      .map((r) => [r[0] === true]);
    pinRange.setValues(pinValues);
  }

  applyCompetitiveHighlight_(sheet, outputRows);
}

function addPinColumnToRows_(rows, pinnedByProgramKey) {
  const safeRows = rows && rows.length ? rows : [RESULTS_HEADER_ROW.slice()];
  const header = (safeRows[0] || []).map((x) => String(x || ""));
  const keyIdx = header.map((x) => String(x || "").trim().toLowerCase()).indexOf("program_key");
  const out = [["Pin"].concat(header)];
  for (let i = 1; i < safeRows.length; i++) {
    const row = Array.isArray(safeRows[i]) ? safeRows[i].slice() : [];
    const key = keyIdx >= 0 ? String(row[keyIdx] || "").trim() : "";
    out.push([!!(key && pinnedByProgramKey[key])].concat(row));
  }
  return out;
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
  const minIdx = header.indexOf("min avg");
  const studentIdx = header.indexOf("student avg");
  if (compIdx < 0) return;
  if (minIdx < 0 || studentIdx < 0) return;

  const n = values.length - 1;
  const yellow = "#fff2cc";
  const white = null; // keep default background

  const bg = [];
  for (let i = 1; i < values.length; i++) {
    const competitive = String(values[i][compIdx] || "").trim();
    const color = competitive ? yellow : white;
    bg.push([color]);
  }

  // Apply only to Min Avg + Student Avg cells (rows 2..), even if columns shift.
  sheet.getRange(2, minIdx + 1, n, 1).setBackgrounds(bg);
  sheet.getRange(2, studentIdx + 1, n, 1).setBackgrounds(bg);
}

function isUncheckable_(notesText) {
  return isAmbiguityText_(notesText);
}

function normalizeHttpUrlForOutput_(value) {
  const raw = String(value || "").trim();
  if (!raw) return "";
  return /^https?:\/\//i.test(raw) ? raw : "";
}

function normalizeConfidenceValue_(value) {
  const t = String(value || "").trim().toLowerCase();
  if (t === "high") return "High";
  if (t === "medium") return "Medium";
  if (t === "low") return "Low";
  if (t === "uncheckable") return "Uncheckable";
  return "Medium";
}

function isConfidenceUncheckable_(value) {
  return normalizeConfidenceValue_(value) === "Uncheckable";
}

function deriveSnapshotResult_(missingText, confidence) {
  if (isConfidenceUncheckable_(confidence)) return "Uncheckable";
  return String(missingText || "").trim() ? "Likely ineligible" : "Likely eligible";
}

function isAmbiguityText_(text) {
  const t = String(text || "").trim().toLowerCase();
  if (!t) return false;
  return (
    /\bsee\s+(degree|department|faculty|program|calendar)\b/.test(t) ||
    /\brefer\s+to\s+(degree|department|faculty|program|calendar)\b/.test(t) ||
    /\brequirement\s+unspecified\b/.test(t) ||
    /\bdepartment(?:al)?\s+requirements?\b/.test(t) ||
    /\binherit(?:ed|ance)?\b/.test(t) ||
    /\bsame\s+as\b/.test(t) ||
    /\bcheck\s+notes\b/.test(t) ||
    /\bcontact\s+(the\s+)?(department|faculty|program|institution)\b/.test(t)
  );
}

function firstAmbiguityReason_(parts) {
  const list = (parts || []).map((x) => String(x || "").trim()).filter(Boolean);
  for (let i = 0; i < list.length; i++) {
    if (isAmbiguityText_(list[i])) {
      return "Requirements reference another degree/department page and cannot be checked deterministically from the snapshot.";
    }
  }
  return "";
}

function confidenceRank_(value) {
  const c = normalizeConfidenceValue_(value);
  if (c === "High") return 3;
  if (c === "Medium") return 2;
  if (c === "Low") return 1;
  return 0;
}

function capConfidence_(current, cap) {
  const normalizedCurrent = normalizeConfidenceValue_(current);
  const normalizedCap = normalizeConfidenceValue_(cap);
  if (normalizedCurrent === "Uncheckable") return normalizedCurrent;
  if (normalizedCap === "Uncheckable") return "Uncheckable";
  return confidenceRank_(normalizedCurrent) <= confidenceRank_(normalizedCap)
    ? normalizedCurrent
    : normalizedCap;
}

function confidenceFromScore_(score) {
  const n = Number(score);
  if (!isFinite(n)) return "Medium";
  if (n >= 3) return "High";
  if (n >= 2) return "Medium";
  return "Low";
}

function defaultUncheckableNextStep_(sourceUrl) {
  if (sourceUrl) {
    return "Open the official program page and confirm exact prerequisites, average method, and department-level requirements.";
  }
  return "Find the official program page first, then confirm exact prerequisites, average method, and department-level requirements.";
}

function evaluateConfidenceForProgram_(opts) {
  const sourceUrl = normalizeHttpUrlForOutput_(opts && opts.sourceUrl);
  const notes = (Array.isArray(opts && opts.notes) ? opts.notes : []).map((x) => String(x || "").trim()).filter(Boolean);
  const advisories = (Array.isArray(opts && opts.advisories) ? opts.advisories : [])
    .map((x) => String(x || "").trim())
    .filter(Boolean);
  const requirementTypeText = String((opts && opts.requirementTypeEffective) || "").trim();
  const englishReq = String((opts && opts.englishReq) || "").trim();
  const mathReq = String((opts && opts.mathReq) || "").trim();
  const socialReq = String((opts && opts.socialReq) || "").trim();
  const scienceReq = String((opts && opts.scienceReq) || "").trim();
  const electiveQty = String((opts && opts.electiveQty) || "").trim();
  const datasetDate = normalizeDateYmd_((opts && opts.datasetDate) || "");
  const staleDaysCap = Math.max(1, Math.round(toNumber_(opts && opts.staleDaysCap) || 60));
  const hasPlacementAssessmentSignal =
    /^placement_assessment(?:\b|;)/i.test(requirementTypeText) ||
    /\b(?:placement\s+(?:assessment|test)|assessment\/placement|accuplacer)\b/i.test(requirementTypeText) ||
    advisories.some((x) => /\b(?:placement|assessment)\b/i.test(String(x || "")));

  if (hasPlacementAssessmentSignal) {
    return {
      confidence: "Uncheckable",
      why: [],
      whyText: "",
      uncheckableReason:
        "Program requires placement or assessment confirmation before eligibility can be determined from the snapshot.",
      nextStep: defaultUncheckableNextStep_(sourceUrl),
    };
  }

  const hasAnyStructuredRequirement = (
    isFinite(toNumber_(opts && opts.avgMin)) ||
    !!englishReq ||
    !!mathReq ||
    !!socialReq ||
    !!scienceReq ||
    !!electiveQty
  );

  if (!hasAnyStructuredRequirement) {
    const reason = "Snapshot row is missing structured admission requirement fields.";
    return {
      confidence: "Uncheckable",
      why: [],
      whyText: "",
      uncheckableReason: reason,
      nextStep: defaultUncheckableNextStep_(sourceUrl),
    };
  }

  const ambiguityReason = firstAmbiguityReason_([
    requirementTypeText,
    englishReq,
    mathReq,
    socialReq,
    scienceReq,
    electiveQty,
  ].concat(notes, advisories));

  if (ambiguityReason) {
    return {
      confidence: "Uncheckable",
      why: [],
      whyText: "",
      uncheckableReason: ambiguityReason,
      nextStep: defaultUncheckableNextStep_(sourceUrl),
    };
  }

  let score = 3;
  const why = [];

  if (!sourceUrl) {
    score = Math.min(score, 1);
    why.push("Source link missing in snapshot data.");
  }

  const avgDefaulted = notes.some((x) => /avg course-count defaulted/i.test(x));
  if (avgDefaulted) {
    score -= 1;
    why.push("Average course-count uses a default assumption.");
  }

  const hasManualReviewSignals = advisories.length > 0 || /(audition|portfolio|casper|interview|questionnaire)/i.test(requirementTypeText);
  if (hasManualReviewSignals) {
    score -= 1;
    why.push("Program includes additional manual-review requirements.");
  }

  const hasUnstructuredNotes = notes.some((x) =>
    /(requirement unspecified|english language proficiency|language proficiency)/i.test(String(x || ""))
  );
  if (hasUnstructuredNotes) {
    score -= 2;
    why.push("Some requirement text is not fully machine-checkable.");
  }

  const datasetAgeDays = calculateDatasetAgeDays_(datasetDate, new Date());
  const isStale = isFinite(datasetAgeDays) && datasetAgeDays > staleDaysCap;
  if (isStale) {
    why.push(`Snapshot data is ${datasetAgeDays} days old.`);
  }

  let confidence = confidenceFromScore_(score);
  if (!sourceUrl) confidence = capConfidence_(confidence, "Low");
  if (isStale) confidence = capConfidence_(confidence, "Medium");

  let whyOut = [];
  if (confidence === "Medium") whyOut = why.slice(0, 1);
  if (confidence === "Low") whyOut = why.slice(0, 3);

  return {
    confidence,
    why: whyOut,
    whyText: whyOut.join(" | "),
    uncheckableReason: "",
    nextStep: "",
  };
}

function buildConfidenceWarningPayload_(confidenceValue, why, uncheckableReason, nextStep) {
  const confidence = normalizeConfidenceValue_(confidenceValue);
  const reasons = (Array.isArray(why) ? why : []).map((x) => String(x || "").trim()).filter(Boolean);
  if (confidence === "High") {
    return { level: "high", text: "", reasons: [], reason: "", nextStep: "" };
  }
  if (confidence === "Medium") {
    return {
      level: "medium",
      text: "Advisory - verify on program website",
      reasons: reasons.slice(0, 1),
      reason: "",
      nextStep: "",
    };
  }
  if (confidence === "Low") {
    return {
      level: "low",
      text: "Low confidence - verify on program website",
      reasons: reasons.slice(0, 3),
      reason: "",
      nextStep: "",
    };
  }
  return {
    level: "uncheckable",
    text: "Uncheckable - manual review required",
    reasons: [],
    reason: String(uncheckableReason || "").trim(),
    nextStep: String(nextStep || "").trim(),
  };
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

function runConfidenceSelfTest_() {
  const base = {
    requirementTypeEffective: "Standard admission requirements",
    englishReq: "English 30-1",
    mathReq: "Math 30-1",
    socialReq: "",
    scienceReq: "",
    electiveQty: "2",
    avgMin: 70,
    notes: [],
    advisories: [],
    datasetDate: "2026-01-01",
    staleDaysCap: 60,
  };

  const high = evaluateConfidenceForProgram_(Object.assign({}, base, { sourceUrl: "https://example.edu/program" }));
  if (high.confidence !== "High") throw new Error(`Confidence self-test failed: expected High, got ${high.confidence}`);

  const low = evaluateConfidenceForProgram_(Object.assign({}, base, { sourceUrl: "" }));
  if (low.confidence !== "Low") throw new Error(`Confidence self-test failed: expected Low, got ${low.confidence}`);

  const uncheckable = evaluateConfidenceForProgram_(Object.assign({}, base, { requirementTypeEffective: "Refer to Degree" }));
  if (uncheckable.confidence !== "Uncheckable") {
    throw new Error(`Confidence self-test failed: expected Uncheckable, got ${uncheckable.confidence}`);
  }
}

