const fs = require("fs");
const path = require("path");
const vm = require("vm");

const repoRoot = path.resolve(__dirname, "..");
const snapshotMetaPath = path.join(repoRoot, "offline_snapshot", "site", "snapshot.meta.json");
const runtimePaths = [
  path.join(repoRoot, "offline_snapshot", "site", "runtime", "eligibility_core.js"),
  path.join(repoRoot, "offline_snapshot", "site", "data", "snapshot_data.js"),
  path.join(repoRoot, "offline_snapshot", "site", "runtime", "offline_bridge.js"),
];

const BASELINE_DATASET_DATE = "2026-02-20";

const PROFILE_A = {
  key: "A",
  label: "Profile A",
  namedCourses: [
    { course: "English 30-1", mark: 92 },
    { course: "Math 30-1", mark: 90 },
    { course: "Math 31", mark: 86 },
    { course: "Social Studies 30-1", mark: 88 },
    { course: "Biology 30", mark: 90 },
    { course: "Chemistry 30", mark: 89 },
    { course: "Physics 30", mark: 87 },
    { course: "French 30", mark: 84 },
    { course: "Art 30", mark: 82 },
    { course: "Drama 30", mark: 80 },
  ],
  expectedSummary: {
    eligible: 262,
    ineligible: 0,
    uncheckable: 37,
  },
};

const PROFILE_B = {
  key: "B",
  label: "Profile B",
  namedCourses: [
    { course: "English 30-2", mark: 60 },
    { course: "Math 30-2", mark: 52 },
    { course: "Social Studies 30-2", mark: 55 },
    { course: "Science 30", mark: 50 },
    { course: "Art 30", mark: 55 },
  ],
  expectedSummary: {
    eligible: 66,
    ineligible: 196,
    uncheckable: 37,
  },
};

const PROFILES = [PROFILE_A, PROFILE_B];

const BASELINE_ANCHORS = [
  {
    profile: "A",
    institution: "NAIT",
    program: "Bachelor of Business Administration (BBA) Co-operative Education",
    snapshotResult: "Likely eligible",
    confidence: "High",
  },
  {
    profile: "B",
    institution: "NAIT",
    program: "Bachelor of Business Administration (BBA) Co-operative Education",
    snapshotResult: "Likely ineligible",
    confidence: "High",
  },
  {
    profile: "A",
    institution: "MacEwan",
    program: "Open Studies",
    snapshotResult: "Uncheckable",
  },
  {
    profile: "B",
    institution: "MacEwan",
    program: "Open Studies",
    snapshotResult: "Uncheckable",
  },
  {
    profile: "A",
    institution: "NorQuest",
    program: "Building Service Worker",
    snapshotResult: "Likely eligible",
    confidence: "Low",
  },
  {
    profile: "B",
    institution: "NorQuest",
    program: "Building Service Worker",
    snapshotResult: "Likely eligible",
    confidence: "Low",
  },
];

const CURRENT_ANCHORS = [
  {
    profile: "A",
    institution: "MacEwan",
    program: "Open Studies",
    snapshotResult: "Uncheckable",
  },
  {
    profile: "B",
    institution: "MacEwan",
    program: "Open Studies",
    snapshotResult: "Uncheckable",
  },
  {
    profile: "A",
    institution: "NorQuest",
    program: "Building Service Worker",
    allowedSnapshotResults: ["Likely eligible", "Uncheckable"],
    allowedConfidence: ["Low", "Uncheckable"],
  },
  {
    profile: "B",
    institution: "NorQuest",
    program: "Building Service Worker",
    allowedSnapshotResults: ["Likely eligible", "Uncheckable"],
    allowedConfidence: ["Low", "Uncheckable"],
  },
  {
    profile: "A",
    institution: "NAIT",
    programStartsWith: "Bachelor of Business Administration - ",
    unique: false,
    minMatches: 1,
    requireNonBlankSnapshotResult: true,
  },
  {
    profile: "B",
    institution: "NAIT",
    programStartsWith: "Bachelor of Business Administration - ",
    unique: false,
    minMatches: 1,
    requireNonBlankSnapshotResult: true,
  },
];

function usageError(message) {
  const err = new Error(message);
  err.isUsage = true;
  return err;
}

function parseArgs(argv) {
  let mode = "current";
  for (let i = 0; i < argv.length; i++) {
    const token = String(argv[i] || "").trim();
    if (!token) continue;
    if (token === "--mode") {
      if (i + 1 >= argv.length) throw usageError("Missing value for --mode. Use current or baseline.");
      mode = String(argv[i + 1] || "").trim().toLowerCase();
      i += 1;
      continue;
    }
    throw usageError(`Unknown argument: ${token}`);
  }
  if (!(mode === "current" || mode === "baseline")) {
    throw usageError(`Invalid mode "${mode}". Use current or baseline.`);
  }
  return { mode };
}

