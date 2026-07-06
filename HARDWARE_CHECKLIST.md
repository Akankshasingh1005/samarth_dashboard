# SAMARTH Exoskeleton: PS3 Hardware Verification and Troubleshooting Guide

This guide to verify if the PS3 Exoskeleton Hardware (ESP32) is working correctly with PS1 and PS2.

---

## How the System Works (The Feedback Loop)

```
 [ PS1: Camera ] --► Detects joint positions in real-time
        │
        ▼
 [ PS2: AI Engine ] --► Analyzes movement, counts reps, and computes assistance/resistance
        │
        ▼ (Target Torque and Mode commands sent via WiFi)
 [ PS3: ESP32 Exoskeleton ] --► Actuates Knee motor based on AI recommendations
        │
        ▼ (ESP32 sends back actual angles, foot pressure, and motor PWM status)
 [ Samarth Dashboard ] --► Displays live values on the screen and saves them
```

---

## Step 1: Pre-Testing Setup (WiFi and Configuration)

Before testing, we need to make sure the ESP32 and your computer running the dashboard can talk to each other.

1. Connect to the same WiFi network:
   * Make sure your ESP32 hardware and the computer running the Samarth server are connected to the same local Wi-Fi / Router.
2. Find the ESP32's IP Address:
   * Power on the ESP32 and look at the Serial Monitor (in Arduino IDE) to find its IP address (e.g., 192.168.1.105 or 192.168.43.50).
3. Configure the Dashboard Settings:
   * Open the .env file in the backend/ directory of the project.
   * Look for the PS3 Sensor Hub section.
   * Change settings to:
     ```env
     PS3_USE_REAL_SENSOR=true
     PS3_ESP_URL=http://<ESP32_IP_ADDRESS>   # Example: http://192.168.1.105
     ```
   * Save the .env file and restart your backend server.

---

## Step 2: Basic Connectivity Verification

Let's test if the backend server can talk to the ESP32.

1. Start the backend server (using python -m uvicorn main:app or your run script).
2. Watch the server terminal logs.
   * If connection is successful, you will see:
     `[PS3] Connected to ESP32 exoskeleton at http://<ESP32_IP_ADDRESS>`
   * If it fails, it will output:
     `[PS3] Auto-connect failed: [Error details]. Falling back to mock.`
3. API Check (Optional - for developers):
   * Open your browser and go to: http://localhost:8000/api/v1/sensor/status
   * It should return a JSON response with "connected": true and "ps3_mode": "real".

---

## Step 3: Testing the Live Session Panel

Now let's check if the frontend displays the live sensor data from the exoskeleton.

1. Open the dashboard.
2. Select a exercise and start session.
3. Look at the Sensor Hub Panel on the right side of the screen:
   * Indicator: It should show a green badge: Connected.
   * Battery Gauge: It should display the current battery status (e.g., Battery 85%).
   * Live Angle Displays: Move the exoskeleton knee joints. The Knee Angle values on the screen should change in real-time.

---

## Step 4: Testing the PS2 to PS3 Feedback Loop

1. Perform one full repetition of the exercise (e.g., a squat) in front of the camera.
2. Once the rep is completed:
   * PS1 and PS2 will detect the repetition and evaluate its form.
   * PS2 will output an assistance/resistance command based on your performance (e.g., if you struggle, it will request Assistive mode; if you perform well, it will request Resistive Torque).
3. Verify Motor Reaction:
   * Watch the exoskeleton motors. They should turn on or change resistance.
   * Check the Sensor Hub Panel on the dashboard:
     * Motor Status should show ON.
     * Target Torque should change to the Nm value calculated by the AI.
     * Knee PWM / Hip PWM should show the updated control signals (0 to 255) sent to the motors.

---

## Step 5: Check Session Summary

1. Click End Session to save your work.
2. Check the Session Summary Page:
   * It should display a new card: PS3 Exoskeleton Sensor Summary.
   * It must show:
     * Average acceleration and peak force/angles.
     * Total motor commands sent during the session.
     * The last motor mode applied.
     * Graphs plotting the knee and hip angles measured by the sensors.

---

## Troubleshooting Guide (How to fix common issues)

### Problem 1: Dashboard shows PS3 - Disconnected
* Check Wi-Fi: Ensure your computer and the ESP32 are connected to the exact same Wi-Fi router. (Note: Many college/corporate Wi-Fi networks block device-to-device communication. Try creating a mobile hotspot and connecting both to it instead).
* Verify IP Address: Check if the ESP32 IP address has changed. Update PS3_ESP_URL in .env with the new IP address and restart the backend.
* Test ESP32 Webpage: Open a browser tab on your computer and type: http://<ESP32_IP_ADDRESS>/data. If you see a blank page or error, the ESP32 server is not running or unreachable.

### Problem 2: Live angles or force values do not update (Frozen)
* Check ESP32 loop speed: The ESP32 code might be crash-looping or stalled. Press the physical RESET button on the ESP32 board.
* Check Sensor Health: Ensure the IMU sensors (MPU-6050) and force sensors are wired properly to the ESP32. If a sensor is disconnected or loose, the ESP32 might send 0.0 or freeze trying to read it.

### Problem 3: Motors are not turning on / commands fail
* Check Power Source: Exoskeleton motors draw high current. Make sure the external battery pack or DC power supply is connected to the motor drivers and turned on (ESP32 USB power alone cannot run the motors).
* Confirm Command Protocol: Check the backend console logs. If you see HTTP error codes (like 404 or 500) when sending a command, the ESP32 firmware might have a different route or format for commands (e.g. /cmd instead of /command).

### Problem 4: Angles on screen don't match actual leg movement
* Recalibrate: Click the Calibrate button in the dashboard panel. Keep the exoskeleton still and straight for 3-5 seconds while it performs home-position zeroing.
* Axis Check: Verify that the IMU sensors on the thigh and shank are mounted in the correct direction (e.g., Y-axis pointing down the leg). If mounted upside down, angles might show negative values or count backwards.
