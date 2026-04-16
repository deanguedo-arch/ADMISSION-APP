const assert = require("assert");
const fs = require("fs");
const path = require("path");

const repoRoot = path.resolve(__dirname, "..");
const source = fs.readFileSync(path.join(repoRoot, "apps_script/WebAppScriptFunctions.html"), "utf8");
const shell = fs.readFileSync(path.join(repoRoot, "apps_script/WebApp.html"), "utf8");

function extractRequiresAuthBlock(text) {
  const marker = "if (boot.requiresAuth) {";
  const start = text.indexOf(marker);
  assert.notStrictEqual(start, -1, "handleBootstrapResponse should branch on boot.requiresAuth");

  let depth = 0;
  let opened = false;
  for (let i = start; i < text.length; i++) {
    const ch = text[i];
    if (ch === "{") {
      depth += 1;
      opened = true;
    } else if (ch === "}") {
      depth -= 1;
      if (opened && depth === 0) return text.slice(start, i + 1);
    }
  }
  throw new Error("Could not parse boot.requiresAuth block");
}

function main() {
  const block = extractRequiresAuthBlock(source);
  assert.match(
    block,
    /initializeGoogleSignIn\s*\(\s*auth\.googleClientId\s*\|\|\s*""(?:\s*,\s*allowedDomainSuffix)?\s*\)/,
    "auth-required bootstrap must render Google sign-in with the configured client id before returning"
  );
  assert.match(
    block,
    /ui\.authLine\.textContent\s*=\s*message\s*\|\|\s*`Sign in with your \$\{allowedDomainSuffix\} account\.`;/,
    "auth-required bootstrap should surface the allowed domain in the auth line"
  );
  assert.match(
    block,
    /ui\.stamp\.textContent\s*=\s*"Awaiting sign-in";/,
    "auth-required bootstrap should leave the page in an awaiting-sign-in state"
  );
  assert.match(
    block,
    /setStatus\(\s*message\s*\|\|\s*"Sign in to load course options\.",?\s*(true\s*)?\);/s,
    "auth-required bootstrap should explain that the user must sign in to proceed"
  );
  assert.match(
    source,
    /function\s+renderGoogleAccountChooserFallback_\s*\(/,
    "web app must provide a visible account-chooser fallback when GIS does not render"
  );
  assert.match(
    source,
    /accounts\.google\.com\/AccountChooser/,
    "account-chooser fallback should point users to Google's account chooser"
  );

  const gisTag = '<script src="https://accounts.google.com/gsi/client" async defer></script>';
  assert(
    shell.includes(gisTag),
    "web app shell must load Google Identity Services before initializing sign-in"
  );
  assert(
    shell.indexOf(gisTag) < shell.indexOf('<?!= includeHtml_("WebAppScriptFunctions"); ?>'),
    "Google Identity Services must load before WebAppScriptFunctions"
  );

  console.log("check-web-auth-bootstrap: PASS");
}

try {
  main();
} catch (err) {
  console.error("check-web-auth-bootstrap: FAIL");
  console.error(err && err.stack ? err.stack : err);
  process.exit(1);
}
