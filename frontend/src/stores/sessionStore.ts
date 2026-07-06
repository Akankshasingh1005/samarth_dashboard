import { create } from 'zustand';
import type { ValidationStatus, FrameAngles, SensorReading, ExoMotorStatus } from '@/types';

interface SessionState {
  sessionId: string | null;
  exerciseId: string | null;
  repCount: number;
  timerSeconds: number;
  isRunning: boolean;
  validationStatus: ValidationStatus | null;
  liveAngles: FrameAngles | null;
  poseConfidence: number;
  wsConnected: boolean;
  feedbackMessages: string[];
  // PS3 Sensor State
  sensorConnected: boolean;
  sensorDeviceId: string | null;
  sensorBattery: number;
  sensorCalibration: 'uncalibrated' | 'calibrating' | 'calibrated';
  sensorKneeAngle: number | null;
  sensorHipAngle: number | null;
  sensorFootForce: number | null;
  sensorStance: boolean;
  sensorMotorsActive: boolean;
  sensorKneeMotor: ExoMotorStatus | null;
  sensorHipMotor: ExoMotorStatus | null;
  sensorMode: 'simulated' | 'real';
  lastModeCommand: { mode_name: string; target_torque: number } | null;

  setSession: (sessionId: string, exerciseId: string) => void;
  incrementRep: () => void;
  setRepCount: (n: number) => void;
  setValidation: (v: ValidationStatus) => void;
  setAngles: (a: FrameAngles) => void;
  setConfidence: (c: number) => void;
  setWsConnected: (c: boolean) => void;
  addFeedback: (msg: string) => void;
  startTimer: () => void;
  tickTimer: () => void;
  resetSession: () => void;
  setSensorReading: (r: SensorReading) => void;
  setLastModeCommand: (cmd: { mode_name: string; target_torque: number }) => void;
}

export const useSessionStore = create<SessionState>((set) => ({
  sessionId: null,
  exerciseId: null,
  repCount: 0,
  timerSeconds: 0,
  isRunning: false,
  validationStatus: null,
  liveAngles: null,
  poseConfidence: 0,
  wsConnected: false,
  feedbackMessages: [],
  // PS3 Sensor initial state
  sensorConnected: false,
  sensorDeviceId: null,
  sensorBattery: 0,
  sensorCalibration: 'uncalibrated',
  sensorKneeAngle: null,
  sensorHipAngle: null,
  sensorFootForce: null,
  sensorStance: false,
  sensorMotorsActive: false,
  sensorKneeMotor: null,
  sensorHipMotor: null,
  sensorMode: 'simulated',
  lastModeCommand: null,

  setSession: (sessionId, exerciseId) => set({ sessionId, exerciseId }),
  incrementRep: () => set((s) => ({ repCount: s.repCount + 1 })),
  setRepCount: (n) => set({ repCount: n }),
  setValidation: (v) => set({ validationStatus: v }),
  setAngles: (a) => set({ liveAngles: a }),
  setConfidence: (c) => set({ poseConfidence: c }),
  setWsConnected: (c) => set({ wsConnected: c }),
  addFeedback: (msg) =>
    set((s) => ({ feedbackMessages: [msg, ...s.feedbackMessages].slice(0, 20) })),
  startTimer: () => set({ isRunning: true, timerSeconds: 0, repCount: 0 }),
  tickTimer: () => set((s) => ({ timerSeconds: s.timerSeconds + 1 })),
  setSensorReading: (r) => set({
    sensorConnected: r.connected,
    sensorDeviceId: r.device_id || null,
    sensorBattery: r.battery_percent,
    sensorCalibration: r.calibration_status,
    sensorMode: r.ps3_mode,
    sensorKneeAngle: r.exo ? r.exo.knee_angle : null,
    sensorHipAngle: r.exo ? r.exo.hip_angle : null,
    sensorFootForce: r.exo ? r.exo.foot_force : null,
    sensorStance: r.exo ? r.exo.stance : false,
    sensorMotorsActive: r.exo ? r.exo.motors_active : false,
    sensorKneeMotor: r.exo ? r.exo.knee_motor : null,
    sensorHipMotor: r.exo ? r.exo.hip_motor : null,
  }),
  setLastModeCommand: (cmd) => set({ lastModeCommand: cmd }),
  resetSession: () =>
    set({
      sessionId: null,
      exerciseId: null,
      repCount: 0,
      timerSeconds: 0,
      isRunning: false,
      validationStatus: null,
      liveAngles: null,
      poseConfidence: 0,
      wsConnected: false,
      feedbackMessages: [],
      sensorConnected: false,
      sensorDeviceId: null,
      sensorBattery: 0,
      sensorCalibration: 'uncalibrated',
      sensorKneeAngle: null,
      sensorHipAngle: null,
      sensorFootForce: null,
      sensorStance: false,
      sensorMotorsActive: false,
      sensorKneeMotor: null,
      sensorHipMotor: null,
      sensorMode: 'simulated',
      lastModeCommand: null,
    }),
}));
