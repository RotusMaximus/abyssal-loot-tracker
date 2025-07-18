@echo off
title Abyssal Loot Tracker

:: ============================================================================
::  This script is the single entry point for the Abyssal Loot Tracker.
::  It checks if setup is complete, runs it if needed, and then starts the app.
:: ============================================================================

:: --- Define the marker file that indicates setup is complete ---
:: We place it in the data folder to keep the root directory clean.
set "MARKER_FILE=data\.setup_complete"

:: --- Check if the marker file exists ---
if exist "%MARKER_FILE%" (
    :: If the marker exists, setup is done. Skip to the run section.
    goto :run_application
)

:: ############################################################################
:: #                        ONE-TIME SETUP LOGIC                              #
:: ############################################################################
echo.
echo Welcome to the Abyssal Loot Tracker!
echo Performing first-time setup...
echo.

:: --- Step 1: Check for Python ---
echo ==========================================================
echo  Step 1: Checking for Python...
echo ==========================================================
echo.
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Python not found in your system's PATH.
    echo.
    echo Please download and install Python from https://www.python.org/downloads/
    echo IMPORTANT: During installation, you MUST check the box "Add python.exe to PATH".
    echo.
    echo Please run this script again after installing Python.
    echo.
    pause
    exit /b
)

echo [OK] Python was found!
echo.
echo.

:: --- Step 2: Install Dependencies ---
echo ==========================================================
echo  Step 2: Installing application components...
echo ==========================================================
echo This may take a few moments. Please wait.
echo.

echo Installing 'uv'...
python -m pip install uv
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install 'uv'. Please check your internet connection and try again.
    pause
    exit /b
)
echo.
echo Installing the application and its dependencies...
uv sync
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install application dependencies.
    echo Please check your internet connection or any error messages above.
    pause
    exit /b
)

:: --- Step 3: Create the Marker File on Success ---
echo.
echo ==========================================================
echo  SETUP COMPLETE!
echo ==========================================================
echo.
:: Ensure the data directory exists before trying to create the file
if not exist "data" mkdir "data"
:: Create marker file
type nul > "%MARKER_FILE%"
echo.
pause

:: ############################################################################
:: #                         END OF SETUP LOGIC                               #
:: ############################################################################


:run_application
:: This is the target for the GOTO command.
:: The script jumps here if setup was already complete.
echo Starting Abyssal Loot Tracker...
uv run run.py