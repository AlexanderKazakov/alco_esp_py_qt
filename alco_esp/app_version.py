import os
import subprocess
import sys

from alco_esp.constants import APP_ROOT_DIR

# A PyInstaller build has no git checkout. The build scripts write the git commit to this file.
BUILD_VERSION_FILE_PATH = os.path.join(APP_ROOT_DIR, "build_version.txt")

UNKNOWN_APP_VERSION = "unknown"


def get_app_version():
    """
    Returns the git commit of the running code, for example "c29a21a" or "c29a21a-dirty".
    "-dirty" means that the code had uncommitted changes.
    Returns "unknown" if the version cannot be found.
    """
    try:
        with open(BUILD_VERSION_FILE_PATH, encoding="utf-8") as version_file:
            build_version = version_file.read().strip()
        if build_version:
            return build_version
    except OSError:
        pass

    # Do not start git from a build. On Windows it can open a console window.
    if getattr(sys, "frozen", False):
        return UNKNOWN_APP_VERSION

    try:
        result = subprocess.run(
            ["git", "describe", "--always", "--dirty"],
            cwd=APP_ROOT_DIR,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return UNKNOWN_APP_VERSION
    git_version = result.stdout.strip()
    if result.returncode != 0 or not git_version:
        return UNKNOWN_APP_VERSION
    return git_version
