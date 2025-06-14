#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

# --- Configuration ---
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )" # Get the directory of this script
PYTHON_SCRIPT="alco_esp/qt_client.py"
APP_NAME="AlcoEspMonitor"
BUILD_ROOT="build_output" # Single directory for all build artifacts
VENV_DIR="$BUILD_ROOT/venv" # Virtual environment inside BUILD_ROOT
DIST_DIR="$BUILD_ROOT/dist" # Output directory for the final build inside BUILD_ROOT
WORK_DIR="$BUILD_ROOT/build_pyinstaller" # Temporary build directory for PyInstaller inside BUILD_ROOT

# --- This script is for a modern 64-bit Linux OS. Run it from the root repository directory ---

echo "--- Starting PyInstaller build for $PYTHON_SCRIPT ---"

# Navigate to the script's directory
cd "$SCRIPT_DIR"
echo "Changed directory to: $(pwd)"

# Create the main build directory if it doesn't exist
if [ ! -d "$BUILD_ROOT" ]; then
    echo "Creating main build directory '$BUILD_ROOT'..."
    mkdir -p "$BUILD_ROOT"
fi

# 1. Create Virtual Environment
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment in '$VENV_DIR'..."
    python3.11 -m venv "$VENV_DIR"
else
    echo "Virtual environment '$VENV_DIR' already exists."
fi

# 2. Activate Virtual Environment
echo "Activating virtual environment..."
source "$VENV_DIR/bin/activate"

# 3. Install Dependencies
echo "Installing required packages..."
pip install --upgrade pip
pip install -r requirements_ubuntu_64bit.txt

echo "Packages installed."

# 4. Run PyInstaller
echo "Running PyInstaller..."
pyinstaller \
    --noconfirm \
    --name "$APP_NAME" \
    --noconsole \
    --add-data "$SCRIPT_DIR/alco_esp/alarm.wav:./alco_esp" \
    --add-data "$SCRIPT_DIR/alco_esp/secrets_template.json:./alco_esp" \
    --distpath "$DIST_DIR" \
    --workpath "$WORK_DIR" \
    --specpath "$BUILD_ROOT" \
    "$PYTHON_SCRIPT"

echo "PyInstaller finished."

# 5. Deactivate Virtual Environment (optional but good practice)
echo "Deactivating virtual environment..."
deactivate

# 6. Clean up build directory (optional)
# echo "Cleaning up temporary build directory '$WORK_DIR'..."
# rm -rf "$WORK_DIR"
# Consider cleaning the entire BUILD_ROOT if desired:
# echo "Cleaning up build output directory '$BUILD_ROOT'..."
# rm -rf "$BUILD_ROOT"

echo "--- Build process completed ---"
echo "The application bundle is located in: $SCRIPT_DIR/$DIST_DIR/$APP_NAME"
echo "You can run the application by executing the file inside that directory (e.g., ./$DIST_DIR/$APP_NAME/$APP_NAME on Linux)."

exit 0