function readJson(filePath) {
  if (!fs.existsSync(filePath)) {
    throw new Error(`Missing required file: ${path.relative(repoRoot, filePath)}`);
  }
  return JSON.parse(fs.readFileSync(filePath, "utf8"));
}

function ensureRuntimeFilesExist() {
  runtimePaths.forEach((filePath) => {
    if (!fs.existsSync(filePath)) {
      throw new Error(
        `Missing required snapshot runtime file: ${path.relative(repoRoot, filePath)}. Rebuild the offline snapshot first.`
      );
    }
  });
}

function loadSnapshotContext() {
  ensureRuntimeFilesExist();

  const context = {
    console,
    Date,
    Math,
    Number,
    String,
    Array,
    Object,
    RegExp,
    JSON,
    Promise,
    isFinite,
    NaN,
    setTimeout,
    clearTimeout,
  };
  context.window = context;
  context.globalThis = context;

  const vmContext = vm.createContext(context);
  runtimePaths.forEach((filePath) => {
    const code = fs.readFileSync(filePath, "utf8");
    vm.runInContext(code, vmContext, { filename: path.relative(repoRoot, filePath) });
  });
  if (!vmContext.google || !vmContext.google.script || !vmContext.google.script.run) {
    throw new Error("Snapshot runtime did not expose google.script.run. Rebuild the offline snapshot.");
  }
  return vmContext;
}

function callRun(context, fnName, payload) {
  return new Promise((resolve, reject) => {
    try {
      context.google.script.run.withSuccessHandler(resolve).withFailureHandler(reject)[fnName](payload || {});
    } catch (err) {
      reject(err);
    }
  });
}

function normalizeSummary(summary) {
  const src = summary && typeof summary === "object" ? summary : {};
  return {
    totalPrograms: Number(src.totalPrograms || 0),
    eligible: Number(src.eligible || 0),
    ineligible: Number(src.missing || 0),
    uncheckable: Number(src.uncheckable || 0),
  };
}

function profilePayload(profile) {
  return {
    namedCourses: (profile.namedCourses || []).map((item) => ({
      course: String(item.course || "").trim(),
      mark: Number(item.mark),
    })),
    manualElectives: [],
  };
}

function addFailure(failures, message) {
  failures.push(String(message || "Unknown failure"));
}

function requireObject(value, label) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new Error(`${label} is missing or invalid.`);
  }
  return value;
}

function buildAnchorLabel(anchor) {
  const programLabel = anchor.programStartsWith
    ? `${anchor.programStartsWith}*`
    : String(anchor.program || "").trim();
  return `${anchor.institution} | ${programLabel} | Profile ${anchor.profile}`;
}

function findAnchor(result, anchor, failures) {
  const details = requireObject(result.detailsByKey, "detailsByKey");
  const matches = Object.values(details).filter((detail) => {
    if (!detail || typeof detail !== "object") return false;
    if (String(detail.institution || "").trim() !== anchor.institution) return false;
    const program = String(detail.program || "").trim();
    if (anchor.programStartsWith) return program.startsWith(anchor.programStartsWith);
    return program === anchor.program;
  });

  const minMatches = Math.max(1, Number(anchor.minMatches || 1));
  if (matches.length < minMatches) {
    addFailure(
      failures,
      `Missing anchor program: ${buildAnchorLabel(anchor)} (need ${minMatches}, found ${matches.length})`
    );
    return null;
  }
  if (anchor.unique !== false && matches.length > 1) {
    const labels = matches.map((detail) => `${detail.institution} | ${detail.program} | ${detail.credential || "Unknown"}`);
    addFailure(
      failures,
      `Ambiguous anchor program (${matches.length} matches): ${buildAnchorLabel(anchor)} -> ${labels.join("; ")}`
    );
    return null;
  }
  return matches;
}

