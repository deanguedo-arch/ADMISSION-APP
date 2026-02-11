/**
 * Admissions Checker Web Auth + Input Surface
 */

function getWebAppClientConfig_() {
  const clientIds = getWebAppAllowedGoogleClientIds_();
  return {
    googleClientId: clientIds.length ? clientIds[0] : "",
  };
}

function getWebAppAllowedGoogleClientIds_() {
  const props = PropertiesService.getScriptProperties();
  const csv = String(props.getProperty(WEBAPP_ALLOWED_GOOGLE_CLIENT_IDS_PROPERTY) || "").trim();
  const primary = String(props.getProperty(WEBAPP_GOOGLE_CLIENT_ID_PROPERTY) || "").trim();
  const parts = [];

  if (csv) {
    csv.split(",").forEach((item) => {
      const id = String(item || "").trim();
      if (id) parts.push(id);
    });
  }
  if (primary) parts.push(primary);

  return unique_(parts);
}

function sanitizeWebPayload_(payload) {
  const root =
    payload && typeof payload === "object" && !Array.isArray(payload) ? payload : {};
  assertAllowedObjectKeys_(root, ["auth", "namedCourses", "manualElectives"], "request");

  return {
    auth: sanitizeWebAuthPayload_(root.auth),
    namedCourses: Array.isArray(root.namedCourses) ? root.namedCourses : [],
    manualElectives: Array.isArray(root.manualElectives) ? root.manualElectives : [],
  };
}

function sanitizeWebAuthPayload_(authPayload) {
  const auth =
    authPayload && typeof authPayload === "object" && !Array.isArray(authPayload)
      ? authPayload
      : {};
  assertAllowedObjectKeys_(auth, ["idToken"], "auth");

  const idToken = String(auth.idToken || "").trim();
  if (idToken.length > WEBAPP_MAX_ID_TOKEN_LENGTH) {
    throw new Error("Invalid sign-in token length.");
  }
  return { idToken };
}

function assertAllowedObjectKeys_(obj, allowedKeys, label) {
  if (!obj || typeof obj !== "object" || Array.isArray(obj)) return;
  const allowed = {};
  (allowedKeys || []).forEach((k) => (allowed[String(k)] = true));
  Object.keys(obj).forEach((k) => {
    if (allowed[k]) return;
    throw new Error(`Unexpected field "${label}.${k}" was sent. Remove personal info and retry.`);
  });
}

function assertAuthorizedWebUser_(authPayload) {
  const auth = sanitizeWebAuthPayload_(authPayload);
  const devOpenRaw = String(
    PropertiesService.getScriptProperties().getProperty(WEBAPP_DEV_OPEN_ACCESS_PROPERTY) || ""
  )
    .trim()
    .toLowerCase();
  const devOpenAccess =
    devOpenRaw === "1" || devOpenRaw === "true" || devOpenRaw === "yes" || devOpenRaw === "on";
  if (auth.idToken) {
    try {
      return verifyGoogleIdToken_(auth.idToken);
    } catch (err) {
      if (!devOpenAccess) throw err;
      Logger.log(`Web auth token fallback (dev open access): ${String(err && err.message ? err.message : err)}`);
    }
  }
  // Backward-compatible fallback for Workspace deployments that expose ActiveUser email.
  try {
    return assertDomainUser_();
  } catch (err) {
    if (!devOpenAccess) throw err;
    return { email: "", tempKey: "dev-open-access", key: "dev-open-access" };
  }
}

