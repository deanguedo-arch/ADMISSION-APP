#!/usr/bin/env node
"use strict";

const fs = require("fs");
const path = require("path");

function argValue(flag, fallback) {
  const i = process.argv.indexOf(flag);
  if (i >= 0 && i + 1 < process.argv.length) return process.argv[i + 1];
  return fallback;
}

const inputPath = path.resolve(process.cwd(), argValue("--input", "apps_script/WebApp.html"));
const outputPath = path.resolve(process.cwd(), argValue("--output", "docs/index.html"));
const root = path.dirname(inputPath);

if (!fs.existsSync(inputPath)) {
  console.error(`Input file not found: ${inputPath}`);
  process.exit(1);
}

function readHtmlWithIncludes(filePath, stack = []) {
  const full = path.resolve(filePath);
  if (stack.includes(full)) {
    throw new Error(`Include cycle detected: ${full}`);
  }

  const raw = fs.readFileSync(full, "utf8");
  const includeRx =
    /(?:<!--\s*@include:([A-Za-z0-9_]+)\s*-->)|(?:<\?!=\s*includeHtml_\(\s*["']([A-Za-z0-9_]+)["']\s*\)\s*;?\s*\?>)/g;

  return raw.replace(includeRx, (_, markerName, scriptletName) => {
    const name = String(markerName || scriptletName || "").trim();
    const includePath = path.join(root, `${name}.html`);
    if (!fs.existsSync(includePath)) {
      throw new Error(`Missing include file: ${includePath}`);
    }
    return readHtmlWithIncludes(includePath, stack.concat(full));
  });
}

try {
  const compiled = readHtmlWithIncludes(inputPath, []);
  if (/<\?!=\s*includeHtml_\(/.test(compiled) || /<!--\s*@include:[A-Za-z0-9_]+\s*-->/.test(compiled)) {
    throw new Error("Compiled output still contains include directives.");
  }

  fs.mkdirSync(path.dirname(outputPath), { recursive: true });
  fs.writeFileSync(outputPath, compiled, "utf8");
  console.log(`Compiled ${inputPath} -> ${outputPath}`);
} catch (err) {
  console.error(String((err && err.message) || err));
  process.exit(1);
}
