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

// ==================== CONFIGURATION (FILL THESE) ====================
// MAC Address of the Bridge Unit (ESP32 #2)
uint8_t bridgeMAC[] = {0xB4, 0xBF, 0xE9, 0x0E, 0x13, 0x68};

// Radio channel (must match the channel printed by ESP B when it connects to your WiFi)
#define WIFI_CHANNEL 11   

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

// 2. Outgoing telemetry structure (Sent from Here -> ESP B -> Website)
typedef struct {
  float battery_percent;
  bool  calibration_status;
  float knee_angle;
  float hip_angle;
  float foot_force;
  bool  stance;
  int   knee_motor_pwm;
  bool  knee_motor_dir;   // true = forward / extension, false = backward
  int   hip_motor_pwm;
  bool  hip_motor_dir;    // true = forward / extension, false = backward
  bool  motors_active;
} telemetry_t;

telemetry_t telemetry;

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

// ==================== INITIALIZE ESP-NOW RADIO ====================
void initESPNow() {
  WiFi.mode(WIFI_STA);
  esp_wifi_set_channel(WIFI_CHANNEL, WIFI_SECOND_CHAN_NONE);
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
  peerInfo.channel = WIFI_CHANNEL;
  peerInfo.encrypt = false;
  if (esp_now_add_peer(&peerInfo) != ESP_OK) {
    Serial.println("Failed to add bridge peer");
  }
}

// ==================== SEND DATA TO WEBSITE ====================
void sendTelemetry() {
  telemetry.battery_percent = readBatteryPercent();
  telemetry.calibration_status = calibration_done;
  telemetry.knee_angle = knee_angle;
  telemetry.hip_angle = hip_angle;
  telemetry.foot_force = foot_force;
  telemetry.stance = stance_detected;
  telemetry.knee_motor_pwm = knee_pwm;
  telemetry.knee_motor_dir = knee_dir_forward;
  telemetry.hip_motor_pwm = hip_pwm;
  telemetry.hip_motor_dir = hip_dir_forward;
  telemetry.motors_active = motor_enabled;

  // Send the data packet over the radio link to ESP B
  esp_now_send(bridgeMAC, (uint8_t*)&telemetry, sizeof(telemetry));
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