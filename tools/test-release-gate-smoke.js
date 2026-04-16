const assert = require("assert");
const fs = require("fs");
const path = require("path");
const { spawnSync } = require("child_process");

const repoRoot = path.resolve(__dirname, "..");
const scriptPath = path.join(repoRoot, "tools", "check-release-gate-smoke.js");
const snapshotMetaPath = path.join(repoRoot, "offline_snapshot", "site", "snapshot.meta.json");
const BASELINE_DATASET_DATE = "2026-02-20";

function runSmoke(mode) {
  return spawnSync(process.execPath, [scriptPath, "--mode", mode], {
    cwd: repoRoot,
    encoding: "utf8",
  });
}

function textOf(result) {
  return [result.stdout || "", result.stderr || ""].join("\n");
}

function main() {
  const snapshotMeta = JSON.parse(fs.readFileSync(snapshotMetaPath, "utf8"));
  const datasetDate = String(snapshotMeta.dataset_date || "").trim();

  const current = runSmoke("current");
  assert.strictEqual(current.status, 0, `current mode should pass\n${textOf(current)}`);
  assert.match(textOf(current), /check-release-gate-smoke: PASS/, "current mode should print PASS");
  assert.match(textOf(current), /mode=current/, "current mode output should include the mode");
  assert.match(
    textOf(current),
    new RegExp(`dataset_date=${datasetDate.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}`),
    "current mode output should include the snapshot dataset date"
  );

  const baseline = runSmoke("baseline");
  if (datasetDate === BASELINE_DATASET_DATE) {
    assert.strictEqual(baseline.status, 0, `baseline mode should pass on the locked baseline\n${textOf(baseline)}`);
    assert.match(textOf(baseline), /check-release-gate-smoke: PASS/, "baseline mode should print PASS");
  } else {
    assert.strictEqual(baseline.status, 1, `baseline mode should fail off-baseline\n${textOf(baseline)}`);
    assert.match(
      textOf(baseline),
      new RegExp(
        `baseline mode requires dataset_date=${BASELINE_DATASET_DATE.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")} but found ${datasetDate.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}`
      ),
      "baseline mode should fail with an explicit dataset date mismatch"
    );
  }

  console.log("test-release-gate-smoke: PASS");
}

try {
  main();
} catch (err) {
  console.error("test-release-gate-smoke: FAIL");
  console.error(err && err.stack ? err.stack : err);
  process.exit(1);
}