function validateAnchor(details, anchor, failures) {
  if (!details || !details.length) return;
  const label = buildAnchorLabel(anchor);
  details.forEach((detail) => {
    const detailLabel =
      details.length > 1 ? `${label} -> ${detail.program} (${detail.credential || "Unknown"})` : label;
    const snapshotResult = String(detail.snapshotResult || "").trim();
    const confidence = String(detail.confidence || "").trim();

    if (anchor.requireNonBlankSnapshotResult && !snapshotResult) {
      addFailure(failures, `${detailLabel} returned a blank snapshot result`);
    }
    if (anchor.snapshotResult && snapshotResult !== anchor.snapshotResult) {
      addFailure(
        failures,
        `${detailLabel} expected snapshot result ${anchor.snapshotResult} but found ${snapshotResult || "(blank)"}`
      );
    }
    if (anchor.snapshotResultNot && snapshotResult === anchor.snapshotResultNot) {
      addFailure(failures, `${detailLabel} should not be ${anchor.snapshotResultNot}`);
    }
    if (anchor.allowedSnapshotResults && anchor.allowedSnapshotResults.indexOf(snapshotResult) < 0) {
      addFailure(
        failures,
        `${detailLabel} expected snapshot result in [${anchor.allowedSnapshotResults.join(", ")}] but found ${snapshotResult || "(blank)"}`
      );
    }
    if (anchor.confidence && confidence !== anchor.confidence) {
      addFailure(failures, `${detailLabel} expected confidence ${anchor.confidence} but found ${confidence || "(blank)"}`);
    }
    if (anchor.allowedConfidence && anchor.allowedConfidence.indexOf(confidence) < 0) {
      addFailure(
        failures,
        `${detailLabel} expected confidence in [${anchor.allowedConfidence.join(", ")}] but found ${confidence || "(blank)"}`
      );
    }
  });
}

function validateSharedShape(profile, result, snapshotMeta, failures) {
  const summary = normalizeSummary(result.summary);
  const rowKeysByView = requireObject(result.rowKeysByView, "rowKeysByView");
  const detailsByKey = requireObject(result.detailsByKey, "detailsByKey");
  const results = requireObject(result.results, "results");
  const profileLabel = `${profile.label}`;

  if (!Array.isArray(rowKeysByView.all)) addFailure(failures, `${profileLabel}: rowKeysByView.all is missing`);
  if (!Array.isArray(rowKeysByView.eligible)) addFailure(failures, `${profileLabel}: rowKeysByView.eligible is missing`);
  if (!Array.isArray(rowKeysByView.ineligible)) addFailure(failures, `${profileLabel}: rowKeysByView.ineligible is missing`);
  if (!Array.isArray(rowKeysByView.uncheckable)) addFailure(failures, `${profileLabel}: rowKeysByView.uncheckable is missing`);
  if (!Array.isArray(results.all)) addFailure(failures, `${profileLabel}: results.all is missing`);
  if (!Array.isArray(results.eligible)) addFailure(failures, `${profileLabel}: results.eligible is missing`);
  if (!Array.isArray(results.ineligible)) addFailure(failures, `${profileLabel}: results.ineligible is missing`);
  if (!Array.isArray(results.uncheckable)) addFailure(failures, `${profileLabel}: results.uncheckable is missing`);

  if (summary.eligible + summary.ineligible + summary.uncheckable !== summary.totalPrograms) {
    addFailure(
      failures,
      `${profileLabel}: summary totals do not add up (${summary.eligible} + ${summary.ineligible} + ${summary.uncheckable} != ${summary.totalPrograms})`
    );
  }

  if (Array.isArray(results.all) && results.all.length !== summary.totalPrograms) {
    addFailure(failures, `${profileLabel}: results.all length ${results.all.length} != totalPrograms ${summary.totalPrograms}`);
  }
  if (Array.isArray(results.eligible) && results.eligible.length !== summary.eligible) {
    addFailure(failures, `${profileLabel}: results.eligible length ${results.eligible.length} != eligible ${summary.eligible}`);
  }
  if (Array.isArray(results.ineligible) && results.ineligible.length !== summary.ineligible) {
    addFailure(failures, `${profileLabel}: results.ineligible length ${results.ineligible.length} != ineligible ${summary.ineligible}`);
  }
  if (Array.isArray(results.uncheckable) && results.uncheckable.length !== summary.uncheckable) {
    addFailure(failures, `${profileLabel}: results.uncheckable length ${results.uncheckable.length} != uncheckable ${summary.uncheckable}`);
  }

  if (Array.isArray(rowKeysByView.all) && rowKeysByView.all.length !== summary.totalPrograms) {
    addFailure(failures, `${profileLabel}: rowKeysByView.all length ${rowKeysByView.all.length} != totalPrograms ${summary.totalPrograms}`);
  }
  if (Array.isArray(rowKeysByView.eligible) && rowKeysByView.eligible.length !== summary.eligible) {
    addFailure(failures, `${profileLabel}: rowKeysByView.eligible length ${rowKeysByView.eligible.length} != eligible ${summary.eligible}`);
  }
  if (Array.isArray(rowKeysByView.ineligible) && rowKeysByView.ineligible.length !== summary.ineligible) {
    addFailure(failures, `${profileLabel}: rowKeysByView.ineligible length ${rowKeysByView.ineligible.length} != ineligible ${summary.ineligible}`);
  }
  if (Array.isArray(rowKeysByView.uncheckable) && rowKeysByView.uncheckable.length !== summary.uncheckable) {
    addFailure(failures, `${profileLabel}: rowKeysByView.uncheckable length ${rowKeysByView.uncheckable.length} != uncheckable ${summary.uncheckable}`);
  }

  if (Object.keys(detailsByKey).length !== summary.totalPrograms) {
    addFailure(failures, `${profileLabel}: detailsByKey size ${Object.keys(detailsByKey).length} != totalPrograms ${summary.totalPrograms}`);
  }

  const metaTotal = Number(snapshotMeta.row_count_total || 0);
  if (metaTotal > 0 && summary.totalPrograms !== metaTotal) {
    addFailure(failures, `${profileLabel}: totalPrograms ${summary.totalPrograms} != snapshot meta row_count_total ${metaTotal}`);
  }

  return summary;
}

