"""
Build script for CoupGame.
Compiles the game with PyInstaller and packages it for release.

Usage:
    python build_game.py

Environment variables (set by GitHub Actions):
    RELEASE_VERSION  — git tag, e.g. "v1.2.3"  (defaults to "v0.0.0-dev")
    TARGET_ARCH      — macOS only: "arm64" or "x86_64"  (defaults to host arch)
"""

import os
import platform
import shutil
import tarfile
import zipfile

import PyInstaller.__main__

# ── Config ────────────────────────────────────────────────────────────────────
APP_NAME = "CoupGame"
SPEC_FILE = "CoupGame.spec"
VERSION = os.environ.get("RELEASE_VERSION", "v0.0.0-dev")
OUTPUT_DIR = "build_output"
# ─────────────────────────────────────────────────────────────────────────────


def clean():
    for folder in ("dist", "build", OUTPUT_DIR):
        if os.path.exists(folder):
            shutil.rmtree(folder)
            print(f"Removed: {folder}/")


def compile_game():
    print(f"Building {APP_NAME} {VERSION}…")
    PyInstaller.__main__.run(["--clean", SPEC_FILE])
    print("PyInstaller finished.")


def write_version_file():
    version_path = os.path.join("dist", APP_NAME, "version.txt")
    with open(version_path, "w") as f:
        f.write(VERSION)
    print(f"Version file written: {version_path}")


def package():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    dist_folder = os.path.join("dist", APP_NAME)
    system = platform.system()

    if system == "Windows":
        archive_name = f"{APP_NAME}-Windows-{VERSION}.zip"
        archive_path = os.path.join(OUTPUT_DIR, archive_name)
        print(f"Creating ZIP: {archive_name}")
        with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, _dirs, files in os.walk(dist_folder):
                for file in files:
                    full_path = os.path.join(root, file)
                    arcname = os.path.relpath(full_path, start="dist")
                    zf.write(full_path, arcname)

    elif system in ("Linux", "Darwin"):
        if system == "Darwin":
            platform_name = f"macOS-{platform.machine()}"
        else:
            platform_name = "Linux"

        archive_name = f"{APP_NAME}-{platform_name}-{VERSION}.tar.gz"
        archive_path = os.path.join(OUTPUT_DIR, archive_name)
        print(f"Creating TAR.GZ: {archive_name}")
        with tarfile.open(archive_path, "w:gz") as tf:
            tf.add(dist_folder, arcname=APP_NAME)

    else:
        raise RuntimeError(f"Unsupported platform: {system}")

    print(f"Release package ready: {archive_path}")


if __name__ == "__main__":
    clean()
    compile_game()
    write_version_file()
    package()
