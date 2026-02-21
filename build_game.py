"""
Build script for CoupGame.

Creates a standalone executable using PyInstaller and packages it for distribution.
Mirrors the build system used by the CoupLauncher repository.

Usage:
    python build_game.py

Environment variables:
    RELEASE_VERSION  Version string injected by GitHub Actions (e.g. "v1.0.0").
                     Defaults to "v0.0.0-dev" when run locally.
    TARGET_ARCH      macOS only. PyInstaller --target-arch value ("arm64",
                     "x86_64", "universal2"). Omit for native build.
"""

import os
import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

APP_NAME = "CoupGame"
ENTRY_POINT = "coup_game.py"
BUILD_OUTPUT = Path("build_output")
PLATFORM = sys.platform          # "win32", "linux", "darwin"
VERSION = os.environ.get("RELEASE_VERSION", "v0.0.0-dev")
TARGET_ARCH = os.environ.get("TARGET_ARCH", "")


def build() -> None:
    print(f"Building {APP_NAME} {VERSION} for {PLATFORM}...")

    for d in ("dist", "build", "__pycache__"):
        if Path(d).exists():
            shutil.rmtree(d)
    BUILD_OUTPUT.mkdir(exist_ok=True)

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--windowed",
        "--name", APP_NAME,
        "--icon=coup.ico",
        "--clean",
        "--noconfirm",
        ENTRY_POINT,
    ]
    if TARGET_ARCH and PLATFORM == "darwin":
        cmd += ["--target-arch", TARGET_ARCH]

    subprocess.run(cmd, check=True)
    _package()
    print("Build complete.")


def _package() -> None:
    """Wrap the PyInstaller output in a platform archive inside build_output/."""
    if PLATFORM == "win32":
        exe = Path("dist") / f"{APP_NAME}.exe"
        out = BUILD_OUTPUT / f"{APP_NAME}-Windows-{VERSION}.zip"
        print(f"Packaging {out.name}...")
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(exe, exe.name)

    elif PLATFORM == "darwin":
        app_bundle = Path("dist") / f"{APP_NAME}.app"
        arch_tag = f"-{TARGET_ARCH}" if TARGET_ARCH else ""
        out = BUILD_OUTPUT / f"{APP_NAME}-macOS{arch_tag}-{VERSION}.tar.gz"
        print(f"Packaging {out.name}...")
        with tarfile.open(out, "w:gz") as tf:
            tf.add(app_bundle, arcname=app_bundle.name)

    else:  # Linux
        exe = Path("dist") / APP_NAME
        out = BUILD_OUTPUT / f"{APP_NAME}-Linux-{VERSION}.tar.gz"
        print(f"Packaging {out.name}...")
        with tarfile.open(out, "w:gz") as tf:
            tf.add(exe, arcname=exe.name)

    print(f"Archive ready: {out}")


if __name__ == "__main__":
    build()
