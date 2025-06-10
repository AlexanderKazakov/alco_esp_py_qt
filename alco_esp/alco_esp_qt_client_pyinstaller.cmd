@ECHO OFF
REM --- Configuration ---
SET "SCRIPT_DIR=%~dp0"
REM Remove trailing backslash from SCRIPT_DIR if it exists
IF "%SCRIPT_DIR:~-1%"=="\" SET "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"

SET "PYTHON_SCRIPT=alco_esp_qt_client.py"
SET "APP_NAME=AlcoEspMonitor"
SET "BUILD_ROOT=build_output"
SET "VENV_DIR=%BUILD_ROOT%\venv"
SET "DIST_DIR=%BUILD_ROOT%\dist"
SET "WORK_DIR=%BUILD_ROOT%\build_pyinstaller"

REM --- This script is for a 32-bit Windows OS ---

ECHO --- Starting PyInstaller build for %PYTHON_SCRIPT% ---

REM Navigate to the script's directory
PUSHD "%SCRIPT_DIR%"
ECHO Changed directory to: %CD%

REM Create the main build directory if it doesn't exist
IF NOT EXIST "%BUILD_ROOT%" (
    ECHO Creating main build directory '%BUILD_ROOT%'...
    MKDIR "%BUILD_ROOT%"
)

REM 1. Create Virtual Environment
IF NOT EXIST "%VENV_DIR%\Scripts\activate.bat" (
    ECHO Creating virtual environment in '%VENV_DIR%'...
    py -3.11 -m venv "%VENV_DIR%"
    IF ERRORLEVEL 1 (
        ECHO Failed to create virtual environment. Exiting.
        GOTO :EOF
    )
) ELSE (
    ECHO Virtual environment '%VENV_DIR%' already exists.
)

REM 2. Activate Virtual Environment
ECHO Activating virtual environment...
CALL "%VENV_DIR%\Scripts\activate.bat"
IF ERRORLEVEL 1 (
    ECHO Failed to activate virtual environment. Exiting.
    GOTO :EOF
)

REM 3. Install Dependencies
ECHO Installing required packages...
python -m pip install --upgrade pip
IF ERRORLEVEL 1 (
    ECHO Failed to upgrade pip. Exiting.
    GOTO :EOF
)
pip install -r ..\requirements_windows_32bit.txt --only-binary :all:
IF ERRORLEVEL 1 (
    ECHO Failed to install requirements. Exiting.
    GOTO :EOF
)

ECHO Packages installed.

REM 4. Run PyInstaller
ECHO Running PyInstaller...
pyinstaller ^
    --noconfirm ^
    --name "%APP_NAME%" ^
    --noconsole ^
    --add-data "%SCRIPT_DIR%\alarm.wav;." ^
    --add-data "%SCRIPT_DIR%\secrets_template.json;." ^
    --distpath "%DIST_DIR%" ^
    --workpath "%WORK_DIR%" ^
    --specpath "%BUILD_ROOT%" ^
    "%PYTHON_SCRIPT%"

IF ERRORLEVEL 1 (
    ECHO PyInstaller failed. Exiting.
    CALL :DEACTIVATE_VENV
    GOTO :EOF
)

ECHO PyInstaller finished.

REM 5. Deactivate Virtual Environment (optional but good practice)
:DEACTIVATE_VENV
ECHO Deactivating virtual environment...
CALL deactivate
IF EXIST "%VENV_DIR%\Scripts\deactivate.bat" (
    CALL "%VENV_DIR%\Scripts\deactivate.bat"
) ELSE (
    ECHO Deactivate script not found or already deactivated.
)


REM 6. Clean up build directory (optional)
REM ECHO Cleaning up temporary build directory '%WORK_DIR%'...
REM IF EXIST "%WORK_DIR%" RMDIR /S /Q "%WORK_DIR%"
REM Consider cleaning the entire BUILD_ROOT if desired:
REM ECHO Cleaning up build output directory '%BUILD_ROOT%'...
REM IF EXIST "%BUILD_ROOT%" RMDIR /S /Q "%BUILD_ROOT%"

ECHO --- Build process completed ---
ECHO The application bundle is located in: %SCRIPT_DIR%\%DIST_DIR%\%APP_NAME%
ECHO You can run the application by executing the file inside that directory (e.g., %DIST_DIR%\%APP_NAME%\%APP_NAME%.exe on Windows).

POPD
ENDLOCAL
EXIT /B 0
