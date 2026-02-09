/**
 * Programs Sync Webhook (optional automation)
 *
 * Purpose:
 * - Accept a CSV payload from your local pipeline and overwrite the `Programs` sheet tab.
 *
 * Setup (high-level):
 * 1) In Google Sheets: Extensions -> Apps Script
 * 2) Add this file (or paste contents)
 * 3) Set script properties:
 *    - SYNC_TOKEN: a secret string
 *    - SPREADSHEET_ID: the target sheet ID
 * 4) Deploy as Web App:
 *    - Execute as: Me
 *    - Who has access: Anyone (or Anyone with link)
 *
 * Request format:
 * POST JSON with:
 * {
 *   "token": "...",
 *   "csv": "Institution,Program,...\n...",
 *   "sheetName": "Programs" // optional
 * }
 */

function doPost(e) {
  try {
    if (!e || !e.postData || !e.postData.contents) {
      return jsonResponse_(400, { ok: false, error: "Missing request body" });
    }

    const body = JSON.parse(e.postData.contents);
    const token = String(body.token || "");
    const csv = String(body.csv || "");
    const sheetName = String(body.sheetName || "Programs");

    const props = PropertiesService.getScriptProperties();
    const expected = String(props.getProperty("SYNC_TOKEN") || "");
    const spreadsheetId = String(props.getProperty("SPREADSHEET_ID") || "");

    if (!expected || !spreadsheetId) {
      return jsonResponse_(500, { ok: false, error: "Missing SYNC_TOKEN or SPREADSHEET_ID script properties" });
    }
    if (!token || token !== expected) {
      return jsonResponse_(403, { ok: false, error: "Forbidden" });
    }
    if (!csv.trim()) {
      return jsonResponse_(400, { ok: false, error: "Empty csv" });
    }

    const ss = SpreadsheetApp.openById(spreadsheetId);
    const sheet = ss.getSheetByName(sheetName) || ss.insertSheet(sheetName);

    const values = Utilities.parseCsv(csv);
    if (!values || !values.length) {
      return jsonResponse_(400, { ok: false, error: "CSV parsed empty" });
    }

    const backup = backupSheetSnapshot_(ss, sheet, sheetName);

    sheet.clearContents();
    sheet.getRange(1, 1, values.length, values[0].length).setValues(values);
    sheet.setFrozenRows(1);

    return jsonResponse_(200, {
      ok: true,
      rows: values.length - 1,
      cols: values[0].length,
      backupSheet: backup.name,
      backupRows: backup.rows,
    });
  } catch (err) {
    return jsonResponse_(500, { ok: false, error: String(err && err.stack ? err.stack : err) });
  }
}

function jsonResponse_(status, obj) {
  const payload = Object.assign({ status }, obj || {});
  // Apps Script ContentService TextOutput does not support setting arbitrary headers or status codes.
  // Encode the intended status in the JSON payload instead.
  return ContentService.createTextOutput(JSON.stringify(payload)).setMimeType(ContentService.MimeType.JSON);
}

function backupSheetSnapshot_(ss, sourceSheet, sourceName) {
  const backupName = sourceName + "_BACKUP";
  const existing = sourceSheet.getDataRange().getValues();
  if (!existing || !existing.length) {
    return { name: backupName, rows: 0 };
  }

  const backupSheet = ss.getSheetByName(backupName) || ss.insertSheet(backupName);
  backupSheet.clearContents();

  const stampUtc = Utilities.formatDate(new Date(), "Etc/UTC", "yyyy-MM-dd HH:mm:ss'Z'");
  backupSheet.getRange(1, 1, 1, 3).setValues([["Meta_Key", "Meta_Value", "Source_Tab"]]);
  backupSheet.getRange(2, 1, 1, 3).setValues([["Backup_UTC", stampUtc, sourceName]]);
  backupSheet.getRange(3, 1, existing.length, existing[0].length).setValues(existing);
  backupSheet.setFrozenRows(3);

  return { name: backupName, rows: existing.length };
}
