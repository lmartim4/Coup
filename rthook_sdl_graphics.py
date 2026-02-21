"""
PyInstaller runtime hook for SDL/OpenGL graphics configuration.

This hook runs before the application starts and configures the environment
to prefer system graphics libraries over any bundled libraries.
"""
import os
import sys
from pathlib import Path


def configure_graphics_environment():
    """
    Configure environment to use system graphics drivers instead of bundled libraries.
    This is critical for PyInstaller bundles that may be built in environments
    without proper graphics driver support (like manylinux containers).
    """
    if not sys.platform.startswith('linux'):
        return

    # Tell Mesa to search system paths for drivers first
    # This ensures we use the host system's graphics drivers
    system_dri_paths = [
        '/usr/lib/dri',
        '/usr/lib/x86_64-linux-gnu/dri',
        '/usr/lib64/dri',
        '/usr/lib/i386-linux-gnu/dri',
    ]

    # Build LIBGL_DRIVERS_PATH from existing system paths
    existing_paths = [p for p in system_dri_paths if Path(p).exists()]
    if existing_paths:
        os.environ['LIBGL_DRIVERS_PATH'] = ':'.join(existing_paths)

    # Prefer system Mesa libraries over any bundled libraries
    # These environment variables tell the dynamic linker to use system libs
    system_lib_paths = [
        '/usr/lib/x86_64-linux-gnu',
        '/usr/lib64',
        '/usr/lib',
        '/lib/x86_64-linux-gnu',
        '/lib64',
        '/lib',
    ]

    existing_lib_paths = [p for p in system_lib_paths if Path(p).exists()]
    if existing_lib_paths:
        # Prepend system paths to LD_LIBRARY_PATH so they take precedence over bundled libs
        current_ld_path = os.environ.get('LD_LIBRARY_PATH', '')

        # Filter out PyInstaller's _MEIPASS path to prevent bundled library conflicts
        # This is critical because Mesa drivers need system libraries, not bundled ones
        meipass = getattr(sys, '_MEIPASS', None)
        if meipass:
            # Remove PyInstaller's bundled library path from LD_LIBRARY_PATH
            filtered_paths = [
                p for p in current_ld_path.split(':')
                if p and not p.startswith(meipass)
            ]
            current_ld_path = ':'.join(filtered_paths)

        new_ld_path = ':'.join(existing_lib_paths)
        if current_ld_path:
            new_ld_path = f"{new_ld_path}:{current_ld_path}"
        os.environ['LD_LIBRARY_PATH'] = new_ld_path

    # Preload critical system libraries to prevent PyInstaller's bundled versions
    # from interfering with Mesa drivers. This is the key fix for driver loading issues.
    preload_libs = []

    # libstdc++: C++ standard library (required by Mesa drivers)
    libstdcpp_candidates = [
        '/usr/lib/x86_64-linux-gnu/libstdc++.so.6',
        '/usr/lib64/libstdc++.so.6',
        '/lib/x86_64-linux-gnu/libstdc++.so.6',
    ]
    for lib in libstdcpp_candidates:
        if Path(lib).exists():
            preload_libs.append(lib)
            break

    # libgcc_s: GCC runtime library (often needed with libstdc++)
    libgcc_candidates = [
        '/lib/x86_64-linux-gnu/libgcc_s.so.1',
        '/usr/lib64/libgcc_s.so.1',
        '/lib64/libgcc_s.so.1',
    ]
    for lib in libgcc_candidates:
        if Path(lib).exists():
            preload_libs.append(lib)
            break

    if preload_libs:
        current_preload = os.environ.get('LD_PRELOAD', '')
        new_preload = ':'.join(preload_libs)
        if current_preload:
            new_preload = f"{new_preload}:{current_preload}"
        os.environ['LD_PRELOAD'] = new_preload

    # SDL configuration for better compatibility
    if 'SDL_VIDEODRIVER' not in os.environ:
        os.environ['SDL_VIDEODRIVER'] = 'x11'

    # Disable SDL's audio if not needed (reduces dependency issues)
    # Comment this out if your game needs audio
    # os.environ['SDL_AUDIODRIVER'] = 'dummy'


# Execute configuration when the hook is loaded
configure_graphics_environment()
