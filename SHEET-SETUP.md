# One-time Google Sheet setup

The job list lives in a Google Sheet in your Drive; a small Apps Script web app bound to it lets the daily run read and append rows. You edit the **Status** column directly in Google Sheets.

## Steps (~5 minutes)

1. Create a new blank spreadsheet in your Drive (e.g. name it **Job posts**): https://sheets.new
2. In the spreadsheet: **Extensions → Apps Script**.
3. Delete the default code and paste the full contents of [`apps-script/Code.gs`](apps-script/Code.gs). Save (⌘S).
4. **Deploy → New deployment**, gear icon → type **Web app**:
   - Description: `job-posts bridge`
   - Execute as: **Me**
   - Who has access: **Anyone with the link** (required so the daily run can call it; the shared secret in the script rejects anyone else)
5. Click **Deploy**, authorize when Google asks (it warns because the script is your own — Advanced → Go to project), and copy the **Web app URL** (ends in `/exec`).
6. Paste that URL as `endpoint` in `sheet-config.json` in this repo (kept out of git).

## Verify

```bash
python3 scripts/sheet.py list
```

Expected: `{"jobs": [], "open": 0, "total": 0}`.

## Notes

- Tabs named after countries (`sweden`, `denmark`, …) are created automatically on first append, with headers `Post URL | Company | Match (%) | Status | Title | Added`, a frozen header row, and a dropdown on **Status** (`open`, `applied`, `in-progress`, `denied`).
- Rows are kept sorted by **Match (%)** descending after every append.
- If you ever edit `Code.gs`, redeploy: **Deploy → Manage deployments → ✏️ → Version: New version → Deploy** (the URL stays the same).
- To revoke access, delete the deployment; to rotate the secret, change `SECRET` in the script (redeploy) and mirror it in `sheet-config.json`.
