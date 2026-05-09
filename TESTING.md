# Testing Guide

## Install dependencies

Install runtime dependencies only:

- Linux:
  - `./.venv/bin/pip install -r requirements_ubuntu_64bit.txt`
- Windows (PowerShell):
  - `.\.venv\Scripts\pip install -r requirements_windows_32bit.txt`

Install test/development overlay dependencies:

- Linux:
  - `./.venv/bin/pip install -r requirements_dev_test.txt`
- Windows (PowerShell):
  - `.\.venv\Scripts\pip install -r requirements_dev_test.txt`

## Run tests

- Linux/macOS shell:
  - `QT_QPA_PLATFORM=offscreen MPLCONFIGDIR=$PWD/.mplconfig ./.venv/bin/python -m pytest -q`
- Windows PowerShell:
  - `$env:QT_QPA_PLATFORM='offscreen'; $env:MPLCONFIGDIR=(Resolve-Path '.\\.mplconfig'); .\\.venv\\Scripts\\python -m pytest -q`

Default run behavior:

- All tests run by default, including integration tests.

Run only integration tests:

- Linux/macOS shell:
  - `QT_QPA_PLATFORM=offscreen MPLCONFIGDIR=$PWD/.mplconfig ./.venv/bin/python -m pytest -q -m integration`
- Windows PowerShell:
  - `$env:QT_QPA_PLATFORM='offscreen'; $env:MPLCONFIGDIR=(Resolve-Path '.\\.mplconfig'); .\\.venv\\Scripts\\python -m pytest -q -m integration`

Run all non-integration tests explicitly:

- Linux/macOS shell:
  - `QT_QPA_PLATFORM=offscreen MPLCONFIGDIR=$PWD/.mplconfig ./.venv/bin/python -m pytest -q -m "not integration"`
- Windows PowerShell:
  - `$env:QT_QPA_PLATFORM='offscreen'; $env:MPLCONFIGDIR=(Resolve-Path '.\\.mplconfig'); .\\.venv\\Scripts\\python -m pytest -q -m "not integration"`