function verifyGoogleIdToken_(idToken) {
  const token = String(idToken || "").trim();
  const devOpenRaw = String(
    PropertiesService.getScriptProperties().getProperty(WEBAPP_DEV_OPEN_ACCESS_PROPERTY) || ""
  )
    .trim()
    .toLowerCase();
  const devOpenAccess =
    devOpenRaw === "1" || devOpenRaw === "true" || devOpenRaw === "yes" || devOpenRaw === "on";
  if (!token) {
    throw new Error("Sign in with your school account and try again.");
  }

  const cache = CacheService.getScriptCache();
  const digest = Utilities.base64EncodeWebSafe(
    Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, token)
  ).replace(/=+$/g, "");
  const cacheKey = `WEBAPP_IDT_${digest.slice(0, 80)}`;
  const nowSec = Math.floor(Date.now() / 1000);
  const cachedRaw = cache.get(cacheKey);

  if (cachedRaw) {
    try {
      const cached = JSON.parse(cachedRaw);
      const cachedExp = toNumber_(cached && cached.exp);
      if (isFinite(cachedExp) && cachedExp > nowSec + 10) {
        return {
          email: String(cached.email || "").toLowerCase(),
          tempKey: "",
          key: String(cached.email || "").toLowerCase(),
        };
      }
    } catch (err) {}
  }

  const response = UrlFetchApp.fetch(
    `${WEBAPP_GOOGLE_TOKENINFO_URL}${encodeURIComponent(token)}`,
    { muteHttpExceptions: true }
  );
  if (response.getResponseCode() !== 200) {
    throw new Error("Google sign-in validation failed. Please sign in again.");
  }

  let tokenInfo = null;
  try {
    tokenInfo = JSON.parse(response.getContentText() || "{}");
  } catch (err) {
    throw new Error("Could not validate your sign-in token.");
  }

  const allowedClientIds = getWebAppAllowedGoogleClientIds_();
  if (!allowedClientIds.length && !devOpenAccess) {
    throw new Error(
      `Web app auth is not configured. Set Script Property ${WEBAPP_GOOGLE_CLIENT_ID_PROPERTY}.`
    );
  }

  const aud = String((tokenInfo && tokenInfo.aud) || "").trim();
  if (!devOpenAccess && allowedClientIds.indexOf(aud) < 0) {
    throw new Error("This sign-in token is not from an approved client.");
  }

  const iss = String((tokenInfo && tokenInfo.iss) || "").trim();
  if (!(iss === "accounts.google.com" || iss === "https://accounts.google.com")) {
    throw new Error("Token issuer is not trusted.");
  }

  const exp = Math.round(toNumber_(tokenInfo && tokenInfo.exp));
  if (!isFinite(exp) || exp <= nowSec) {
    throw new Error("Your sign-in expired. Please sign in again.");
  }

  const email = String((tokenInfo && tokenInfo.email) || "")
    .trim()
    .toLowerCase();
  const emailVerified = String((tokenInfo && tokenInfo.email_verified) || "")
    .trim()
    .toLowerCase();
  const hostedDomain = String((tokenInfo && tokenInfo.hd) || "")
    .trim()
    .toLowerCase();

  if (!email || emailVerified !== "true") {
    throw new Error("Google account email is not verified.");
  }
  if (!devOpenAccess) {
    if (!email.endsWith(WEBAPP_ALLOWED_DOMAIN_SUFFIX)) {
      throw new Error(`Access is restricted to ${WEBAPP_ALLOWED_DOMAIN_SUFFIX} users.`);
    }
    if (hostedDomain !== WEBAPP_ALLOWED_DOMAIN) {
      throw new Error(`Sign in with your ${WEBAPP_ALLOWED_DOMAIN} school account.`);
    }
  }

  const ttl = Math.max(30, Math.min(WEBAPP_ID_TOKEN_CACHE_SECONDS, exp - nowSec));
  cache.put(cacheKey, JSON.stringify({ email, exp }), ttl);
  return { email, tempKey: "", key: email };
}

function assertDomainUser_() {
  const devOpenRaw = String(
    PropertiesService.getScriptProperties().getProperty(WEBAPP_DEV_OPEN_ACCESS_PROPERTY) || ""
  )
    .trim()
    .toLowerCase();
  const devOpenAccess =
    devOpenRaw === "1" || devOpenRaw === "true" || devOpenRaw === "yes" || devOpenRaw === "on";
  let email = "";
  try {
    email = String((Session.getActiveUser() && Session.getActiveUser().getEmail()) || "")
      .trim()
      .toLowerCase();
  } catch (err) {}

  if (!email) {
    if (devOpenAccess) return { email: "", tempKey: "dev-open-access", key: "dev-open-access" };
    throw new Error("Sign in with your school account and retry.");
  }
  if (!devOpenAccess && !email.endsWith(WEBAPP_ALLOWED_DOMAIN_SUFFIX)) {
    throw new Error(`Access is restricted to ${WEBAPP_ALLOWED_DOMAIN_SUFFIX} users.`);
  }

  return { email, tempKey: "", key: email };
}

function assertWebRateLimit_(identity, action) {
  const cache = CacheService.getScriptCache();
  const safeKey = String((identity && identity.key) || "unknown").replace(/[^a-zA-Z0-9@._-]/g, "_");
  const keyBase = `WEBAPP_RL_${safeKey}`;
  const now = Date.now();

  const intervalKey = `${keyBase}_LAST`;
  const lastAt = toNumber_(cache.get(intervalKey));
  if (isFinite(lastAt) && now - lastAt < WEBAPP_RATE_LIMIT_MIN_INTERVAL_MS) {
    throw new Error("Please wait 2 seconds before trying again.");
  }
  cache.put(intervalKey, String(now), 120);

  const windowKey = `${keyBase}_WINDOW`;
  const countKey = `${keyBase}_COUNT`;
  let windowStart = toNumber_(cache.get(windowKey));
  let count = toNumber_(cache.get(countKey));

  if (!isFinite(windowStart) || now - windowStart >= WEBAPP_RATE_LIMIT_WINDOW_SECONDS * 1000) {
    windowStart = now;
    count = 0;
  }
  count = (isFinite(count) ? count : 0) + 1;

  cache.put(windowKey, String(windowStart), WEBAPP_RATE_LIMIT_WINDOW_SECONDS + 30);
  cache.put(countKey, String(count), WEBAPP_RATE_LIMIT_WINDOW_SECONDS + 30);

  if (count > WEBAPP_RATE_LIMIT_MAX_PER_WINDOW) {
    throw new Error("Too many requests. Please wait about a minute and try again.");
  }
}

