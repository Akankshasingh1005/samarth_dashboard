# 🧪 How to Test the ESP32 Communication

This guide explains how to test the full communication loop between your two ESP32 boards and the website. Follow the steps in order.

---

## 🛒 What You Need

- 2x ESP32 DEVKITV1 boards
- 2x USB cables (micro-USB or USB-C depending on your board)
- A laptop with Arduino IDE installed
- A phone (for WiFi setup — one time only)
- All devices on the **same WiFi network**

---

## 📦 Step 1: Install Libraries in Arduino IDE

Open Arduino IDE → Go to **Sketch → Include Library → Manage Libraries**

Search and install these 4 libraries:

| Search for | Author | Click Install |
|---|---|---|
| `WiFiManager` | tzapu | ✅ Install |
| `ArduinoJson` | Benoit Blanchon | ✅ Install (v7) |
| `MPU6050` | Electronic Cats | ✅ Install |
| `I2Cdev` | Jeff Rowberg | ✅ Install |

Also make sure you have the ESP32 board package:
- Go to **Tools → Board → Boards Manager**
- Search `esp32` → Install **"esp32 by Espressif Systems"** (latest version)
- Select board: **Tools → Board → esp32 → ESP32 Dev Module**

---

## 🌐 Step 2: Flash ESP B (Bridge Unit) — The one that connects to WiFi

1. Open `dashboard/esp_code/esp_to_website.cpp` in Arduino IDE
2. Plug in ESP B via USB
3. Select the correct **COM port** (Tools → Port)
4. Click **Upload** (→ button)
5. Open **Serial Monitor** (Tools → Serial Monitor, set baud to **115200**)

### What happens:

```
========== Samarth Bridge Unit ==========
Connecting to WiFi (or starting setup portal)...
```

6. **Pick up your phone** → Go to WiFi settings
7. You'll see a new WiFi network called **"Samarth-ESP32-Setup"** → Connect to it
8. A webpage opens automatically (if not, open browser and go to `192.168.4.1`)
9. Tap **"Configure WiFi"**
10. Select your WiFi network from the list
11. Enter your WiFi password → Tap **Save**

### Serial Monitor should now show:

```
✅ Connected to WiFi. IP: 192.168.X.X     ← WRITE THIS DOWN (you need it later)
WiFi channel: 6                            ← WRITE THIS DOWN
Bridge Unit ready. MAC: AA:BB:CC:DD:EE:FF  ← WRITE THIS DOWN
```

---

## 🌐 Understanding the WiFi Setup Portal (FAQ)

### 1. When and why does the WiFi portal open?
* **On first boot**: Because the ESP32 has no saved WiFi networks in its memory, it hosts the hotspot so you can configure it.
* **When WiFi changes**: If you rename your WiFi or change the password, the ESP32 won't be able to connect and will automatically open the portal again.
* **When the router is off**: If the ESP32 powers up and cannot detect your router, it starts the portal.

### 2. How does it work under the hood?
* It saves your WiFi name (SSID) and password inside its permanent memory (EEPROM).
* When powered on, it first tries to connect to the saved network.
* **If successful**: It connects quietly in 2 seconds and goes straight to running the server. **No portal is shown.**
* **If it fails**: It waits and opens the setup hotspot for 3 minutes before retrying.

### 3. Will the portal appear again when I'm testing or when the website is deployed?
* **During Local Testing**: No. As long as your router is on and your credentials haven't changed, the ESP32 will auto-connect instantly on power-up. You won't see the portal.
* **On Website Deployment**: No. The server code on the website connects to the ESP32's IP address. The ESP32 itself stays connected to your router.
* **When moving to a new location**: Yes! If you take the exoskeleton to a clinic, hospital, or another house, the ESP32 won't find your home WiFi. It will open the portal so you can connect it to the new clinic's WiFi network. Alternatively, you can force it to open by **holding the BOOT button** during power-up.

---

> ⚠️ **Write down these 3 things!** You need them for the next steps.

---

## 🦿 Step 3: Flash ESP A (Exo Unit) — The one connected to sensors/motors

1. Open `dashboard/esp_code/esp_to_esp.cpp` in Arduino IDE

2. **Edit line 34** — Replace the MAC with ESP B's MAC from Step 2:
   ```cpp
   uint8_t bridgeMAC[] = {0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0xFF};
   ```
   Example: If ESP B's MAC was `24:6F:28:1A:2B:3C`, write:
   ```cpp
   uint8_t bridgeMAC[] = {0x24, 0x6F, 0x28, 0x1A, 0x2B, 0x3C};
   ```

3. **Edit line 35** — Set the WiFi channel from Step 2:
   ```cpp
   #define WIFI_CHANNEL 6    // ← put the channel number from Step 2
   ```

4. Unplug ESP B, plug in ESP A
5. Select the correct COM port
6. Click **Upload**
7. Open Serial Monitor

