// Offline runtime bridge for the static admissions snapshot.
// This file is loaded after eligibility_core.js and snapshot_data.js.

(function () {
  "use strict";

  var snapshot = window.OFFLINE_SNAPSHOT;
  if (!snapshot || typeof snapshot !== "object") {
    throw new Error("OFFLINE_SNAPSHOT is not available. Rebuild the offline snapshot.");
  }

  var DEFAULT_HEADERS = [
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

  if (!Array.isArray(window.RESULTS_HEADER_ROW) || !window.RESULTS_HEADER_ROW.length) {
    window.RESULTS_HEADER_ROW = DEFAULT_HEADERS.slice();
  }

  if (typeof window.MANUAL_ELECTIVE_SLOTS === "undefined") {
    window.MANUAL_ELECTIVE_SLOTS = Number(snapshot.manualElectiveSlots || 5);
  }

  function hasOwn(obj, key) {
    return Object.prototype.hasOwnProperty.call(obj, key);
  }

  function normalizeText(value) {
    return String(value == null ? "" : value).trim();
  }

  function toNumber(value) {
    var n = Number(value);
    return Number.isFinite(n) ? n : NaN;
  }

  function clampMark(value) {
    if (!Number.isFinite(value)) return NaN;
    if (value < 0) return 0;
    if (value > 100) return 100;
    return value;
  }

  function normalizeGroup(value) {
    var t = normalizeText(value).toUpperCase();
    return t === "A" || t === "B" || t === "C" || t === "D" ? t : "";
  }

  function shallowCloneObject(obj) {
    if (!obj || typeof obj !== "object" || Array.isArray(obj)) return {};
    var out = {};
    Object.keys(obj).forEach(function (key) {
      out[key] = obj[key];
    });
    return out;
  }

  function deepClone(value) {
    if (value === null || typeof value !== "object") return value;
    if (Array.isArray(value)) return value.map(deepClone);
    var out = {};
    Object.keys(value).forEach(function (key) {
      out[key] = deepClone(value[key]);
    });
    return out;
  }

  if (typeof window.copyWebDetailsByKey_ !== "function") {
    window.copyWebDetailsByKey_ = function (detailsByKey) {
      var input = detailsByKey && typeof detailsByKey === "object" ? detailsByKey : {};
      var out = {};
      Object.keys(input).forEach(function (key) {
        out[key] = deepClone(input[key]);
      });
      return out;
    };
  }

  if (typeof window.listNamedCourseOptions_ !== "function") {
    window.listNamedCourseOptions_ = function () {
      var alias = typeof window.courseAliases_ === "function" ? window.courseAliases_() : {};
      var byKey = {};
      Object.keys(alias || {}).forEach(function (key) {
        var value = normalizeText(alias[key]);
        if (!value) return;
        var norm = typeof window.normalizeCourseKey_ === "function" ? window.normalizeCourseKey_(value) : value.toUpperCase();
        if (!norm) return;
        byKey[norm] =
          typeof window.formatCourseName_ === "function" ? window.formatCourseName_(norm) : value;
      });
      if (typeof window.listElectiveCourseOptions_ === "function") {
        window.listElectiveCourseOptions_().forEach(function (course) {
          var value = normalizeText(course);
          if (!value) return;
          var norm = typeof window.normalizeCourseKey_ === "function" ? window.normalizeCourseKey_(value) : value.toUpperCase();
          if (!norm) return;
          byKey[norm] =
            typeof window.formatCourseName_ === "function" ? window.formatCourseName_(norm) : value;
        });
      }
      return Object.keys(byKey)
        .map(function (k) {
          return byKey[k];
        })
        .sort(function (a, b) {
          return String(a).localeCompare(String(b));
        });
    };
  }

  function fnv1a32(input) {
    var text = String(input || "");
    var hash = 0x811c9dc5;
    for (var i = 0; i < text.length; i++) {
      hash ^= text.charCodeAt(i);
      hash = Math.imul(hash, 0x01000193) >>> 0;
    }
    return hash >>> 0;
  }

  function stableHashToken(input) {
    var source = String(input || "");
    var a = fnv1a32(source).toString(36);
    var b = fnv1a32(source.split("").reverse().join("")).toString(36);
    var out = (a + b).replace(/[^a-z0-9]/gi, "").toLowerCase();
    if (out.length >= 12) return out.slice(0, 12);
    while (out.length < 12) out += "0";
    return out;
  }

  // Override Apps Script Utilities-based keying with a browser-safe deterministic key.
  window.makeProgramKey_ = function (institution, program, credential, row) {
    var parts = [institution, program, credential]
      .map(function (value) {
        if (typeof window.slugProgramKeyPart_ === "function") {
          return window.slugProgramKeyPart_(value);
        }
        return String(value || "")
          .trim()
          .toLowerCase()
          .replace(/[^a-z0-9]+/g, "_")
          .replace(/^_+|_+$/g, "")
          .slice(0, 60);
      })
      .filter(Boolean);

    var base = parts.length ? parts.join("__") : "program";
    var rowSignature = (Array.isArray(row) ? row : [])
      .map(function (value) {
        return String(value == null ? "" : value).trim();
      })
      .join("|");
    var fingerprint =
      String(institution || "") +
      "||" +
      String(program || "") +
      "||" +
      String(credential || "") +
      "||" +
      rowSignature;
    return base + "_" + stableHashToken(fingerprint);
  };

  function sanitizeNamedCourses(rows) {
    var out = [];
    var list = Array.isArray(rows) ? rows : [];
    for (var i = 0; i < list.length; i++) {
      var item = list[i];
      if (!item || typeof item !== "object" || Array.isArray(item)) continue;
      var course = normalizeText(item.course);
      var mark = clampMark(toNumber(item.mark));
      if (!course || !Number.isFinite(mark)) continue;
      out.push([course, mark]);
    }
    return out;
  }

  function sanitizeManualElectives(rows) {
    var out = [];
    var list = Array.isArray(rows) ? rows : [];
    for (var i = 0; i < list.length; i++) {
      var item = list[i];
      if (!item || typeof item !== "object" || Array.isArray(item)) continue;
      var course = normalizeText(item.course);
      var mark = clampMark(toNumber(item.mark));
      if (!course || !Number.isFinite(mark)) continue;
      out.push([course, normalizeGroup(item.group), mark]);
    }
    return out;
  }

  function buildBootstrapResponse() {
    return {
      generatedAt: new Date().toISOString(),
      requiresAuth: false,
      auth: {
        email: "offline@snapshot.local",
        googleClientId: "",
        allowedDomainSuffix: "",
      },
      dataset: {
        lastProgramsSyncUtc: normalizeText(snapshot.lastProgramsSyncUtc),
        lastProgramsSyncLocal: normalizeText(snapshot.lastProgramsSyncLocal),
      },
      namedCourseOptions: window.listNamedCourseOptions_(),
      electiveCourseOptions:
        typeof window.listElectiveCourseOptions_ === "function" ? window.listElectiveCourseOptions_() : [],
      manualElectiveSlots: Number(snapshot.manualElectiveSlots || 5),
      groups: ["A", "B", "C", "D"],
    };
  }

  function buildEligibilityResponse(payload) {
    if (typeof window.evaluateProgramsForStudent_ !== "function") {
      throw new Error("Eligibility runtime is unavailable. Rebuild the offline snapshot.");
    }
    if (typeof window.buildCourseMap_ !== "function" || typeof window.buildElectives_ !== "function") {
      throw new Error("Eligibility helpers are unavailable. Rebuild the offline snapshot.");
    }

    var namedRows = sanitizeNamedCourses(payload && payload.namedCourses);
    var manualRows = sanitizeManualElectives(payload && payload.manualElectives);
    var courseMap = window.buildCourseMap_(namedRows);
    var manualElectives = window.buildElectives_(manualRows, { source: "manual-web", rowOffset: 1 });

    var programsRange = Array.isArray(snapshot.programsRange) ? snapshot.programsRange : [];
    var avgRules = shallowCloneObject(snapshot.avgRules);
    if (!hasOwn(avgRules, "byKey")) avgRules.byKey = {};
    if (!hasOwn(avgRules, "byInstitution")) avgRules.byInstitution = {};

    var electiveRuleOverrides = shallowCloneObject(snapshot.electiveRuleOverrides);
    if (!hasOwn(electiveRuleOverrides, "byKey")) electiveRuleOverrides.byKey = {};
    if (!hasOwn(electiveRuleOverrides, "byInstitution")) electiveRuleOverrides.byInstitution = {};

    var evaluation = window.evaluateProgramsForStudent_({
      programsRange: programsRange,
      courseMap: courseMap,
      manualElectives: manualElectives,
      avgRules: avgRules,
      electiveRuleOverrides: electiveRuleOverrides,
    });

    var generatedAt = new Date().toISOString();
    var datasetStamp = normalizeText(snapshot.datasetStamp) || "offline_snapshot";
    var allKeys = (evaluation.rowKeysByView && evaluation.rowKeysByView.all) || [];

    return {
      generatedAt: generatedAt,
      headers: Array.isArray(window.RESULTS_HEADER_ROW)
        ? window.RESULTS_HEADER_ROW.slice()
        : DEFAULT_HEADERS.slice(),
      meta: {
        generatedAt: generatedAt,
        datasetRows: Math.max(0, programsRange.length - 1),
        activeProgramsEvaluated: Math.max(0, allKeys.length),
        rowKeyVersion: "v1",
        datasetStamp: datasetStamp,
        datasetStampVersion: "offline",
        cacheHit: false,
        lastProgramsSyncUtc: normalizeText(snapshot.lastProgramsSyncUtc),
        lastProgramsSyncLocal: normalizeText(snapshot.lastProgramsSyncLocal),
      },
      summary: {
        totalPrograms: Math.max(0, (evaluation.finalOut || []).length - 1),
        eligible: Math.max(0, (evaluation.eligibleRows || []).length - 1),
        missing: Math.max(0, (evaluation.ineligibleRows || []).length - 1),
        uncheckable: Math.max(0, (evaluation.uncheckableRows || []).length - 1),
      },
      rowKeysByView: {
        all: ((evaluation.rowKeysByView && evaluation.rowKeysByView.all) || []).slice(),
        eligible: ((evaluation.rowKeysByView && evaluation.rowKeysByView.eligible) || []).slice(),
        ineligible: ((evaluation.rowKeysByView && evaluation.rowKeysByView.ineligible) || []).slice(),
        uncheckable: ((evaluation.rowKeysByView && evaluation.rowKeysByView.uncheckable) || []).slice(),
      },
      detailsByKey: window.copyWebDetailsByKey_(evaluation.detailsByKey || {}),
      results: {
        all: (evaluation.finalOut || []).slice(1),
        eligible: (evaluation.eligibleRows || []).slice(1),
        ineligible: (evaluation.ineligibleRows || []).slice(1),
        uncheckable: (evaluation.uncheckableRows || []).slice(1),
      },
    };
  }

  function makeRunProxy() {
    var successHandler = null;
    var failureHandler = null;

    function invoke(work) {
      var onSuccess = successHandler;
      var onFailure = failureHandler;
      successHandler = null;
      failureHandler = null;
      setTimeout(function () {
        try {
          var result = work();
          if (typeof onSuccess === "function") onSuccess(result);
        } catch (err) {
          if (typeof onFailure === "function") onFailure(err);
          else console.error(err);
        }
      }, 0);
      return proxy;
    }

    var proxy = {
      withSuccessHandler: function (fn) {
        successHandler = typeof fn === "function" ? fn : null;
        return proxy;
      },
      withFailureHandler: function (fn) {
        failureHandler = typeof fn === "function" ? fn : null;
        return proxy;
      },
      getWebAppBootstrapData: function () {
        return invoke(function () {
          return buildBootstrapResponse();
        });
      },
      runWebEligibility: function (payload) {
        return invoke(function () {
          return buildEligibilityResponse(payload || {});
        });
      },
    };
    return proxy;
  }

  var googleObj = window.google && typeof window.google === "object" ? window.google : {};
  if (!googleObj.script || typeof googleObj.script !== "object") googleObj.script = {};
  googleObj.script.run = makeRunProxy();
  window.google = googleObj;
})();
