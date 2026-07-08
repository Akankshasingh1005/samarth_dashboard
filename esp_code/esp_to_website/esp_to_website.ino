/*
  ===========================================================================
  BRIDGE UNIT (ESP32 #2) - Code for the WiFi/HTTP Router Gateway
  ===========================================================================
  
  What this device does:
  1. Automatically connects to your local WiFi using a captive portal manager.
     - If it can't find WiFi, it hosts its own access point hotspot named "Samarth-ESP32-Setup".
     - You connect your phone to it, pick your WiFi, enter your password, and it saves it forever.
     - Hold the BOOT button (GPIO 0) during power-on to clear settings and connect to a different WiFi.
  2. Receives raw sensor readings from ESP A (Exo Unit) via ESP-NOW radio.
  3. Hosts a local HTTP Web Server to communicate with the laptop/website.
     - Laptop polls `/data` to retrieve latest angles, motor speeds, and forces.
     - Laptop polls `/status` to verify hardware is online and get battery levels.
     - Laptop POSTs `/command` to set assistive modes and motor target forces.
  ===========================================================================
*/

#include <esp_now.h>
#include <WiFi.h>
#include <esp_wifi.h>
#include <WebServer.h>
#include <ArduinoJson.h>
#include <WiFiManager.h>

// ==================== CONFIGURATION (FILL THESE) ====================
// ⚠️ MAC Address of the Exo Unit (ESP32 #1). Put the value printed in ESP A's Serial Monitor here.
uint8_t exoMAC[] = {0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0xFF};

// Radio channel (configured automatically during WiFi connection)
#define WIFI_CHANNEL 6

// Pin definition for the BOOT button on the ESP32 (GPIO 0)
// Hold down this button while powering on to reset WiFi settings.
#define WIFI_RESET_PIN 0

// ==================== DATA PACKET STRUCTURES ====================
// 1. Outgoing command structure (Website -> Here -> Sent to Exo Unit)
typedef struct {
  int mode_id;
  float target_torque;
} exercise_cmd_t;

// 2. Incoming telemetry structure (Sent from Exo Unit -> Received Here)
typedef struct {
  float battery_percent;
  bool  calibration_status;
  float knee_angle;
  float hip_angle;
  float foot_force;
  bool  stance;
  int   knee_motor_pwm;
  bool  knee_motor_dir;
  int   hip_motor_pwm;
  bool  hip_motor_dir;
  bool  motors_active;
} telemetry_t;

telemetry_t latestTelemetry = {};
bool telemetryReceived = false; // True when we successfully receive the first packet from ESP A



// Create local Web Server on standard HTTP port 80
WebServer server(80);

// ==================== ESP-NOW RADIO CALLBACKS ====================
#if ESP_ARDUINO_VERSION >= ESP_ARDUINO_VERSION_VAL(3, 0, 0)
// This function triggers when a packet is successfully sent (not used, kept as standard)
void onDataSent(const wifi_tx_info_t *info, esp_now_send_status_t status) {}

