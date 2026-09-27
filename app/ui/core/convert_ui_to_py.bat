@echo off
setlocal enabledelayedexpansion


:: Define relative paths
set "UI_FILE=app\ui\core\MainWindow.ui"
set "PY_FILE=app\ui\core\main_window.py"
set "QRC_FILE=app\ui\core\media.qrc"
set "RCC_PY_FILE=app\ui\core\media_rc.py"

:: Incremental check: skip generation when UI/resources unchanged (faster startup)
:: If python is unavailable, errorlevel is non-zero -> fall back to always rebuilding
python "%~dp0ui_build_check.py"
if not errorlevel 1 (
    endlocal
    exit /b 0
)

:: Run PySide6 commands
pyside6-uic "%UI_FILE%" -o "%PY_FILE%"
pyside6-rcc "%QRC_FILE%" -o "%RCC_PY_FILE%"

:: Record signature of this build
python "%~dp0ui_build_check.py" --stamp

:: Define search and replace strings
set "searchString=import media_rc"
set "replaceString=from app.ui.core import media_rc"

:: Create a temporary file
set "tempFile=%PY_FILE%.tmp"

:: Process the file
(for /f "usebackq delims=" %%A in ("%PY_FILE%") do (
    set "line=%%A"
    if "!line!"=="%searchString%" (
        echo %replaceString%
    ) else (
        echo !line!
    )
)) > "%tempFile%"

:: Replace the original file with the temporary file
move /y "%tempFile%" "%PY_FILE%"

echo Replacement complete.