function validateBaselineSummary(profile, summary, failures) {
  const expected = profile.expectedSummary || {};
  if (summary.eligible !== Number(expected.eligible || 0)) {
    addFailure(failures, `${profile.label}: expected eligible ${expected.eligible} but found ${summary.eligible}`);
  }
  if (summary.ineligible !== Number(expected.ineligible || 0)) {
    addFailure(failures, `${profile.label}: expected ineligible ${expected.ineligible} but found ${summary.ineligible}`);
  }
  if (summary.uncheckable !== Number(expected.uncheckable || 0)) {
    addFailure(failures, `${profile.label}: expected uncheckable ${expected.uncheckable} but found ${summary.uncheckable}`);
  }
}

async function runProfiles(context) {
  const out = {};
  for (const profile of PROFILES) {
    out[profile.key] = await callRun(context, "runWebEligibility", profilePayload(profile));
  }
  return out;
}

function printPass(mode, snapshotMeta, summaries) {
  const datasetDate = String(snapshotMeta.dataset_date || "").trim();
  console.log(`check-release-gate-smoke: PASS mode=${mode} dataset_date=${datasetDate}`);
  PROFILES.forEach((profile) => {
    const summary = summaries[profile.key];
    console.log(
      `${profile.label}: total=${summary.totalPrograms} eligible=${summary.eligible} ineligible=${summary.ineligible} uncheckable=${summary.uncheckable}`
    );
  });
}

function printFail(mode, snapshotMeta, failures) {
  const datasetDate = String(snapshotMeta.dataset_date || "").trim();
  console.error(`check-release-gate-smoke: FAIL mode=${mode} dataset_date=${datasetDate}`);
  failures.forEach((failure) => console.error(`- ${failure}`));
}

async function main() {
  const { mode } = parseArgs(process.argv.slice(2));
  const snapshotMeta = readJson(snapshotMetaPath);
  const datasetDate = String(snapshotMeta.dataset_date || "").trim();
  const failures = [];

  if (mode === "baseline" && datasetDate !== BASELINE_DATASET_DATE) {
    addFailure(
      failures,
      `baseline mode requires dataset_date=${BASELINE_DATASET_DATE} but found ${datasetDate || "(blank)"}`
    );
    printFail(mode, snapshotMeta, failures);
    process.exit(1);
  }

  const context = loadSnapshotContext();
  const resultsByProfile = await runProfiles(context);
  const summaries = {};

  PROFILES.forEach((profile) => {
    const result = resultsByProfile[profile.key];
    const summary = validateSharedShape(profile, result, snapshotMeta, failures);
    summaries[profile.key] = summary;
  });

  if (mode === "baseline") {
    PROFILES.forEach((profile) => {
      validateBaselineSummary(profile, summaries[profile.key], failures);
    });
    BASELINE_ANCHORS.forEach((anchor) => {
      const detail = findAnchor(resultsByProfile[anchor.profile], anchor, failures);
      validateAnchor(detail, anchor, failures);
    });
  } else {
    CURRENT_ANCHORS.forEach((anchor) => {
      const detail = findAnchor(resultsByProfile[anchor.profile], anchor, failures);
      validateAnchor(detail, anchor, failures);
    });
  }

  if (failures.length) {
    printFail(mode, snapshotMeta, failures);
    process.exit(1);
  }

  printPass(mode, snapshotMeta, summaries);
}

main().catch((err) => {
  const mode = (() => {
    try {
      return parseArgs(process.argv.slice(2)).mode;
    } catch (parseErr) {
      return "unknown";
    }
  })();
  let snapshotMeta = { dataset_date: "" };
  try {
    snapshotMeta = readJson(snapshotMetaPath);
  } catch (metaErr) {}

  const message = err && err.message ? err.message : String(err || "Unknown error");
  printFail(mode, snapshotMeta, [message]);
  process.exit(err && err.isUsage ? 2 : 1);
});
