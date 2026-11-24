# Connect Google Drive

Google Drive holds the documents the intake drafts from. `scripts/from_gdrive.py` lists them in the `docs` source (document, kind, updated_at, location).

Connector: Google Drive has a Claude connector in the directory (`drivemcp.googleapis.com`), with search and read. Status: tested on fixtures shaped like the documented Drive API v3 `files.list` response; not yet run on a live drive.

## List the documents

`files.list` with `fields=nextPageToken,files(id,name,mimeType,modifiedTime,webViewLink)` (without `fields`, Drive returns only id, name and type), every page, saved as it stands.

```bash
python3 scripts/from_gdrive.py --files run/drive/files-*.json --kind "risk register" --drive "Acme shared drive" --run run
```

Folders and trashed files are left out. `--kind` is the user's word for what the files are.

## Quote them in proposals

Export or download each document as text or Markdown first, and quote that file word for word in `intake.py propose`. The script checks every quote against the local file. A spreadsheet such as a risk register can go straight to `intake.py import --risks` as CSV, with its named columns.
