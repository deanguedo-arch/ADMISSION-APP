#!/usr/bin/env node
"use strict";

const fs = require("fs");
const path = require("path");
const http = require("http");

function argValue(flag, fallback) {
  const i = process.argv.indexOf(flag);
  if (i >= 0 && i + 1 < process.argv.length) return process.argv[i + 1];
  return fallback;
}

const port = Number(argValue("--port", process.env.PORT || "5173")) || 5173;
const rootArg = argValue("--root", "apps_script");
const root = path.resolve(process.cwd(), rootArg);

if (!fs.existsSync(root)) {
  console.error(`Root path not found: ${root}`);
  process.exit(1);
}

const mime = {
  ".html": "text/html; charset=utf-8",
  ".js": "application/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".ico": "image/x-icon",
};

function readHtmlWithIncludes(filePath, stack = []) {
  const full = path.resolve(filePath);
  if (!full.startsWith(root)) {
    throw new Error(`Include outside root is not allowed: ${filePath}`);
  }
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

function safeResolve(urlPath) {
  const clean = decodeURIComponent((urlPath || "/").split("?")[0]);
  const rel = clean === "/" ? "/WebApp.html" : clean;
  const full = path.resolve(root, `.${rel}`);
  if (!full.startsWith(root)) return null;
  return full;
}

const server = http.createServer((req, res) => {
  const filePath = safeResolve(req.url || "/");
  if (!filePath) {
    res.statusCode = 403;
    res.end("Forbidden");
    return;
  }

  let target = filePath;
  if (fs.existsSync(target) && fs.statSync(target).isDirectory()) {
    target = path.join(target, "WebApp.html");
  }

  const ext = path.extname(target).toLowerCase();
  try {
    if (ext === ".html") {
      const html = readHtmlWithIncludes(target, []);
      res.setHeader("Content-Type", mime[ext] || "text/html; charset=utf-8");
      res.setHeader("Cache-Control", "no-store");
      res.end(html);
      return;
    }

    fs.readFile(target, (err, data) => {
      if (err) {
        res.statusCode = 404;
        res.end("Not found");
        return;
      }
      res.setHeader("Content-Type", mime[ext] || "application/octet-stream");
      res.setHeader("Cache-Control", "no-store");
      res.end(data);
    });
  } catch (err) {
    res.statusCode = 500;
    res.setHeader("Content-Type", "text/plain; charset=utf-8");
    res.end(String((err && err.message) || "Server error"));
  }
});

server.listen(port, () => {
  console.log(`Static preview server running on http://localhost:${port}/WebApp.html?mock=1`);
  console.log(`Serving files from: ${root}`);
});
