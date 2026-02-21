"""
Build script for CoupGame.

Creates a standalone executable using PyInstaller and packages it for distribution.

Usage:
    python build_game.py

Environment variables:
    RELEASE_VERSION  Version string injected by GitHub Actions (e.g. "v1.0.0").
                     Defaults to "v0.0.0-dev" when run locally.
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


def build() -> None:
    print(f"Building {APP_NAME} {VERSION} for {PLATFORM}...")

    for d in ("dist", "build", "__pycache__"):
        if Path(d).exists():
            shutil.rmtree(d)
    BUILD_OUTPUT.mkdir(exist_ok=True)

    if PLATFORM == "darwin":
        # --onedir produces a proper .app bundle on macOS.
        # --onefile + --windowed is deprecated (v7.0 will make it an error).
        # Pillow must be installed so PyInstaller can convert coup.ico → .icns.
        cmd = [
            sys.executable, "-m", "PyInstaller",
            "--onedir",
            "--windowed",
            "--name", APP_NAME,
            "--icon=coup.ico",
            "--clean",
            "--noconfirm",
            ENTRY_POINT,
        ]
    elif PLATFORM == "win32":
        # Windows: single-file executable with windowed mode
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
    else:
        # Linux: single-file executable, console mode to avoid OpenGL driver issues
        # Runtime hook configures environment to use system graphics libraries
        cmd = [
            sys.executable, "-m", "PyInstaller",
            "--onefile",
            "--name", APP_NAME,
            "--icon=coup.ico",
            "--clean",
            "--noconfirm",
            # Runtime hook to configure graphics environment before app starts
            "--runtime-hook", "rthook_sdl_graphics.py",
            # Exclude OpenGL/Mesa libraries - use system drivers instead
            "--exclude-module", "OpenGL",
            "--exclude-module", "OpenGL_accelerate",
            # Don't bundle libGL, Mesa will be loaded from system
            ENTRY_POINT,
        ]

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
        out = BUILD_OUTPUT / f"{APP_NAME}-macOS-arm64-{VERSION}.tar.gz"
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