### Serial Monitor should show:

```
Calibrating IMU gyros... keep sensors still
Exo Unit ready. MAC: XX:XX:XX:XX:XX:XX    ← WRITE THIS DOWN
```

---

## 🔗 Step 4: Connect the MACs (so they can find each other)

1. Go back to `esp_to_website.cpp`

2. **Edit line 41** — Replace with ESP A's MAC from Step 3:
   ```cpp
   uint8_t exoMAC[] = {0xXX, 0xXX, 0xXX, 0xXX, 0xXX, 0xXX};
   ```

3. Unplug ESP A, plug in ESP B
4. Flash ESP B again (Upload)

Now both ESPs know each other's MAC address and can communicate!

5. **Plug in ESP A** (with a separate USB cable or power source)

Both should now be running simultaneously.

---

## 🐍 Step 5: Run the Test Script (from your laptop)

This script verifies if the entire bidirectional path is working:
* **Forward Path**: Laptop/Website → ESP B (HTTP) → ESP A (ESP-NOW)
* **Return Path**: ESP A → ESP B (ESP-NOW) → Laptop/Website (HTTP Poll)

> 💡 **Built-in Emulator**: You can test this even if **ESP A** (Exo Unit) is powered off! **ESP B** has a built-in emulator that automatically generates smooth joint movements (sine waves) and foot forces when ESP A is offline. If you turn ESP A on, the emulator automatically shuts down and displays real sensor values instead.

Open a terminal/command prompt on your laptop and run:

```bash
cd dashboard\esp_code
$env:PYTHONIOENCODING="utf-8"
python test_esp_communication.py --ip 10.81.192.229
```

### 🔍 How to check if it's working properly:

#### 1. Verify ESP A ↔ ESP B (ESP-NOW Link)
Look at **Test 2: Read sensor data** in the script output:
* **Working**: You see changing angles and force values:
  `✅ Read telemetry — knee=45.2° hip=30.1° force=2.1N stance=no motors=off`
* **Not Working**: You see:
  `⚠️ Read telemetry (ESP A not connected yet)`
  *If you see this, check: Is ESP A powered on? Did you copy the MAC addresses correctly in Steps 3 & 4?*

#### 2. Verify Bidirectional Control Loop
Look at **Test 3: Send motor commands** and **Test 4: Loop test**:
* Open ESP A's Serial Monitor in a separate Arduino IDE window.
* When the script sends commands (e.g. `mode_id=1, torque=0.5`), verify that ESP A's Serial Monitor prints that it received the command and starts driving the motors.
* Verify that the updated motor PWM values are reflected in the test script output.

### ❌ Troubleshooting Errors:

| Symptom | Cause | Solution |
|---|---|---|
| `Cannot connect` | Laptop and ESP B are on different networks, or IP is wrong. | Check ESP B's Serial Monitor for the IP address. Make sure your laptop is on the same WiFi. |
| `ESP A not connected yet` | ESP A isn't sending data to ESP B. | Ensure both devices have matching MAC addresses configured, are powered on, and use the same WiFi channel (11). |
| `UnicodeEncodeError` | Console encoding issue. | Prepend your run command with `$env:PYTHONIOENCODING="utf-8"`. |

---

## 🌍 Step 6: Test with the Full Website (optional)

1. Open `dashboard/backend/.env` in a text editor

2. Update the ESP IP:
   ```
   PS3_ESP_URL=http://192.168.X.X
   ```
   (Replace with ESP B's IP from Step 2)

3. Start the backend server:
   ```bash
   cd dashboard\backend
   python -m uvicorn main:app --reload
   ```

4. Start the frontend:
   ```bash
   cd dashboard\frontend
   npm run dev
   ```

5. Open the website → Login → Start a live exercise session

6. You should see:
   - **Real sensor data** showing in the session panel
   - **Motor commands** appearing in ESP B's Serial Monitor
   - ESP A's Serial Monitor showing received mode changes

---

## 🔄 Changing WiFi Network Later

If you move to a different location or WiFi:

1. Power off ESP B
2. **Hold the BOOT button** (the small button near the USB port)
3. While holding, power on ESP B
4. Keep holding for 3 seconds, then release
5. Serial Monitor will say: `⚠️ BOOT button held — clearing saved WiFi credentials...`
6. Connect to **"Samarth-ESP32-Setup"** from your phone again
7. Pick the new WiFi → Enter password → Done

---

## 📋 Quick Reference

| Thing | Where to find it |
|---|---|
| ESP B's IP address | Serial Monitor after WiFi connects |
| ESP B's MAC address | Serial Monitor at startup |
| ESP A's MAC address | Serial Monitor at startup |
| WiFi channel | Serial Monitor after WiFi connects |
| Test script | `dashboard/esp_code/test_esp_communication.py` |
| Backend ESP config | `dashboard/backend/.env` → `PS3_ESP_URL` |
