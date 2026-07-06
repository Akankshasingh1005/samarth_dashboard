@echo off
echo ============================================
echo   Samarth ESP32 Driver Installer
echo ============================================
echo.
echo Installing CP210x USB to UART Bridge driver...
echo.

:: Check for admin privileges
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: This script must be run as Administrator!
    echo.
    echo Right-click this file and select "Run as administrator"
    echo.
    pause
    exit /b 1
)

:: Install the driver
pnputil /add-driver "%~dp0silabser.inf" /install

if %errorlevel% equ 0 (
    echo.
    echo ✓ Driver installed successfully!
    echo.
    echo Now unplug your ESP32 and plug it back in.
    echo A COM port should appear in Device Manager.
) else (
    echo.
    echo ERROR: Driver installation failed.
    echo Try downloading manually from:
    echo https://www.silabs.com/developer-tools/usb-to-uart-bridge-vcp-drivers
)

echo.
pause