// This function triggers automatically whenever we receive telemetry from ESP A (Exo Unit)
void onDataRecv(const esp_now_recv_info_t *info, const uint8_t *data, int len) {
#else
void onDataSent(const uint8_t *mac, esp_now_send_status_t status) {}
void onDataRecv(const uint8_t *mac, const uint8_t *data, int len) {
#endif
  // ESP A now sends JSON strings, parse them with ArduinoJson
  // Expected format: {"knee_angle":75.3,"hip_angle":45.1,"foot_force":3.42,
  //                   "stance":true,"knee_pwm":95,"knee_dir":"ext",
  //                   "hip_pwm":60,"hip_dir":"ext","motors":"on"}
  JsonDocument doc;
  DeserializationError err = deserializeJson(doc, (const char*)data, len);
  if (err) {
    Serial.print("ESP-NOW JSON parse error: ");
    Serial.println(err.c_str());
    return;
  }

  latestTelemetry.knee_angle      = doc["knee_angle"] | 0.0f;
  latestTelemetry.hip_angle       = doc["hip_angle"] | 0.0f;
  latestTelemetry.foot_force      = doc["foot_force"] | 0.0f;
  latestTelemetry.stance          = doc["stance"] | false;
  latestTelemetry.knee_motor_pwm  = doc["knee_pwm"] | 0;
  latestTelemetry.knee_motor_dir  = (strcmp(doc["knee_dir"] | "ext", "ext") == 0);
  latestTelemetry.hip_motor_pwm   = doc["hip_pwm"] | 0;
  latestTelemetry.hip_motor_dir   = (strcmp(doc["hip_dir"] | "ext", "ext") == 0);
  latestTelemetry.motors_active   = (strcmp(doc["motors"] | "off", "on") == 0);
  latestTelemetry.battery_percent = 100;  // Battery not sent in JSON, default to 100
  latestTelemetry.calibration_status = true;
  telemetryReceived = true;
}

// ==================== HELPER: Relay command to Exo Unit ====================
void relayCommandToExo(int mode_id, float target_torque) {
  exercise_cmd_t cmd;
  cmd.mode_id = mode_id;
  cmd.target_torque = target_torque;
  
  // Send over ESP-NOW radio to ESP A
  esp_now_send(exoMAC, (uint8_t*)&cmd, sizeof(cmd));

  Serial.print("Command relayed to Exo Unit: Mode=");
  Serial.print(mode_id);
  Serial.print(", Torque=");
  Serial.print(target_torque);
  Serial.println("Nm");
}

// ==================== HTTP WEB SERVER HANDLERS ====================

// 1. POST /exercise (Legacy route for backwards compatibility)
void handleExercise() {
  if (server.method() != HTTP_POST) {
    server.send(405, "application/json", "{\"error\":\"method not allowed\"}");
    return;
  }

  String body = server.arg("plain");
  JsonDocument doc;
  DeserializationError err = deserializeJson(doc, body);
  if (err) {
    server.send(400, "application/json", "{\"error\":\"invalid json\"}");
    return;
  }

  int mode_id = doc["mode_id"] | 0;
  float target_torque = doc["target_torque"] | 0.0f;

  relayCommandToExo(mode_id, target_torque);
  server.send(200, "application/json", "{\"status\":\"ok\"}");
}

// 2. GET /telemetry (Legacy route for raw telemetry boolean format)
void handleTelemetry() {
  JsonDocument doc;
  doc["battery_percent"]    = latestTelemetry.battery_percent;
  doc["calibration_status"] = latestTelemetry.calibration_status;
  doc["knee_angle"]         = latestTelemetry.knee_angle;
  doc["hip_angle"]          = latestTelemetry.hip_angle;
  doc["foot_force"]         = latestTelemetry.foot_force;
  doc["stance"]             = latestTelemetry.stance;
  doc["knee_motor_pwm"]     = latestTelemetry.knee_motor_pwm;
  doc["knee_motor_dir"]     = latestTelemetry.knee_motor_dir;
  doc["hip_motor_pwm"]      = latestTelemetry.hip_motor_pwm;
  doc["hip_motor_dir"]      = latestTelemetry.hip_motor_dir;
  doc["motors_active"]      = latestTelemetry.motors_active;
  doc["connected"]          = telemetryReceived;

  String out;
  serializeJson(doc, out);
  server.send(200, "application/json", out);
}

// 3. GET /data (The standard endpoint polled by the backend RealSensorHub)
void handleData() {
  JsonDocument doc;
  doc["knee_angle"]         = latestTelemetry.knee_angle;
  doc["hip_angle"]          = latestTelemetry.hip_angle;
  doc["foot_force"]         = latestTelemetry.foot_force;
  doc["stance"]             = latestTelemetry.stance;
  doc["knee_pwm"]           = latestTelemetry.knee_motor_pwm;
  // Convert directions from booleans to strings ("ext" = extension, "flex" = flexion)
  doc["knee_dir"]           = latestTelemetry.knee_motor_dir ? "ext" : "flex";
  doc["hip_pwm"]            = latestTelemetry.hip_motor_pwm;
  doc["hip_dir"]            = latestTelemetry.hip_motor_dir ? "ext" : "flex";
  // Convert motor states to "on"/"off" strings
  doc["motors"]             = latestTelemetry.motors_active ? "on" : "off";
  doc["battery_percent"]    = latestTelemetry.battery_percent;
  doc["calibration_status"] = latestTelemetry.calibration_status ? "calibrated" : "uncalibrated";
  doc["connected"]          = telemetryReceived;

  String out;
  serializeJson(doc, out);
  server.send(200, "application/json", out);
}

// 4. GET /status (Verifies the device is responsive and gets basic info)
void handleStatus() {
  JsonDocument doc;
  doc["device_id"]          = "ESP32-BRIDGE";
  doc["battery_percent"]    = latestTelemetry.battery_percent;
  doc["calibration_status"] = latestTelemetry.calibration_status ? "calibrated" : "uncalibrated";
  doc["connected"]          = telemetryReceived;
  doc["ip"]                 = WiFi.localIP().toString();
  doc["channel"]            = WiFi.channel();
  doc["uptime_ms"]          = millis();

  String out;
  serializeJson(doc, out);
  server.send(200, "application/json", out);
}

// 5. POST /command (Aligned route for receiving mode/torque instructions)
void handleCommand() {
  if (server.method() != HTTP_POST) {
    server.send(405, "application/json", "{\"error\":\"method not allowed\"}");
    return;
  }

  String body = server.arg("plain");
  JsonDocument doc;
  DeserializationError err = deserializeJson(doc, body);
  if (err) {
    server.send(400, "application/json", "{\"error\":\"invalid json\"}");
    return;
  }

  int mode_id = doc["mode_id"] | 0;
  float target_torque = doc["target_torque"] | 0.0f;

  relayCommandToExo(mode_id, target_torque);
  server.send(200, "application/json", "{\"status\":\"ok\"}");
}

// 6. POST /calibrate (Calibration endpoint placeholder)
void handleCalibrate() {
  JsonDocument doc;
  doc["calibration_status"] = latestTelemetry.calibration_status ? "calibrated" : "uncalibrated";
  doc["message"] = "Calibration is performed automatically on Exo Unit boot";

  String out;
  serializeJson(doc, out);
  server.send(200, "application/json", out);
}

// ==================== AUTO WiFi CONNECTION (WiFiManager) ====================
void initWiFi() {
  WiFiManager wm;

  const char* custom_html = 
    "<style>"
    "body { background-color: #F8FAFC !important; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif !important; color: #0F172A !important; padding: 40px 10px !important; display: flex !important; flex-direction: column !important; align-items: center !important; justify-content: center !important; min-height: 90vh !important; margin: 0 !important; }"
    "h1 { color: #229096 !important; font-size: 28px !important; font-weight: 800 !important; text-align: center !important; margin-bottom: 8px !important; }"
    "h3 { color: #64748B !important; font-size: 14px !important; text-align: center !important; margin-top: 0 !important; margin-bottom: 25px !important; font-weight: 500 !important; }"
    "div.wrap { background: #FFFFFF !important; padding: 35px 30px !important; border-radius: 20px !important; box-shadow: 0 10px 25px -5px rgba(15,23,42,0.08), 0 8px 16px -6px rgba(15,23,42,0.04) !important; border: 1px solid #E2E8F0 !important; width: 100% !important; max-width: 480px !important; box-sizing: border-box !important; margin: 20px auto !important; }"
    "button, input[type='submit'] { background-color: #229096 !important; color: #FFFFFF !important; border: none !important; padding: 14px !important; border-radius: 12px !important; font-weight: 600 !important; font-size: 15px !important; cursor: pointer !important; width: 100% !important; margin: 15px 0 5px 0 !important; box-shadow: 0 4px 12px 0 rgba(34, 144, 150, 0.2) !important; transition: all 0.2s ease !important; }"
    "button:hover, input[type='submit']:hover { background-color: #1B757A !important; transform: translateY(-1px) !important; box-shadow: 0 6px 16px 0 rgba(34, 144, 150, 0.3) !important; }"
    "input[type='text'], input[type='password'] { background-color: #FFFFFF !important; border: 1px solid #CBD5E1 !important; padding: 14px 16px !important; border-radius: 12px !important; font-size: 14px !important; color: #0F172A !important; margin-bottom: 15px !important; width: 100% !important; box-sizing: border-box !important; outline: none !important; transition: all 0.2s !important; }"
    "input[type='text']:focus, input[type='password']:focus { border-color: #229096 !important; box-shadow: 0 0 0 3px rgba(34, 144, 150, 0.15) !important; }"
    "div.q { border-bottom: 1px solid #F1F5F9 !important; padding: 12px 8px !important; display: flex !important; justify-content: space-between !important; align-items: center !important; }"
    "div.q a { color: #0F172A !important; text-decoration: none !important; font-weight: 600 !important; font-size: 14px !important; transition: color 0.2s !important; }"
    "div.q a:hover { color: #229096 !important; }"
    "div.msg { background-color: #E9F7F8 !important; color: #229096 !important; padding: 12px 15px !important; border-radius: 10px !important; font-size: 13px !important; border: 1px solid rgba(34, 144, 150, 0.15) !important; margin-bottom: 20px !important; line-height: 1.5 !important; }"
    "a { color: #229096 !important; text-decoration: none !important; font-weight: 600 !important; }"
    "</style>";

  wm.setCustomHeadElement(custom_html);

  // Set up the physical BOOT pin as input with internal pullup resistor
  pinMode(WIFI_RESET_PIN, INPUT_PULLUP);
  delay(100); // debounce delay
  
  // If BOOT button is held down during startup, clear saved WiFi configurations
  if (digitalRead(WIFI_RESET_PIN) == LOW) {
    Serial.println("⚠️ BOOT button held — clearing saved WiFi credentials...");
    wm.resetSettings();
  }

  // Tries to auto-connect using last saved credentials.
  // If it can't, it starts an Access Point called "Samarth-ESP32-Setup"
  wm.setConfigPortalTimeout(180);  // Close configuration portal after 3 minutes
  wm.setConnectTimeout(8);         // Limit saved Wi-Fi search to 8 seconds before starting setup portal AP

  Serial.println("Connecting to WiFi (or starting setup portal)...");
  if (!wm.autoConnect("Samarth-ESP32-Setup")) {
    Serial.println("❌ WiFi setup timed out. Restarting...");
    ESP.restart();
  }

  Serial.println();
  Serial.print("✅ Connected to WiFi. IP: ");
  Serial.println(WiFi.localIP());
  Serial.print("WiFi channel: ");
  Serial.println(WiFi.channel());
  Serial.println("↑ Set WIFI_CHANNEL in esp_to_esp.cpp to this value");
}

// ==================== INITIALIZE ESP-NOW RADIO ====================
void initESPNow() {
  // Sync the ESP-NOW channel to match the WiFi channel assigned by your router
  uint8_t currentChannel = WiFi.channel();
  esp_wifi_set_channel(currentChannel, WIFI_SECOND_CHAN_NONE);

  if (esp_now_init() != ESP_OK) {
    Serial.println("ESP-NOW init failed");
    return;
  }
  
  // Register callback functions
  esp_now_register_send_cb(onDataSent);
  esp_now_register_recv_cb(onDataRecv);

  // Register the Exo Unit (ESP A) as a peer for direct radio communication
  esp_now_peer_info_t peerInfo = {};
  memcpy(peerInfo.peer_addr, exoMAC, 6);
  peerInfo.channel = currentChannel;
  peerInfo.encrypt = false;
  if (esp_now_add_peer(&peerInfo) != ESP_OK) {
    Serial.println("Failed to add exo peer");
  }
}

// ==================== SETUP (RUNS ONCE ON POWER UP) ====================
void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println("\n========== Samarth Bridge Unit ==========");

  // Connect to network
  initWiFi();
  
  // Start radio link
  initESPNow();

  // Register HTTP endpoint routes
  server.on("/exercise",  HTTP_POST, handleExercise);
  server.on("/telemetry", HTTP_GET,  handleTelemetry);
  server.on("/data",      HTTP_GET,  handleData);
  server.on("/status",    HTTP_GET,  handleStatus);
  server.on("/command",   HTTP_POST, handleCommand);
  server.on("/calibrate", HTTP_POST, handleCalibrate);
  server.begin();

  Serial.print("Bridge Unit ready. MAC: ");
  Serial.println(WiFi.macAddress());
  Serial.println("HTTP server started on port 80");
  Serial.println("=========================================");
}

// ==================== LOOP (RUNS REPEATEDLY) ====================
void loop() {
  // Check for and process incoming HTTP client requests
  server.handleClient();
}