const assert = require("assert");
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const repoRoot = path.resolve(__dirname, "..");
const source = [
  "apps_script/EligibilityShared.gs",
  "apps_script/EligibilityProgramsData.gs",
  "apps_script/Code.gs",
  "apps_script/WebAuth.gs",
]
  .map((relativePath) => fs.readFileSync(path.join(repoRoot, relativePath), "utf8"))
  .join("\n\n");

function makeContext(options) {
  const opts = options || {};
  const props = Object.assign(
    {
      WEBAPP_GOOGLE_CLIENT_ID: "client-1",
      WEBAPP_ALLOWED_GOOGLE_CLIENT_IDS: "",
      WEBAPP_DEV_OPEN_ACCESS: "",
    },
    opts.props || {}
  );
  const cache = {};
  return {
    console,
    Date,
    JSON,
    Math,
    Number,
    String,
    Array,
    Object,
    RegExp,
    isFinite,
    Logger: { log() {} },
    PropertiesService: {
      getScriptProperties() {
        return {
          getProperty(name) {
            return Object.prototype.hasOwnProperty.call(props, name) ? props[name] : "";
          },
        };
      },
    },
    CacheService: {
      getScriptCache() {
        return {
          get(key) {
            return cache[key] || null;
          },
          put(key, value) {
            cache[key] = String(value);
          },
        };
      },
    },
    Utilities: {
      DigestAlgorithm: { SHA_256: "SHA_256" },
      computeDigest() {
        return [1, 2, 3, 4];
      },
      base64EncodeWebSafe() {
        return "digest";
      },
    },
    UrlFetchApp: {
      fetch() {
        return {
          getResponseCode() {
            return 200;
          },
          getContentText() {
            return JSON.stringify(
              Object.assign(
                {
                  aud: "client-1",
                  iss: "accounts.google.com",
                  exp: Math.floor(Date.now() / 1000) + 3600,
                  email: "person@gmail.com",
                  email_verified: "true",
                  hd: "",
                },
                opts.tokenInfo || {}
              )
            );
          },
        };
      },
    },
    Session: {
      getActiveUser() {
        return {
          getEmail() {
            return opts.sessionEmail || "";
          },
        };
      },
      getTemporaryActiveUserKey() {
        return opts.tempKey || "";
      },
    },
  };
}

function runWithContext(context, expression) {
  vm.runInNewContext(`${source}\n\nglobalThis.__result = (${expression});`, context, {
    filename: "web-auth-policy.vm.js",
  });
  return context.__result;
}

function main() {
  const gmailToken = runWithContext(makeContext(), 'verifyGoogleIdToken_("token")');
  assert.strictEqual(gmailToken.email, "person@gmail.com", "verified non-domain Google tokens should be allowed");

  const gmailSession = runWithContext(
    makeContext({ sessionEmail: "person@gmail.com" }),
    "assertDomainUser_()"
  );
  assert.strictEqual(gmailSession.email, "person@gmail.com", "non-domain session users should be allowed");

  const tempSession = runWithContext(
    makeContext({ tempKey: "temporary-google-user-key" }),
    "assertDomainUser_()"
  );
  assert.strictEqual(
    tempSession.key,
    "temporary-google-user-key",
    "temporary active-user keys should be accepted when Apps Script requires Google sign-in"
  );

  console.log("check-web-auth-google-account-policy: PASS");
}

try {
  main();
} catch (err) {
  console.error("check-web-auth-google-account-policy: FAIL");
  console.error(err && err.stack ? err.stack : err);
  process.exit(1);
}