function sanitizeWebMessage_(msg) {
  const text = String(msg || "Access blocked.");
  return text.replace(/[<>&]/g, "");
}

function listNamedCourseOptions_() {
  const alias = courseAliases_();
  const fromAlias = Object.keys(alias).map((k) => String(alias[k] || "").trim());
  const byKey = {};

  fromAlias
    .concat(listElectiveCourseOptions_())
    .filter(Boolean)
    .forEach((course) => {
      const key = normalizeCourseKey_(course);
      if (!key) return;
      byKey[key] = formatCourseName_(key);
    });

  return Object.keys(byKey)
    .map((key) => byKey[key])
    .sort((a, b) => String(a).localeCompare(String(b)));
}

function sanitizeWebNamedCourses_(rows) {
  const list = Array.isArray(rows) ? rows : [];
  const allowedByKey = buildWebAllowedCourseSet_(listNamedCourseOptions_());
  const out = [];
  for (let i = 0; i < list.length && i < 80; i++) {
    const item = list[i];
    if (!item || typeof item !== "object" || Array.isArray(item)) {
      throw new Error(`Invalid namedCourses row at position ${i + 1}.`);
    }
    assertAllowedObjectKeys_(item, ["course", "mark"], `namedCourses[${i}]`);
    const course = String(item.course || "").trim();
    const mark = toNumber_(item.mark);
    if (!course && !isFinite(mark)) continue;
    if (!course || !isFinite(mark)) {
      throw new Error(`Named course row ${i + 1} must include both course and mark.`);
    }
    const key = normalizeCourseKey_(course);
    if (!allowedByKey[key]) {
      throw new Error(`Unsupported course in named row ${i + 1}. Use the course list options only.`);
    }
    out.push([formatCourseName_(key), Math.max(0, Math.min(100, mark))]);
  }
  return out;
}

function sanitizeWebManualElectives_(rows) {
  const list = Array.isArray(rows) ? rows : [];
  const allowedByKey = buildWebAllowedCourseSet_(listElectiveCourseOptions_());
  const out = [];
  for (let i = 0; i < list.length && i < 25; i++) {
    const item = list[i];
    if (!item || typeof item !== "object" || Array.isArray(item)) {
      throw new Error(`Invalid manualElectives row at position ${i + 1}.`);
    }
    assertAllowedObjectKeys_(item, ["course", "group", "mark"], `manualElectives[${i}]`);
    const course = String(item.course || "").trim();
    const mark = toNumber_(item.mark);
    if (!course && !isFinite(mark)) continue;
    if (!course || !isFinite(mark)) {
      throw new Error(`Manual elective row ${i + 1} must include both course and mark.`);
    }
    const key = normalizeCourseKey_(course);
    if (!allowedByKey[key]) {
      throw new Error(`Unsupported course in manual row ${i + 1}. Use elective dropdown values only.`);
    }
    const group = String(item.group || "").trim().toUpperCase();
    if (group && !["A", "B", "C", "D"].includes(group)) {
      throw new Error(`Invalid group in manual row ${i + 1}. Use A, B, C, or D.`);
    }
    out.push([formatCourseName_(key), group || "", Math.max(0, Math.min(100, mark))]);
  }
  return out;
}

function buildWebAllowedCourseSet_(courses) {
  const out = {};
  (courses || []).forEach((course) => {
    const key = normalizeCourseKey_(course);
    if (key) out[key] = true;
  });
  return out;
}

function copyWebDetailsByKey_(detailsByKey) {
  const out = {};
  const src = detailsByKey && typeof detailsByKey === "object" ? detailsByKey : {};
  Object.keys(src).forEach((rawKey) => {
    const key = String(rawKey || "").trim();
    if (!key) return;
    const value = src[rawKey];
    try {
      out[key] = JSON.parse(JSON.stringify(value || {}));
    } catch (err) {
      out[key] = {};
    }
  });
  return out;
}

