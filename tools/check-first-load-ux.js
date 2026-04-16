const assert = require("assert");
const fs = require("fs");
const path = require("path");

const repoRoot = path.resolve(__dirname, "..");
const stateSource = fs.readFileSync(path.join(repoRoot, "apps_script", "WebAppScriptState.html"), "utf8");
const bodySource = fs.readFileSync(path.join(repoRoot, "apps_script", "WebAppBody.html"), "utf8");
const functionsSource = fs.readFileSync(path.join(repoRoot, "apps_script", "WebAppScriptFunctions.html"), "utf8");

assert(
  stateSource.includes('const DEFAULT_PRIMARY_MODE = "explorer";'),
  "Expected explorer to be the default primary mode"
);
assert(
  stateSource.includes('const DEFAULT_RESULT_VIEW = "all";'),
  "Expected all to be the default result view"
);
assert(
  stateSource.includes('const MOBILE_SCREEN_DEFAULT = "inputs";'),
  "Expected inputs to be the default mobile screen"
);
assert(
  stateSource.includes("primaryMode: DEFAULT_PRIMARY_MODE"),
  "Expected state.primaryMode to use DEFAULT_PRIMARY_MODE"
);
assert(
  stateSource.includes("view: DEFAULT_RESULT_VIEW"),
  "Expected state.view to use DEFAULT_RESULT_VIEW"
);

const runActionsIndex = bodySource.indexOf('<div class="actions run-actions">');
const namedCoursesIndex = bodySource.indexOf("<h3>Named Courses</h3>");
assert(runActionsIndex >= 0, "Missing run actions block");
assert(namedCoursesIndex >= 0, "Missing named courses heading");
assert(
  runActionsIndex < namedCoursesIndex,
  "Expected Check Eligibility actions to appear before the course tables"
);

assert(
  functionsSource.includes("state.primaryMode = DEFAULT_PRIMARY_MODE;"),
  "Expected resetForm to restore DEFAULT_PRIMARY_MODE"
);
assert(
  functionsSource.includes("state.view = DEFAULT_RESULT_VIEW;"),
  "Expected resetForm to restore DEFAULT_RESULT_VIEW"
);
assert(
  functionsSource.includes("function renderGettingStartedStateHtml_()"),
  "Expected a guided getting-started empty state helper"
);
assert(
  functionsSource.includes("function renderDetailsIntroStateHtml_()"),
  "Expected a guided details intro helper"
);
assert(
  !functionsSource.includes("Options loaded:"),
  "Expected old debug-style options stamp copy to be removed"
);
assert(
  !functionsSource.includes("Signed in as ${state.auth.email}"),
  "Expected raw signed-in email copy to be removed from the header"
);

console.log("check-first-load-ux: PASS");
