// Samarth TypeScript Types

export interface User {
  id: string;
  email: string;
  role: 'patient' | 'therapist' | 'admin';
  first_name: string;
  last_name: string;
  full_name: string;
  avatar_url?: string;
  is_active: boolean;
  created_at: string;
  last_login?: string;
}

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user_id: string;
  role: string;
  full_name: string;
}

export interface Exercise {
  id: string;
  name: string;
  slug: string;
  description: string;
  category: 'knee' | 'hip' | 'ankle' | 'full_leg';
  difficulty: 'beginner' | 'intermediate' | 'advanced';
  target_joints: string[];
  target_reps: number;
  target_sets: number;
  target_rom_degrees: number;
  estimated_duration_seconds: number;
  gif_url?: string;
  thumbnail_url?: string;
  demo_video_url?: string;
  audio_guide_url?: string;
  safety_instructions: string[];
  contraindications: string[];
  is_active: boolean;
}

export interface Session {
  id: string;
  patient_id: string;
  exercise_id: string;
  status: 'in_progress' | 'completed' | 'abandoned';
  mode: 'live' | 'uploaded';
  start_time: string;
  end_time?: string;
  duration_seconds?: number;
  total_reps: number;
  avg_left_rom: number;
  avg_right_rom: number;
  symmetry_score: number;
  ps1_processed: boolean;
  ps2_processed: boolean;
  quality_score?: number;
  quality_trend?: 'improving' | 'stable' | 'declining';
  session_score?: number;
  video_url?: string;
  // PS3 fields
  ps3_connected?: boolean;
  ps3_device_id?: string;
  ps3_sensor_data_path?: string;
  ps3_avg_acceleration?: number;
  ps3_peak_acceleration?: number;
  ps3_commands_sent?: number;
  ps3_last_mode?: string;
}

export interface FrameAngles {
  left_hip: number;
  right_hip: number;
  left_knee: number;
  right_knee: number;
  left_ankle: number;
  right_ankle: number;
}

export interface ValidationStatus {
  left_hip_visible: boolean;
  right_hip_visible: boolean;
  left_knee_visible: boolean;
  right_knee_visible: boolean;
  left_ankle_visible: boolean;
  right_ankle_visible: boolean;
  full_lower_body_visible: boolean;
  inside_zone: boolean;
  adequate_lighting: boolean;
  camera_stable: boolean;
  all_valid: boolean;
  guidance_message: string;
}

// PS2 Types
export interface PS2ErrorFlags {
  insufficient_ROM: number;
  too_fast: number;
  too_slow: number;
  knee_valgus: number;
  asymmetric: number;
  trunk_comp: number;
}

export interface PS2Confidence {
  insufficient_ROM: number;
  too_fast: number;
  too_slow: number;
  knee_valgus: number;
  asymmetric: number;
  trunk_comp: number;
}

export interface PS2ModeCommand {
  mode_id: number;
  mode_name: string;
  target_torque: number;
}

export interface PS2SessionMetrics {
  rep_number: number;
  session_score: number;
  quality_trend: 'improving' | 'stable' | 'declining';
}

export interface PS2RepResult {
  timestamp: number;
  rep_id: number;
  dtw_bypassed: boolean;
  error_flags: PS2ErrorFlags;
  confidence: PS2Confidence;
  mode_command: PS2ModeCommand;
  session: PS2SessionMetrics;
}

export interface PS2SessionResult {
  session_id: string;
  total_reps_analyzed: number;
  overall_session_score: number;
  quality_trend: 'improving' | 'stable' | 'declining';
  rep_results: PS2RepResult[];
  dominant_errors: string[];
  recommendations: string[];
  ps2_mode: 'real';
}

// PS3 Types
export interface ExoMotorStatus {
  pwm: number;
  direction: 'ext' | 'flex';
}

export interface ExoSensorData {
  knee_angle: number;
  hip_angle: number;
  foot_force: number;
  stance: boolean;
  knee_motor: ExoMotorStatus;
  hip_motor: ExoMotorStatus;
  motors_active: boolean;
}

export interface SensorReading {
  connected: boolean;
  device_id?: string;
  battery_percent: number;
  signal_strength: number;
  calibration_status: 'uncalibrated' | 'calibrating' | 'calibrated';
  connection_status: 'disconnected' | 'connecting' | 'connected';
  accelerometer: { x: number; y: number; z: number };
  gyroscope: { x: number; y: number; z: number };
  temperature_celsius: number;
  timestamp: number;
  ps3_mode: 'simulated' | 'real';
  exo?: ExoSensorData;
  esp_url?: string;
}

export interface PS3Status {
  connected: boolean;
  device_id?: string;
  battery_percent: number;
  calibration_status: 'uncalibrated' | 'calibrating' | 'calibrated';
  last_command?: {
    cmd: string;
    mode_id: number;
    mode_name: string;
    target_torque: number;
  };
  commands_sent: number;
}

// Analytics Types
export interface WeeklyProgress {
  week: string;
  year: number;
  date?: string;
  sessions: number;
  total_reps: number;
  avg_left_rom: number;
  avg_right_rom: number;
  avg_symmetry: number;
  avg_score: number;
}

export interface ROMTrend {
  date: string;
  avg_left_rom: number;
  avg_right_rom: number;
  avg_symmetry: number;
  sessions: number;
}

export interface AnalyticsSummary {
  total_sessions: number;
  completed_sessions: number;
  total_reps: number;
  avg_left_rom: number;
  avg_right_rom: number;
  avg_symmetry: number;
  avg_session_score: number;
  completion_rate: number;
}

export interface Notification {
  id: string;
  type: string;
  title: string;
  message: string;
  is_read: boolean;
  action_url?: string;
  created_at: string;
}
