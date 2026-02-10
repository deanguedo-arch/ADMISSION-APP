/**
 * Admissions Checker Program Data + Rule Parsing
 */

function indexHeader_(header) {
  const idx = {};
  header.forEach((h, i) => {
    const key = normHeaderKey_(h);
    if (!key) return;
    // Keep the first occurrence.
    if (idx[key] === undefined) idx[key] = i;
  });
  return idx;
}

function normHeaderKey_(h) {
  return String(h || "")
    .replace(/^\uFEFF/, "") // BOM
    .trim()
    .toLowerCase();
}

function requireProgramsColumns_(idx) {
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

function readAvgRules_(ss) {
  const sheet = ss.getSheetByName("AvgRules");
  if (!sheet) return { byKey: {}, byInstitution: {} };
  const values = sheet.getDataRange().getValues();
  if (!values || values.length < 2) return { byKey: {}, byInstitution: {} };

  const header = values[0].map((x) => String(x || "").trim());
  const idx = {};
  header.forEach((h, i) => (idx[normHeaderKey_(h)] = i));

  const byKey = {};
  const byInstitution = {};

  for (let i = 1; i < values.length; i++) {
    const row = values[i];
    const institution = String(row[idx["institution"]] || "").trim();
    const program = String(row[idx["program"]] || "").trim();
    const avgTotal = toNumber_(row[idx["avg_total"]]);
    if (!institution || !isFinite(avgTotal) || avgTotal <= 0) continue;

    if (program === "*" || !program) {
      byInstitution[institution] = Math.round(avgTotal);
      continue;
    }
    byKey[`${institution}||${program}`] = Math.round(avgTotal);
  }

  return { byKey, byInstitution };
}

function readElectiveRuleOverrides_(ss) {
  const sheet = ss.getSheetByName("ElectiveRules");
  if (!sheet) return { byKey: {}, byInstitution: {} };

  const values = sheet.getDataRange().getValues();
  if (!values || values.length < 2) return { byKey: {}, byInstitution: {} };

  const header = values[0].map((x) => String(x || "").trim());
  const idx = {};
  header.forEach((h, i) => (idx[normHeaderKey_(h)] = i));

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
  return unique_(parts.map((x) => String(x || "").trim()).filter(Boolean)).join("; ");
}

function combineRuleText_(baseText, overrideText) {
  const a = String(baseText || "").trim();
  const b = String(overrideText || "").trim();
  if (a && b) return `${a}; ${b}`;
  return a || b || "";
}

function resolveAvgTotal_(opts) {
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

function getStr_(row, idx, col) {
  const i = idx[normHeaderKey_(col)];
  if (i === undefined) return "";
  const v = row[i];
  if (v === null || v === undefined) return "";
  return String(v).trim();
}

function unifyEnglishReq_(row, idx) {
  const a = getStr_(row, idx, "English_Req");
  if (a) return a;
  const b = getStr_(row, idx, "Eng_Req");
  return b;
}

function unifyEnglishMin_(row, idx) {
  const a = getStr_(row, idx, "English_Min");
  if (a) return a;
  const b = getStr_(row, idx, "Eng_Min");
  return b;
}

function toNumber_(v) {
  if (v === null || v === undefined) return NaN;
  const s = String(v).trim();
  if (!s) return NaN;
  const n = Number(s);
  return isFinite(n) ? n : NaN;
}

function canonKey_(s) {
  return String(s || "")
    .trim()
    .toUpperCase()
    .replace(/\./g, "")
    .replace(/\s+/g, " ");
}

function parseElectiveQty_(text) {
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

function parseAllowedGroups_(poolText) {
  const t = String(poolText || "").toUpperCase();
  const m = t.match(/\b[ABCD]\b/g);
  if (!m || !m.length) return ["A", "B", "C", "D"];
  return unique_(m);
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
    const minMark = toNumber_(markMatch[1]);
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
  return toNumber_(t);
}

function parseGroupsFromText_(text) {
  const m = String(text || "").toUpperCase().match(/[ABCD]/g);
  return m ? unique_(m) : [];
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

  const courses = unique_(
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

