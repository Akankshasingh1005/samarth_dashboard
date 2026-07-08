/*
  ===========================================================================
  EXO UNIT (ESP32 #1) - Code for the Exoskeleton Leg Unit
  ===========================================================================
  
  What this device does:
  1. Reads joint angles of the thigh and shank using two MPU6050 IMU sensors.
  2. Reads how hard the patient's foot pushes the ground using a Force Sensor (FSR).
  3. Drives two motor controllers (BTS7960) to help or resist knee and hip movement.
  4. Talks to the BRIDGE UNIT (ESP32 #2) directly over ESP-NOW (direct radio, no internet needed).
     - Receives: Mode (Assist/Resist) and Target Torque from the website.
     - Sends: Telemetry data (angles, forces, motor speeds) back to the website.
     
  How to configure:
  - Fill in the MAC address of ESP B (Bridge) in `bridgeMAC[]`.
  - Match the `WIFI_CHANNEL` with your router's channel.
  ===========================================================================
*/

#include <esp_now.h>
#include <WiFi.h>
#include <esp_wifi.h>
#include <Wire.h>
#include <MPU6050.h>
#include <I2Cdev.h>
#include <ArduinoJson.h>
#include <WiFiManager.h>

// ==================== CONFIGURATION (FILL THESE) ====================
// MAC Address of the Bridge Unit (ESP32 #2)
uint8_t bridgeMAC[] = {0xB4, 0xBF, 0xE9, 0x0E, 0x13, 0x68};

// Pin definition for the BOOT button on the ESP32 (GPIO 0)
// Hold down this button while powering on to reset WiFi settings.
#define WIFI_RESET_PIN 0

// ==================== MOTOR PIN DEFINITIONS ====================
// Pins to control the Knee motor speed and direction (BTS7960 driver)
#define KNEE_RPWM  4   // Forward speed control pin
#define KNEE_LPWM  16  // Backward speed control pin
#define KNEE_R_EN  17  // Enable forward drive (High = Active)
#define KNEE_L_EN  5   // Enable backward drive (High = Active)

// Pins to control the Hip motor speed and direction (BTS7960 driver)
#define HIP_RPWM   13  // Forward speed control pin
#define HIP_LPWM   14  // Backward speed control pin
#define HIP_R_EN   15  // Enable forward drive (High = Active)
#define HIP_L_EN   12  // Enable backward drive (High = Active)

// Sensor pin for the foot force sensor
#define FSR_PIN    34  // Analog pin A0 / GPIO 34

// Motor PWM settings (High frequency to avoid motor whining noise)
#define PWM_FREQ   20000 // 20 kHz
#define PWM_RES    8     // 8-bit resolution (speed values from 0 to 255)
#define PWM_MAX    255   // Max speed value

// ==================== TORQUE -> MOTOR SPEED SCALING ====================
// Target torque is received as a decimal number (0.0 to 2.0 Nm) from the website.
// The scale factor converts this torque value into a motor speed (0 to 255 PWM).
#define TORQUE_TO_PWM_SCALE 150.0
#define MAX_TORQUE 2.0

// ==================== SENSOR OBJECTS ====================
// MPU6050 Accelerometer/Gyroscope sensors
MPU6050 mpu_thigh(0x68);    // Thigh sensor (I2C address 0x68)
MPU6050 mpu_shank(0x69);    // Shank/Calf sensor (I2C address 0x69 - AD0 pin set HIGH)

// Raw angles and offset variables
float thigh_pitch = 0, shank_pitch = 0;
float thigh_gyro_offset = 0, shank_gyro_offset = 0;
unsigned long last_imu_time = 0;

// ==================== TIMER INTERVALS ====================
unsigned long lastTelemetryTime = 0;
const int TELEMETRY_INTERVAL = 10;    // Send data to website at 100 Hz (every 10ms)
unsigned long lastControlTime = 0;
const int CONTROL_INTERVAL = 5;       // Adjust motor speeds at 200 Hz (every 5ms)

// ==================== CURRENT EXOSKELETON STATE ====================
float knee_angle = 0;         // Calculated knee angle in degrees (0 to 130)
float hip_angle = 0;          // Calculated hip angle in degrees (-30 to 120)
float foot_force = 0;         // Foot force force in Newtons
bool stance_detected = false; // True when patient is stepping on the ground
bool calibration_done = false;// True after IMUs are calibrated on boot

// ==================== MOTOR STATE ====================
bool motor_enabled = false;
int knee_pwm = 0;
bool knee_dir_forward = true;
int hip_pwm = 0;
bool hip_dir_forward = true;

