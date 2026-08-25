// Job-posts sheet bridge.
// Bound to the "Job posts" spreadsheet; deployed as a web app (execute as me,
// access: anyone with the link). The daily Claude Code run calls it via
// scripts/sheet.py. Redeploy after any edit (Deploy → Manage deployments → edit → New version).

const SECRET = "a850b072ac6718208c5b3fd404a16c08"; // must match sheet-config.json in the repo
const STATUSES = ["open", "applied", "in-progress", "denied"];
const HEADERS = ["Post URL", "Company", "Match (%)", "Status", "Title", "Added"];

function doPost(e) {
  let req;
  try {
    req = JSON.parse(e.postData.contents);
  } catch (err) {
    return json_({ error: "bad json" });
  }
  if (req.secret !== SECRET) return json_({ error: "unauthorized" });
  try {
    if (req.action === "list") return json_(listAll_());
    if (req.action === "append") return json_(appendRows_(req.rows || []));
    return json_({ error: "unknown action: " + req.action });
  } catch (err) {
    return json_({ error: String(err) });
  }
}

function doGet(e) {
  if (!e.parameter || e.parameter.secret !== SECRET) return json_({ error: "unauthorized" });
  return json_(listAll_());
}

function json_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(
    ContentService.MimeType.JSON
  );
}

// A country tab is any sheet whose first header cell matches HEADERS[0].
function countrySheets_() {
  return SpreadsheetApp.getActive()
    .getSheets()
    .filter(sh => sh.getLastRow() >= 1 && sh.getRange(1, 1).getValue() === HEADERS[0]);
}

function sheetFor_(country) {
  const ss = SpreadsheetApp.getActive();
  let sh = ss.getSheetByName(country);
  if (!sh) sh = ss.insertSheet(country);
  if (sh.getRange(1, 1).getValue() !== HEADERS[0]) {
    sh.getRange(1, 1, 1, HEADERS.length).setValues([HEADERS]).setFontWeight("bold");
    sh.setFrozenRows(1);
    sh.setColumnWidth(1, 300); // Post URL
    sh.setColumnWidth(2, 180); // Company
    sh.setColumnWidth(5, 320); // Title
  }
  const rule = SpreadsheetApp.newDataValidation()
    .requireValueInList(STATUSES, true)
    .setAllowInvalid(false)
    .build();
  sh.getRange(2, 4, sh.getMaxRows() - 1, 1).setDataValidation(rule); // Status column
  return sh;
}

function listAll_() {
  const jobs = [];
  for (const sh of countrySheets_()) {
    const rows = sh.getLastRow() > 1
      ? sh.getRange(2, 1, sh.getLastRow() - 1, HEADERS.length).getValues()
      : [];
    for (const r of rows) {
      if (!r[0]) continue;
      jobs.push({
        country: sh.getName(),
        url: String(r[0]),
        company: String(r[1]),
        match: Number(r[2]) || 0,
        status: String(r[3]),
        title: String(r[4]),
        added: r[5] instanceof Date ? Utilities.formatDate(r[5], "UTC", "yyyy-MM-dd") : String(r[5]),
      });
    }
  }
  const openCount = jobs.filter(j => j.status === "open").length;
  return { jobs: jobs, open: openCount, total: jobs.length };
}

// rows: [{country, url, company, match, status, title, added}]
function appendRows_(rows) {
  const byCountry = {};
  for (const r of rows) (byCountry[r.country] = byCountry[r.country] || []).push(r);
  let added = 0;
  for (const country in byCountry) {
    const sh = sheetFor_(country);
    const existing = new Set(
      sh.getLastRow() > 1
        ? sh.getRange(2, 1, sh.getLastRow() - 1, 1).getValues().map(v => String(v[0]))
        : []
    );
    const fresh = byCountry[country].filter(r => !existing.has(r.url));
    if (fresh.length) {
      sh.getRange(sh.getLastRow() + 1, 1, fresh.length, HEADERS.length).setValues(
        fresh.map(r => [r.url, r.company, r.match, r.status || "open", r.title || "", r.added || ""])
      );
      added += fresh.length;
    }
    if (sh.getLastRow() > 2) {
      sh.getRange(2, 1, sh.getLastRow() - 1, HEADERS.length).sort({ column: 3, ascending: false });
    }
  }
  return { added: added, open: listAll_().open };
}
