import { create } from 'zustand';
import type { ValidationStatus, FrameAngles } from '@/types';

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
  setSession: (sessionId, exerciseId) => set({ sessionId, exerciseId }),
  incrementRep: () => set((s) => ({ repCount: s.repCount + 1 })),
  setRepCount: (n) => set({ repCount: n }),
  setValidation: (v) => set({ validationStatus: v }),
  setAngles: (a) => set({ liveAngles: a }),
  setConfidence: (c) => set({ poseConfidence: c }),
  setWsConnected: (c) => set({ wsConnected: c }),
  addFeedback: (msg) =>
    set((s) => ({ feedbackMessages: [msg, ...s.feedbackMessages].slice(0, 20) })),
  startTimer: () => set({ isRunning: true }),
  tickTimer: () => set((s) => ({ timerSeconds: s.timerSeconds + 1 })),
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
    }),
}));