int current_mode_id = 0;         // Current Mode: 0 = Off, 1 = Stance-Assist, 2 = Constant Assist
float current_target_torque = 0.0;

// ==================== DATA PACKET STRUCTURES ====================
// 1. Incoming command structure (Relayed from Website -> ESP B -> Here)
typedef struct {
  int mode_id;
  float target_torque;
} exercise_cmd_t;

exercise_cmd_t incomingCommand;

// ==================== ESP-NOW RADIO CALLBACKS ====================
#if ESP_ARDUINO_VERSION >= ESP_ARDUINO_VERSION_VAL(3, 0, 0)
// This function triggers when a packet is successfully sent (not used, kept as standard)
void onDataSent(const wifi_tx_info_t *info, esp_now_send_status_t status) {}

// This function triggers automatically whenever we receive a command from ESP B (Bridge)
void onDataRecv(const esp_now_recv_info_t *info, const uint8_t *data, int len) {
#else
void onDataSent(const uint8_t *mac, esp_now_send_status_t status) {}
void onDataRecv(const uint8_t *mac, const uint8_t *data, int len) {
#endif
  if (len != sizeof(exercise_cmd_t)) return; // Ignore corrupted packets
  memcpy(&incomingCommand, data, sizeof(incomingCommand));
  current_mode_id = incomingCommand.mode_id;
  current_target_torque = incomingCommand.target_torque;
}

// ==================== MOTOR CONTROL FUNCTIONS ====================
// Initialize the PWM hardware to control motor speeds (Arduino-ESP32 v3.x compatible)
void setupPWM() {
  ledcAttach(KNEE_RPWM, PWM_FREQ, PWM_RES);
  ledcAttach(KNEE_LPWM, PWM_FREQ, PWM_RES);
  ledcAttach(HIP_RPWM,  PWM_FREQ, PWM_RES);
  ledcAttach(HIP_LPWM,  PWM_FREQ, PWM_RES);
}

// Stop both knee and hip motors instantly
void stopAllMotors() {
  ledcWrite(KNEE_RPWM, 0); ledcWrite(KNEE_LPWM, 0);
  ledcWrite(HIP_RPWM,  0); ledcWrite(HIP_LPWM,  0);
  knee_pwm = 0; hip_pwm = 0;
}

// Drive the Knee Motor at a specific speed (0 to 255) and direction
void driveKneeMotor(int pwm, bool forward) {
  pwm = constrain(pwm, 0, PWM_MAX);
  if (forward) { 
    ledcWrite(KNEE_RPWM, pwm); 
    ledcWrite(KNEE_LPWM, 0); 
  } else { 
    ledcWrite(KNEE_RPWM, 0);   
    ledcWrite(KNEE_LPWM, pwm); 
  }
}

// Drive the Hip Motor at a specific speed (0 to 255) and direction
void driveHipMotor(int pwm, bool forward) {
  pwm = constrain(pwm, 0, PWM_MAX);
  if (forward) { 
    ledcWrite(HIP_RPWM, pwm); 
    ledcWrite(HIP_LPWM, 0); 
  } else { 
    ledcWrite(HIP_RPWM, 0);   
    ledcWrite(HIP_LPWM, pwm); 
  }
}

// ==================== SENSOR: READ joint angles (IMUs) ====================
// Read accelerometer/gyroscope raw data, apply complementary filter to find pitch
void readMPU(MPU6050 &mpu, float &pitch, float &gyro_offset) {
  int16_t ax, ay, az, gx, gy, gz;
  mpu.getMotion6(&ax, &ay, &az, &gx, &gy, &gz);

  // Pitch calculation using trigonometry
  float acc_pitch = atan2(-ax, sqrt((float)ay*ay + (float)az*az)) * 180.0 / M_PI;
  float gyro_rate = (gx - gyro_offset) / 131.0;

  unsigned long now = micros();
  float dt = (now - last_imu_time) / 1000000.0;
  if (dt < 0) dt = 0.001; // Avoid divide by zero
  last_imu_time = now;

  // Complementary filter: combines 98% Gyro (fast) + 2% Accel (stable) to find true angle
  pitch = 0.98 * (pitch + gyro_rate * dt) + 0.02 * acc_pitch;
}

// Keep the sensor perfectly still on boot to record baseline offset values
void calibrateIMU(MPU6050 &mpu, float &gyro_offset) {
  long sum = 0;
  for (int i = 0; i < 100; i++) {
    int16_t gx, gy, gz;
    mpu.getRotation(&gx, &gy, &gz);
    sum += gx;
    delay(5);
  }
  gyro_offset = sum / 100.0;
}

// Read both IMU sensors and calculate the joint angles
void readIMUs() {
  readMPU(mpu_thigh, thigh_pitch, thigh_gyro_offset);
  readMPU(mpu_shank, shank_pitch, shank_gyro_offset);

  // Knee angle is the difference between Thigh angle and Calf/Shank angle
  knee_angle = thigh_pitch - shank_pitch;
  hip_angle = thigh_pitch;
  
  // Safe bounds check
  knee_angle = constrain(knee_angle, 0, 130);
  hip_angle = constrain(hip_angle, -30, 120);
}

// ==================== SENSOR: READ Foot Pressure Sensor (FSR) ====================
// Read FSR voltage, calculate electrical resistance, and convert to force in Newtons
void readFSR() {
  int raw = analogRead(FSR_PIN);
  float voltage = (raw / 4095.0) * 3.3; // Convert 12-bit ADC reading to Voltage
  float fsr_resistance;
  
  if (voltage < 0.01) {
    fsr_resistance = 10000000;
  } else {
    fsr_resistance = (10000.0 * (3.3 - voltage)) / voltage;
  }

  if (fsr_resistance > 1000000) {
    foot_force = 0; // No pressure
  } else {
    float conductance = 1.0 / fsr_resistance;
    foot_force = (conductance * 1e6) / 800.0; // Estimate force
  }
  
  // Simple low-pass filter to smooth out sensor spikes/noise
  static float filtered_force = 0;
  filtered_force = 0.9 * filtered_force + 0.1 * foot_force;
  foot_force = filtered_force;
  
  // If force is greater than 2 Newtons, detect that foot is on the ground
  stance_detected = (foot_force > 2.0);
}

// ==================== BATTERY level (Placeholder) ====================
float readBatteryPercent() {
  return 100.0; // Default to 100%. Replace with an ADC divider reading later.
}

// ==================== MAIN MOTOR CONTROL / MODES ====================
// Apply the assistive/resistive motor force based on active exercise mode
void applyControl() {
  // Mode 0: Safe Stop
  if (current_mode_id == 0) {
    motor_enabled = false;
    stopAllMotors();
    return;
  }

  motor_enabled = true;
  float torque = constrain(current_target_torque, 0.0, MAX_TORQUE);

  // Mode 1: Gait-triggered assist
  // Only push when the user's foot is on the ground (stance phase) and joint exceeds thresholds
  if (current_mode_id == 1) {
    if (stance_detected && knee_angle > 30) {
      // Calculate speed scaled by current angle and target torque
      knee_pwm = constrain((int)(torque * TORQUE_TO_PWM_SCALE * (knee_angle - 30) / 90.0), 0, PWM_MAX);
      knee_dir_forward = true;
    } else {
      knee_pwm = 0;
    }
    if (stance_detected && hip_angle > 20) {
      hip_pwm = constrain((int)(torque * TORQUE_TO_PWM_SCALE * (hip_angle - 20) / 100.0), 0, PWM_MAX);
      hip_dir_forward = true;
    } else {
      hip_pwm = 0;
    }
  } 
  // Mode 2: Constant Assist
  // Pushes constantly, ignoring whether foot is on the ground or not
  else if (current_mode_id == 2) {
    knee_pwm = constrain((int)(torque * TORQUE_TO_PWM_SCALE), 0, PWM_MAX);
    knee_dir_forward = true;
    hip_pwm = constrain((int)(torque * TORQUE_TO_PWM_SCALE), 0, PWM_MAX);
    hip_dir_forward = true;
  } 
  // Unknown mode: Safe Stop
  else {
    knee_pwm = 0;
    hip_pwm = 0;
  }

  driveKneeMotor(knee_pwm, knee_dir_forward);
  driveHipMotor(hip_pwm, hip_dir_forward);
}

// ==================== AUTO WiFi CONNECTION (WiFiManager) ====================
void initWiFi() {
  WiFiManager wm;

  // Custom styling for setup page
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

  wm.setConfigPortalTimeout(180);  // Close configuration portal after 3 minutes
  wm.setConnectTimeout(8);         // Limit saved Wi-Fi search to 8 seconds

  Serial.println("Connecting Exo Unit to WiFi...");
  if (!wm.autoConnect("Samarth-ESP32-Exo-Setup")) {
    Serial.println("❌ WiFi setup timed out. Restarting...");
    ESP.restart();
  }

  Serial.println();
  Serial.print("✅ Connected to WiFi. IP: ");
  Serial.println(WiFi.localIP());
  Serial.print("WiFi channel: ");
  Serial.println(WiFi.channel());
}

// ==================== INITIALIZE ESP-NOW RADIO ====================
void initESPNow() {
  uint8_t currentChannel = WiFi.channel();
  esp_wifi_set_channel(currentChannel, WIFI_SECOND_CHAN_NONE);
  esp_wifi_set_ps(WIFI_PS_NONE); // Disable power saving for maximum radio speed/reliability

  if (esp_now_init() != ESP_OK) {
    Serial.println("ESP-NOW init failed");
    return;
  }
  
  // Register receiver and sender callback functions
  esp_now_register_send_cb(onDataSent);
  esp_now_register_recv_cb(onDataRecv);

  // Register the Bridge Unit (ESP B) as a radio peer
  esp_now_peer_info_t peerInfo = {};
  memcpy(peerInfo.peer_addr, bridgeMAC, 6);
  peerInfo.channel = currentChannel;
  peerInfo.encrypt = false;
  if (esp_now_add_peer(&peerInfo) != ESP_OK) {
    Serial.println("Failed to add bridge peer");
  }
}

// ==================== SEND DATA TO BRIDGE (as JSON) ====================
void sendTelemetry() {
  // Build JSON document matching the format expected by the website:
  // {"knee_angle":75.3,"hip_angle":45.1,"foot_force":3.42,"stance":true,
  //  "knee_pwm":95,"knee_dir":"ext","hip_pwm":60,"hip_dir":"ext","motors":"on"}
  JsonDocument doc;
  doc["knee_angle"]  = knee_angle;
  doc["hip_angle"]   = hip_angle;
  doc["foot_force"]  = foot_force;
  doc["stance"]      = stance_detected;
  doc["knee_pwm"]    = knee_pwm;
  doc["knee_dir"]    = knee_dir_forward ? "ext" : "flex";
  doc["hip_pwm"]     = hip_pwm;
  doc["hip_dir"]     = hip_dir_forward ? "ext" : "flex";
  doc["motors"]      = motor_enabled ? "on" : "off";

  // Serialize to string and send over ESP-NOW radio link to ESP B
  char jsonBuffer[256];
  size_t len = serializeJson(doc, jsonBuffer, sizeof(jsonBuffer));
  esp_now_send(bridgeMAC, (uint8_t*)jsonBuffer, len);
}

// ==================== SETUP (RUNS ONCE ON POWER UP) ====================
void setup() {
  Serial.begin(115200);
  
  // Start I2C communication (Pins: SDA=21, SCL=22)
  Wire.begin(21, 22);
  Wire.setClock(400000); // 400kHz fast I2C mode

  // Initialize both IMUs
  mpu_thigh.initialize();
  mpu_shank.initialize();
  if (!mpu_thigh.testConnection() || !mpu_shank.testConnection()) {
    Serial.println("MPU6050 connection failed! Check wiring.");
    while (1); // Halt if sensors are disconnected
  }
  
  mpu_thigh.setFullScaleGyroRange(MPU6050_GYRO_FS_250);
  mpu_shank.setFullScaleGyroRange(MPU6050_GYRO_FS_250);

  // Calibrate Gyro scopes. KEEP DEVICE STILL during boot.
  Serial.println("Calibrating IMU gyros... keep sensors still");
  calibrateIMU(mpu_thigh, thigh_gyro_offset);
  calibrateIMU(mpu_shank, shank_gyro_offset);
  last_imu_time = micros();
  calibration_done = true;

  // Configure Motor speed enable pins as outputs
  setupPWM();
  pinMode(KNEE_R_EN, OUTPUT); pinMode(KNEE_L_EN, OUTPUT);
  pinMode(HIP_R_EN, OUTPUT);  pinMode(HIP_L_EN, OUTPUT);
  digitalWrite(KNEE_R_EN, HIGH); digitalWrite(KNEE_L_EN, HIGH);
  digitalWrite(HIP_R_EN, HIGH);  digitalWrite(HIP_L_EN, HIGH);
  stopAllMotors(); // Ensure motors don't spin on boot

  // Start Radio
  initWiFi();
  initESPNow();
  
  Serial.print("Exo Unit ready. MAC: ");
  Serial.println(WiFi.macAddress());
}

// ==================== LOOP (RUNS REPEATEDLY) ====================
void loop() {
  unsigned long now = millis();

  // Read sensors and adjust motor speeds as fast as possible
  readIMUs();
  readFSR();
  applyControl();

  // Send updates to website every 10 milliseconds
  if (now - lastTelemetryTime >= TELEMETRY_INTERVAL) {
    sendTelemetry();
    lastTelemetryTime = now;
  }

  delay(1); // Give ESP32 CPU a break for internal processes
}