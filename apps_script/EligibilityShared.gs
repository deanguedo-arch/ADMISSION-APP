/**
 * Admissions Checker Shared Helpers
 */

function unique_(arr) {
  const seen = {};
  const out = [];
  arr.forEach((x) => {
    const k = String(x);
    if (seen[k]) return;
    seen[k] = true;
    out.push(x);
  });
  return out;
}

function title_(s) {
  const t = String(s || "");
  return t.charAt(0).toUpperCase() + t.slice(1);
}

