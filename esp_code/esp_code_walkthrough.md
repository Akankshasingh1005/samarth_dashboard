# 📂 Walkthrough of the `esp_code` Folder

This document provides a guide to the structure, purpose, and contents of every file and folder inside the `esp_code` directory.

---

## 🗺️ Folder Structure Map

```
esp_code/
├── esp_to_esp/                       # [FOLDER] ESP A (Exo Unit) Arduino Sketch
│   └── esp_to_esp.ino                # Code for reading sensors & driving motors
├── esp_to_website/                   # [FOLDER] ESP B (Bridge Unit) Arduino Sketch
│   └── esp_to_website.ino            # Code for HTTP server & WiFiManager portal
├── esp_to_esp.cpp                    # Raw C++ copy of ESP A code (for reference)
├── esp_to_website.cpp                # Raw C++ copy of ESP B code (for reference)
├── test_esp_communication.py         # Python script to test connection & feedback loop
├── TESTING_GUIDE.md                  # Comprehensive step-by-step guide to run & test
├── install_driver.bat                # One-click installer script for the CP2102 driver
├── silabser.inf                      # Driver configuration file (needed by installer)
├── silabser.cat                      # Driver catalog file (needed by installer)
└── [arm/ arm64/ x64/ x86/]           # [FOLDERS] Driver binary files for different systems
```

---

## 📄 File-by-File Details

### 1. `esp_to_esp/esp_to_esp.ino` (ESP A - Exo Unit)
* **What it does**: This is the firmware for the **first ESP32 (Exo Unit)** which is attached to the physical exoskeleton.
* **Key Features**:
  * **Sensors**: Reads knee/hip angles from MPU6050 IMUs via I2C and reads foot contact/pressure from a foot Force Sensitive Resistor (FSR).
  * **Actuators**: Drives the knee and hip motors using RPWM/LPWM signals mapped from target torque.
  * **Radio link**: Connects to the Bridge Unit via **ESP-NOW** (direct radio).
  * **Telemetry**: Sends live angles, motor speed, and stance status to the Bridge Unit 100 times per second.

---

### 2. `esp_to_website/esp_to_website.ino` (ESP B - Bridge Unit)
* **What it does**: This is the firmware for the **second ESP32 (Bridge Unit)** which acts as the gateway between the Exo Unit and your laptop/website.
* **Key Features**:
  * **WiFiManager**: Auto-scans and connects to WiFi. If credentials are lost or missing, it starts a local hotspot called `"Samarth-ESP32-Setup"` so you can enter credentials from your phone.
  * **ESP-NOW receiver**: Listens for incoming sensor telemetry packets from the Exo Unit (ESP A).
  * **HTTP Server**: Runs a lightweight web server on port 80 that hosts the endpoints for the FastAPI backend:
    * `GET /status` — Device configuration, battery level, and uptime.
    * `GET /data` — Latest joint angles, foot force, and motor status.
    * `POST /command` — Receives mode (Assistive/Resistive) and target torque from the backend and relays them to ESP A.

---

### 3. `test_esp_communication.py` (Python test script)
* **What it does**: A command-line script run from your laptop to verify the entire connection path without starting the full website or backend.
* **Key Tests**:
  * **Test 1: Ping**: Verifies that the Bridge Unit (ESP B) is alive and accessible on the local network.
  * **Test 2: Telemetry Check**: Polls joint sensor data to confirm ESP B is successfully receiving radio signals from ESP A.
  * **Test 3 & 4: Control commands**: Sends simulated mode commands to check that the motor control path is functioning.
  * **Test 5: Loop**: Performs a continuous 10-second read/write stress test at 10Hz to measure latency and stability.

---

### 4. `TESTING_GUIDE.md` (Testing Instruction Manual)
* **What it does**: A clear, beginner-friendly manual detailing library installation, board configuration, captive portal setup, and running the Python verification script.

---

### 5. `install_driver.bat` and associated CP2102 files
* **What it does**: A Windows batch utility that installs the Silicon Labs USB-to-Serial driver with administrative privileges.
* **Why it's needed**: Ensures your computer recognizes the USB connection to the ESP32 and assigns a valid `COM` port (like `COM6`) for code uploads.
