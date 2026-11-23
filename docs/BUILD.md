# Building the Windows client

The app normally runs with `python app.py`. To hand someone a double-clickable
app, build it with **PyInstaller**.

Packaged builds keep read-only files (templates, assets, docs) inside the bundle,
and write user data (settings, results, logs, the downloaded ffprobe) to
`%APPDATA%\HackOn` — so the app works even when installed in a read-only location.
Running from source is unchanged: your data stays in the project folder.

## Build (Windows)

In the project folder, with the venv active:

```
pip install pyinstaller
pyinstaller hackon-dedupe.spec
```

Output: **`dist\HackOn\HackOn.exe`**. Double-click it — it starts the local server
and opens your browser at http://127.0.0.1:5000, just like `python app.py`.

To share it for testing, zip the whole **`dist\HackOn\`** folder (the exe needs the
files next to it).

## Notes
- First launch creates `%APPDATA%\HackOn\` for settings, results, logs and the
  ffprobe download, so each tester starts with a clean setup (your dev data is
  untouched).
- The build keeps a console window so you can watch the server log and any errors
  while testing. For a quieter release build, set `console=False` in
  `hackon-dedupe.spec`.
- No app icon yet: PyInstaller needs a `.ico` and the project only ships
  `assets/icon.svg`. Convert it, then set `icon='assets/icon.ico'` in the spec.
- If PyInstaller reports a missing module at runtime, add it to `hiddenimports`
  in the spec and rebuild. (scipy / numpy / Pillow / imagehash are handled by
  PyInstaller's built-in hooks.)
- This is a onedir test build. A signed Windows installer and the Mac `.app` are
  the next packaging steps on the plan.
