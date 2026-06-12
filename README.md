# Secure File Workspace

A complete Flask full-stack assessment project with account signup/login, private file upload/download, file deletion, dark/light mode, animated UI states, live dashboard search, and drag-and-drop uploads.

## Features

- User signup, login, logout, and password hashing
- SQLite persistence with per-user file ownership
- Multiple file upload with type validation
- Secure download using original filenames
- File deletion from database and disk
- Dark/light theme stored in the browser
- Live file search and selected-file previews
- Responsive dashboard with inline SVG icons
- Automated tests for auth, uploads, downloads, deletes, and user isolation

## Run

```bash
python app.py
```

Open `http://127.0.0.1:5000`.

## Test

```bash
python -m unittest discover -s tests -v
```

## Build Check

```bash
python -m compileall app.py tests
```

## Notes

Runtime data is stored in `instance/app.sqlite3` and uploaded files are stored in `uploads/`. Both are created automatically when the app starts.
