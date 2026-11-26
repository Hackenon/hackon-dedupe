"""Build the HackOn desktop client with PyInstaller, and optionally a Windows
installer with Inno Setup. Dev tool.

Wraps the steps in docs/BUILD.md so one command produces a shareable build:

    python tools/build_exe.py              # build dist/HackOn/ (HackOn.exe + _internal\)
    python tools/build_exe.py --clean      # wipe build/ + dist/ first, then build
    python tools/build_exe.py --release    # build, then zip + SHA-256 (portable onedir)
    python tools/build_exe.py --installer  # build, then compile HackOn-Setup.exe (Inno Setup)
    python tools/build_exe.py --installer --version 1.2.0   # set the installer version
    python tools/build_exe.py --no-install # don't auto-install PyInstaller if missing

Run it on the OS you want the build for: a Windows .exe/installer only comes from
Windows. The installer needs Inno Setup 7 (ISCC.exe) on PATH or in its default
location -- https://jrsoftware.org/isdl.php. It builds from hackon-dedupe.spec and
installer/hackon.iss, so those stay the single source of truth.
"""

import argparse
import hashlib
import importlib.util
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "hackon-dedupe.spec"
ISS = ROOT / "installer" / "hackon.iss"
DIST = ROOT / "dist" / "HackOn"
ZIP_NAME = "HackOn-Setup.zip"
INSTALLER_EXE = ROOT / "HackOn-Setup.exe"
VERSION_FILE = ROOT / "VERSION"


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_version():
    """Single source of truth for the app/installer version: the VERSION file."""
    try:
        v = VERSION_FILE.read_text(encoding="utf-8").strip()
        return v or "1.0.0"
    except OSError:
        return "1.0.0"


def write_checksum(path):
    digest = sha256_file(path)
    name = Path(path).name
    (ROOT / "SHA256SUMS.txt").write_text(f"{digest}  {name}\n", encoding="utf-8")
    print(f"SHA-256: {digest}")
    print("Wrote SHA256SUMS.txt")


def ensure_pyinstaller(allow_install):
    if importlib.util.find_spec("PyInstaller") is not None:
        return
    if not allow_install:
        sys.exit("PyInstaller is not installed. Run `pip install pyinstaller`, or drop --no-install.")
    print("PyInstaller not found; installing it...")
    subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)


def run_build(clean):
    if not SPEC.is_file():
        sys.exit(f"Spec not found: {SPEC}")
    cmd = [sys.executable, "-m", "PyInstaller", SPEC.name, "--noconfirm"]
    if clean:
        cmd.append("--clean")
    print("Running:", " ".join(cmd))
    subprocess.run(cmd, cwd=str(ROOT), check=True)


def built_exe():
    """Return the built launcher path, whichever OS produced it."""
    for name in ("HackOn.exe", "HackOn"):
        p = DIST / name
        if p.exists():
            return p
    return None


def make_release():
    """Zip the CONTENTS of dist/HackOn so HackOn.exe + _internal/ sit at the zip
    root, then write SHA256SUMS.txt -- matches docs/BUILD.md's release steps."""
    if not DIST.is_dir():
        sys.exit(f"No build at {DIST}; build before --release.")
    zip_path = ROOT / ZIP_NAME
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(DIST.rglob("*")):
            if f.is_file():
                z.write(f, f.relative_to(DIST).as_posix())
    print(f"Wrote {zip_path.name} ({zip_path.stat().st_size // (1024*1024)} MB)")
    write_checksum(zip_path)


def find_iscc():
    """Locate Inno Setup's command-line compiler (ISCC.exe), any major version.

    Inno Setup isn't on PATH by default and each major version installs into its
    own "Inno Setup N" folder, so glob both Program Files roots and prefer the
    newest (7 over 6)."""
    found = shutil.which("iscc") or shutil.which("ISCC")
    if found:
        return found
    bases, seen = [], set()
    for env in ("ProgramW6432", "ProgramFiles", "ProgramFiles(x86)"):
        val = os.environ.get(env)
        if val:
            bases.append(Path(val))
    bases += [Path(r"C:\Program Files"), Path(r"C:\Program Files (x86)")]
    candidates = []
    for base in bases:
        if str(base) in seen:
            continue
        seen.add(str(base))
        try:
            candidates += base.glob("Inno Setup */ISCC.exe")
        except OSError:
            pass

    def version(path):
        try:
            return float(path.parent.name.split()[-1])   # "Inno Setup 7" -> 7.0
        except ValueError:
            return 0.0

    candidates.sort(key=version, reverse=True)
    return str(candidates[0]) if candidates else None


def make_installer(version):
    """Compile installer/hackon.iss into HackOn-Setup.exe with Inno Setup."""
    if not DIST.is_dir():
        sys.exit(f"No build at {DIST}; build before --installer.")
    if not ISS.is_file():
        sys.exit(f"Inno Setup script not found: {ISS}")
    iscc = find_iscc()
    if not iscc:
        sys.exit("Inno Setup (ISCC.exe) not found. Install Inno Setup 7 from\n"
                 "  https://jrsoftware.org/isdl.php\n"
                 "then re-run, or compile installer/hackon.iss in the Inno Setup IDE.")
    cmd = [iscc, f"/DMyAppVersion={version}", str(ISS)]
    print("Running:", " ".join(cmd))
    subprocess.run(cmd, cwd=str(ROOT), check=True)
    if INSTALLER_EXE.exists():
        print(f"\nBuilt installer: {INSTALLER_EXE} "
              f"({INSTALLER_EXE.stat().st_size // (1024*1024)} MB)")
        write_checksum(INSTALLER_EXE)
    else:
        print("\nInno Setup finished but HackOn-Setup.exe was not found -- check the log above.")


def main():
    ap = argparse.ArgumentParser(description="Build the HackOn desktop client and optional installer.")
    ap.add_argument("--clean", action="store_true", help="wipe build/ and dist/ before building")
    ap.add_argument("--release", action="store_true", help="after building, zip + SHA-256 (portable onedir)")
    ap.add_argument("--installer", action="store_true", help="after building, compile HackOn-Setup.exe (Inno Setup)")
    ap.add_argument("--version", default=read_version(),
                    help="installer version (default: the VERSION file, else 1.0.0)")
    ap.add_argument("--no-install", action="store_true", help="do not auto-install PyInstaller if missing")
    args = ap.parse_args()

    if sys.platform != "win32":
        print(f"Note: on {sys.platform}, PyInstaller builds a {sys.platform} app, not a Windows .exe,\n"
              f"      and the Inno Setup installer only builds on Windows. Run this on Windows.")

    ensure_pyinstaller(allow_install=not args.no_install)

    if args.clean:
        for d in (ROOT / "build", ROOT / "dist"):
            if d.exists():
                print(f"Removing {d}")
                shutil.rmtree(d)

    run_build(clean=args.clean)

    exe = built_exe()
    if exe:
        print(f"\nBuilt: {exe}")
    else:
        print("\nBuild finished, but no HackOn launcher was found in dist/HackOn/ -- check the log above.")

    if args.release:
        make_release()
    if args.installer:
        make_installer(args.version)
    if not (args.release or args.installer):
        print("Share it by zipping dist/HackOn/, or re-run with --installer (setup.exe) or --release (zip).")


if __name__ == "__main__":
    main()
