/**
 * Web App HTML include renderer.
 * Supports markers in HTML files: <!-- @include:FileName -->
 */

function renderWebAppHtml_() {
  return resolveWebAppHtmlIncludes_(readWebAppHtmlFile_("WebApp"), 0, {});
}

function readWebAppHtmlFile_(name) {
  const file = String(name || "").trim();
  if (!file) throw new Error("Web app include name is empty.");
  return HtmlService.createHtmlOutputFromFile(file).getContent();
}

function resolveWebAppHtmlIncludes_(html, depth, activeStack) {
  const maxDepth = 20;
  if (depth > maxDepth) {
    throw new Error("Web app HTML include depth exceeded.");
  }

  const text = String(html || "");
  return text.replace(/<!--\s*@include:([A-Za-z0-9_]+)\s*-->/g, function (_, includeName) {
    const name = String(includeName || "").trim();
    if (!name) return "";

    if (activeStack[name]) {
      throw new Error(`Web app HTML include cycle detected: ${name}`);
    }

    const nextStack = {};
    Object.keys(activeStack || {}).forEach((k) => (nextStack[k] = true));
    nextStack[name] = true;

    const included = readWebAppHtmlFile_(name);
    return resolveWebAppHtmlIncludes_(included, depth + 1, nextStack);
  });
}
