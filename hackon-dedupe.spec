# -*- mode: python ; coding: utf-8 -*-
# PyInstaller build for HackOn Photo & Video DeDupe.
#   pip install pyinstaller
#   pyinstaller hackon-dedupe.spec
# Output: dist/HackOn/HackOn.exe  (a onedir build you can zip and move anywhere)

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('templates', 'templates'),   # Flask HTML templates (read-only, bundled)
        ('assets', 'assets'),         # logos / favicon served at /assets
        ('docs', 'docs'),             # HELP.md / INSTALL.md for the in-app Help page
        ('THIRD-PARTY-NOTICES.md', '.'),  # third-party licence notices
    ],
    hiddenimports=[
        'keyring.backends.Windows',   # where API keys / Plex token are stored on Windows
        'keyring.backends.chainer',
        'keyring.backends.fail',
        'pillow_heif',                # .HEIC/.HEIF photo support
        'waitress',                   # production WSGI server (app mode)
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='HackOn',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,   # keep the console for test builds so you can see the server log + any errors
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icon.ico',   # embedded in HackOn.exe (shortcuts inherit it)
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='HackOn',
)
