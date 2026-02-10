/**
 * Admissions Checker Subject Parsing + Requirement Evaluation
 */

function buildCourseMap_(studentRows) {
  const map = {};
  const alias = courseAliases_();
  studentRows.forEach(([course, mark]) => {
    const c = String(course || "").trim();
    const m = toNumber_(mark);
    if (!c || !isFinite(m)) return;
    const k0 = canonKey_(c);
    const k = alias[k0] || k0;
    map[k] = m;
  });
  return map;
}

function courseAliases_() {
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

function evalSubject_(courseMap, subject, reqText, minMark) {
  const t = String(reqText || "").trim();
  if (!t) return { kind: "none" };
  if (/^(See Degree|Refer to Degree)$/i.test(t)) return { kind: "unknown", reason: t };
  if (/(placement|assessment|test)/i.test(t)) return { kind: "assessment", reason: "assessment/placement mentioned" };
  if (/english language proficiency/i.test(t)) return { kind: "unknown", reason: "English language proficiency" };
  if (/\bunspecified\b/i.test(t)) return { kind: "unknown", reason: `${title_(subject)} requirement unspecified` };

  // Support simple AND requirements like "Mathematics 30-1 and Mathematics 31".
  // Each AND-part can itself be an OR list (e.g., "30-1 or 30-2 and 31").
  const andParts = splitByAnd_(t);
  if (andParts.length > 1) {
    const parts = andParts.map((p) => {
      const courses = normalizeRequirementToCourses_(subject, p);
      const best = bestMarkWithEquivalencies_(courseMap, courses);
      return { courses, best };
    });
    const out = { kind: "all", parts };
    if (isFinite(minMark) && minMark > 0) out.minMark = minMark;
    return out;
  }

  const courses = normalizeRequirementToCourses_(subject, t);
  const best = bestMarkWithEquivalencies_(courseMap, courses);
  const out = { kind: "any", courses, best };
  if (isFinite(minMark) && minMark > 0) out.minMark = minMark;
  return out;
}

function evalScience_(courseMap, scienceReq, minMark) {
  if (!scienceReq || scienceReq.kind === "none") return { kind: "none" };
  if (scienceReq.kind === "unknown") return { kind: "unknown", reason: scienceReq.reason };

  if (scienceReq.kind === "all") {
    const courses = scienceReq.courses || [];
    const checks = courses.map((c) => {
      const best = bestMarkWithEquivalencies_(courseMap, [c]);
      if (!best) return { course: c, ok: false, reason: `Missing ${c}` };
      if (isFinite(minMark) && minMark > 0 && best.mark < minMark) {
        return { course: c, ok: false, reason: `${c} mark too low: ${best.mark} < ${minMark}`, mark: best.mark, key: best.key };
      }
      return { course: c, ok: true, mark: best.mark, key: best.key };
    });
    return { kind: "all", courses, checks, minMark };
  }

  if (scienceReq.kind === "all_plus_any") {
    const allCourses = unique_(scienceReq.allCourses || []);
    const anyCourses = unique_(scienceReq.anyCourses || []);

    const checksAll = allCourses.map((c) => {
      const best = bestMarkWithEquivalencies_(courseMap, [c]);
      if (!best) return { course: c, ok: false, reason: `Missing ${c}` };
      if (isFinite(minMark) && minMark > 0 && best.mark < minMark) {
        return { course: c, ok: false, reason: `${c} mark too low: ${best.mark} < ${minMark}`, mark: best.mark, key: best.key };
      }
      return { course: c, ok: true, mark: best.mark, key: best.key };
    });

    const bestAny = bestMarkWithEquivalencies_(courseMap, anyCourses);
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
    const courses = unique_(scienceReq.courses || []);
    const k = Math.max(0, Math.round(scienceReq.k || 0));

    const candidates = [];
    courses.forEach((c) => {
      const best = bestMarkWithEquivalencies_(courseMap, [c]);
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
  const best = bestMarkWithEquivalencies_(courseMap, courses);
  const out = { kind: "any", courses, best };
  if (isFinite(minMark) && minMark > 0) out.minMark = minMark;
  return out;
}

function appendEval_(ev, label, reasons, notes, advisories) {
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

function buildScienceReq_(row, idx) {
  // Prefer NAIT-style flags when present.
  const flagPairs = [
    ["Bio_30_Req", "Biology 30"],
    ["Chem_30_Req", "Chemistry 30"],
    ["Phys_30_Req", "Physics 30"],
    ["Sci_30_Req", "Science 30"],
  ];
  const flagCourses = [];
  flagPairs.forEach(([flag, course]) => {
    const v = getStr_(row, idx, flag);
    if (/^yes$/i.test(v)) flagCourses.push(course);
  });

  const t = getStr_(row, idx, "Science_Req");
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

function parseAlternatives_(subject, text) {
  const norm = String(text || "")
    .replace(/\//g, " or ")
    .replace(/\s+/g, " ")
    .trim();

  // If we have course codes, prefer extracting them.
  const codes = extractCourseCodes_(norm);
  if (codes.length) {
    const prefix =
      subject === "english" ? "English " :
      subject === "math" ? "Math " :
      subject === "social" ? "Social Studies " :
      "";
    return unique_(codes.map((c) => prefix + c));
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

function normalizeRequirementToCourses_(subject, rawText) {
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

  const courses = parseAlternatives_(subject, t);
  // Handle Math 31-style requirements (no dash).
  if (subject === "math" && /(?:math|mathematics)\s*31\b/i.test(t)) {
    courses.push("Math 31");
  }
  return unique_(courses);
}

function bestMarkWithEquivalencies_(courseMap, courses) {
  let best = null;
  courses.forEach((c) => {
    const alias = courseAliases_();
    const keys = expandEquivalencies_(c).map((x) => {
      const k0 = canonKey_(x);
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

function expandEquivalencies_(course) {
  const s = String(course || "").trim();
  if (!s) return [];

  const t = canonKey_(s);
  const m = /^(ENGLISH|MATH|SOCIAL STUDIES)\s+(20|30)-([12])$/.exec(t);
  if (!m) return [s];

  const subj = m[1];
  const level = Number(m[2]);
  const stream = m[3]; // "1" or "2"

  const out = [];
  const label = subj === "SOCIAL STUDIES" ? "Social Studies" : title_(subj.toLowerCase());

  // Exact requirement first.
  out.push(`${label} ${level}-${stream}`);

  // -1 can satisfy -2, not vice versa.
  if (stream === "2") out.push(`${label} ${level}-1`);

  // 30-level can satisfy 20-level (same stream), and 30-1 can satisfy 20-2 via the -2 rule.
  if (level === 20) {
    out.push(`${label} 30-${stream}`);
    if (stream === "2") out.push(`${label} 30-1`);
  }

  return unique_(out);
}

function extractCourseCodes_(text) {
  const t = String(text || "").replace(/\//g, " ");
  const out = [];
  const re = /\b(\d{2}-[12])\b/g;
  let m;
  while ((m = re.exec(t))) out.push(m[1]);
  return unique_(out);
}

function collectRequiredMarks_(evals) {
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

function countRequiredSlots_(evals) {
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

