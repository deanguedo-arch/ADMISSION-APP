/**
 * Admissions Checker Elective Mapping + Average Selection
 */

function buildElectives_(rows, opts) {
  const source = String((opts && opts.source) || "manual").trim().toLowerCase();
  const rowOffset = Math.max(1, Math.round(toNumber_((opts && opts.rowOffset) || 1) || 1));
  const electives = [];
  (rows || []).forEach(([name, group, mark], i) => {
    const m = toNumber_(mark);
    if (!isFinite(m)) return;

    const label = String(name || "").trim();
    const key = label ? normalizeCourseKey_(label) : "";
    const overrideGroup = String(group || "").trim().toUpperCase();
    let groups = [];
    if (["A", "B", "C", "D"].includes(overrideGroup)) groups = [overrideGroup];
    else if (key) groups = electiveGroupsForCourseKey_(key);
    if (!groups.length) return;

    groups = unique_(groups.filter((g) => ["A", "B", "C", "D"].includes(String(g || "").toUpperCase())));
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
  return unique_(options).sort((a, b) => String(a).localeCompare(String(b)));
}

function buildAutoElectivesFromCourseMap_(courseMap) {
  const out = [];
  Object.keys(courseMap || {}).forEach((courseKey) => {
    const mark = toNumber_(courseMap[courseKey]);
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
    const mark = toNumber_(item.mark);
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
  const k0 = canonKey_(course);
  const alias = courseAliases_();
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
  if (map[key] && map[key].length) return unique_(map[key]);

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
  return unique_(inferred);
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

function computeStudentAverage_(opts) {
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
    Math.max(0, Math.round(toNumber_(electiveNeeded) || 0)),
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
  const needed = Math.max(0, Math.round(toNumber_(neededCount) || 0));
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
  const target = Math.max(0, Math.round(toNumber_(targetCount) || 0));
  if (target === 0) return [];

  const maxByGroup = (rules && rules.maxByGroup) || {};
  const minFromSets = (rules && rules.minFromSets) || [];
  if (minFromSets.some((r) => (toNumber_(r.count) || 0) > target)) return null;

  let best = null;
  let bestSum = -Infinity;

  const chosen = [];
  const usedUnits = {};
  const groupCounts = {};

  const meetsMinGroupRules = () =>
    minFromSets.every((rule) => {
      const groups = rule.groups || [];
      const minCount = Math.max(0, Math.round(toNumber_(rule.count) || 0));
      if (!groups.length || minCount === 0) return true;
      let count = 0;
      groups.forEach((g) => {
        const group = String(g || "").toUpperCase();
        count += groupCounts[group] || 0;
      });
      return count >= minCount;
    });

  function dfs_(index, sum) {
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
    const maxForGroup = toNumber_(maxByGroup[group]);
    const unitKey = candidate.key ? `KEY:${candidate.key}` : `SRC:${candidate.sourceKey}`;

    const canUseUnit = !usedUnits[unitKey];
    const canUseGroup = !isFinite(maxForGroup) || (groupCounts[group] || 0) < maxForGroup;

    if (canUseUnit && canUseGroup) {
      chosen.push(candidate);
      usedUnits[unitKey] = true;
      groupCounts[group] = (groupCounts[group] || 0) + 1;
      dfs_(index + 1, sum + candidate.mark);
      chosen.pop();
      groupCounts[group] = groupCounts[group] - 1;
      if (!groupCounts[group]) delete groupCounts[group];
      delete usedUnits[unitKey];
    }

    dfs_(index + 1, sum);
  }

  dfs_(0, 0);
  return best;
}

