const assert = require("assert");
const fs = require("fs");
const path = require("path");

const repoRoot = path.resolve(__dirname, "..");
const workflowPath = path.join(repoRoot, ".github", "workflows", "refresh_and_sync.yml");
const workflow = fs.readFileSync(workflowPath, "utf8");

assert(
  !/\n\s+skip_scrape:\s*\n/.test(workflow),
  "STEP 2 workflow_dispatch should not expose skip_scrape on GitHub Actions runs"
);

assert(
  !/inputs\.skip_scrape/.test(workflow),
  "STEP 2 workflow should not forward inputs.skip_scrape into RUN_ALL"
);

assert(
  !/-SkipScrape/.test(workflow),
  "STEP 2 workflow should not pass -SkipScrape on GitHub-hosted runners"
);

console.log("check-refresh-workflow-no-skip-scrape: PASS");
