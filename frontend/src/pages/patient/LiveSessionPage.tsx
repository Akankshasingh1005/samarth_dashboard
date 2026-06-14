import { useEffect, useRef, useState, useCallback } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  Pause, Square, Activity,
  ArrowUpCircle, ArrowDownCircle, Clock, Repeat,
  Wifi, WifiOff, Zap, Heart, AlertTriangle, ShieldAlert
} from 'lucide-react';
import { useSessionStore } from '@/stores/sessionStore';
import { useAuthStore } from '@/stores/authStore';
import { sessionApi } from '@/api';
import { drawPoseOverlay } from '@/api/poseOverlay';
import { toast } from 'sonner';
import type { PS2ErrorFlags, PS2Confidence } from '@/types';

const ERROR_FLAG_LABELS: Record<keyof PS2ErrorFlags, { label: string; color: string }> = {
  insufficient_ROM: { label: 'Insufficient ROM', color: 'text-amber-600 bg-amber-50 border-amber-200' },
  too_fast: { label: 'Moving Too Fast', color: 'text-red-600 bg-red-50 border-red-200' },
  too_slow: { label: 'Moving Too Slow', color: 'text-blue-600 bg-blue-50 border-blue-200' },
  knee_valgus: { label: 'Knee Valgus', color: 'text-purple-600 bg-purple-50 border-purple-200' },
  asymmetric: { label: 'Asymmetric Motion', color: 'text-orange-600 bg-orange-50 border-orange-200' },
  trunk_comp: { label: 'Trunk Compensation', color: 'text-rose-600 bg-rose-50 border-rose-200' },
};

// Injury-risk flags that trigger HIGH ALERT feedback
const HIGH_ALERT_FLAGS: (keyof PS2ErrorFlags)[] = ['knee_valgus', 'trunk_comp', 'too_fast'];

// Feedback types
type FeedbackItem = {
  id: number;
  message: string;
  type: 'normal' | 'alert' | 'good';
  timestamp: number;
};

function AngleGauge({ label, value, maxAngle = 180 }: { label: string; value: number; maxAngle?: number }) {
  const pct = Math.min((value / maxAngle) * 100, 100);
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs text-slate-500">
        <span>{label}</span>
        <span className="font-semibold text-samarth-text">{value.toFixed(1)}°</span>
      </div>
      <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
        <div
          className="h-full bg-brand rounded-full transition-all duration-100"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

function formatTime(secs: number) {
  const m = Math.floor(secs / 60).toString().padStart(2, '0');
  const s = (secs % 60).toString().padStart(2, '0');
  return `${m}:${s}`;
}

export default function LiveSessionPage() {
  const { sessionId } = useParams<{ sessionId: string; exerciseId: string }>();
  const navigate = useNavigate();
  const { accessToken } = useAuthStore();
  const {
    repCount, setRepCount, timerSeconds, tickTimer, startTimer,
    liveAngles, setAngles, poseConfidence, setConfidence, wsConnected, setWsConnected,
    resetSession,
  } = useSessionStore();

  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const overlayCanvasRef = useRef<HTMLCanvasElement>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const sendIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const landmarksRef = useRef<Record<string, any>>({});

  const [paused, setPaused] = useState(false);
  const [ending, setEnding] = useState(false);
  const [lastRep, setLastRep] = useState<{ flags: PS2ErrorFlags; confidence: PS2Confidence; score: number } | null>(null);
  const [ps2Mode, setPs2Mode] = useState<'mock' | 'real'>('mock');
  const [qualityTrend, setQualityTrend] = useState<'improving' | 'stable' | 'declining'>('stable');
  const [scores, setScores] = useState<number[]>([]);
  const [sensorData] = useState({ battery: 82, connected: false }); // PS3 stub
  void sensorData;
  const [cameraReady, setCameraReady] = useState(false);

  // ── Two-tier feedback system ──────────────────────────────────────
  const [feedbackQueue, setFeedbackQueue] = useState<FeedbackItem[]>([]);
  const [activeFeedback, setActiveFeedback] = useState<FeedbackItem | null>(null);
  const [activeAlert, setActiveAlert] = useState<FeedbackItem | null>(null);
  const feedbackIdRef = useRef(0);

  const addFeedback = useCallback((message: string, type: 'normal' | 'alert' | 'good' = 'normal') => {
    feedbackIdRef.current += 1;
    const item: FeedbackItem = {
      id: feedbackIdRef.current,
      message,
      type,
      timestamp: Date.now(),
    };

    if (type === 'alert') {
      // HIGH ALERT — show immediately, overrides everything
      setActiveAlert(item);
      // Auto-dismiss after 5 seconds
      setTimeout(() => {
        setActiveAlert((current) => (current?.id === item.id ? null : current));
      }, 5000);
    } else {
      // Normal/good feedback — queue it
      setFeedbackQueue((prev) => [...prev, item]);
    }
  }, []);

  // Process feedback queue — show one at a time with 3-second minimum display
  useEffect(() => {
    if (activeFeedback || feedbackQueue.length === 0) return;

    const next = feedbackQueue[0];
    setActiveFeedback(next);
    setFeedbackQueue((prev) => prev.slice(1));

    const timer = setTimeout(() => {
      setActiveFeedback(null);
    }, 3000);

    return () => clearTimeout(timer);
  }, [activeFeedback, feedbackQueue]);

  // Start timer on mount
  useEffect(() => {
    startTimer();
    timerRef.current = setInterval(() => {
      if (!paused) tickTimer();
    }, 1000);
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [paused]);

  // Camera + WebSocket setup
  useEffect(() => {
    const setup = async () => {
      try {
        // Request portrait-friendly ratio for full-body exercise visibility
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { width: { ideal: 480 }, height: { ideal: 640 }, facingMode: 'user' },
          audio: false,
        });
        streamRef.current = stream;
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          await videoRef.current.play();
          setCameraReady(true);
        }
      } catch {
        // Fallback to minimal constraints
        try {
          const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
          streamRef.current = stream;
          if (videoRef.current) {
            videoRef.current.srcObject = stream;
            await videoRef.current.play();
            setCameraReady(true);
          }
        } catch {
          toast.error('Camera not available. Please check permissions.');
        }
      }

      if (!accessToken || !sessionId) return;
      const ws = new WebSocket(`ws://localhost:8000/ws/session/${sessionId}/${accessToken}`);
      wsRef.current = ws;

      ws.onopen = () => {
        setWsConnected(true);
        sendIntervalRef.current = setInterval(() => {
          if (paused || !videoRef.current || !canvasRef.current || ws.readyState !== WebSocket.OPEN) return;
          const canvas = canvasRef.current;
          const ctx = canvas.getContext('2d');
          if (!ctx) return;
          canvas.width = 320;
          canvas.height = 240;
          ctx.drawImage(videoRef.current, 0, 0, 320, 240);
          canvas.toBlob((blob) => {
            if (blob && ws.readyState === WebSocket.OPEN) {
              blob.arrayBuffer().then((buf) => ws.send(buf));
            }
          }, 'image/jpeg', 0.6);
        }, 100); // 10fps during session
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === 'frame_result') {
            if (data.angles) setAngles(data.angles);
            if (data.pose_confidence !== undefined) setConfidence(data.pose_confidence);
            if (data.rep_count !== undefined && data.rep_count !== repCount) {
              setRepCount(data.rep_count);
              if (data.ps2_mode === 'real' || data.ps2_mode === 'mock') {
                setPs2Mode(data.ps2_mode);
              }
              handleRepCompleted(data.rep_count, data.rep_result);
            }
            // Draw skeleton overlay using received landmarks
            if (data.landmarks) {
              landmarksRef.current = data.landmarks;
              const overlay = overlayCanvasRef.current;
              const video = videoRef.current;
              if (overlay && video) {
                overlay.width = video.videoWidth || video.clientWidth;
                overlay.height = video.videoHeight || video.clientHeight;
                const ctx = overlay.getContext('2d');
                if (ctx) {
                  drawPoseOverlay(ctx, overlay.width, overlay.height, data.landmarks, data.angles);
                }
              }
            }
          }
        } catch {}
      };

      ws.onerror = () => setWsConnected(false);
      ws.onclose = () => setWsConnected(false);
    };

    setup();
    return () => {
      if (sendIntervalRef.current) clearInterval(sendIntervalRef.current);
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: 'end' }));
      }
      wsRef.current?.close();
      streamRef.current?.getTracks().forEach((t) => t.stop());
    };
  }, [sessionId, accessToken]);

  const handleRepCompleted = (repNumber: number, repResult?: any) => {
    let score: number;
    let flags: PS2ErrorFlags;
    let confidence: PS2Confidence;

    if (repResult) {
      flags = repResult.error_flags;
      confidence = repResult.confidence;
      score = repResult.session?.session_score ?? 0.8;
      if (repResult.session?.quality_trend) {
        setQualityTrend(repResult.session.quality_trend);
      }
    } else {
      // Simulate PS2 per-rep result (fallback)
      score = Math.random() * 0.4 + 0.6;
      flags = {
        insufficient_ROM: score < 0.7 ? 1 : 0,
        too_fast: Math.random() > 0.8 ? 1 : 0,
        too_slow: 0,
        knee_valgus: Math.random() > 0.85 ? 1 : 0,
        asymmetric: Math.random() > 0.75 ? 1 : 0,
        trunk_comp: Math.random() > 0.9 ? 1 : 0,
      };
      confidence = {
        insufficient_ROM: flags.insufficient_ROM ? 0.85 : 0.12,
        too_fast: flags.too_fast ? 0.87 : 0.08,
        too_slow: 0.05,
        knee_valgus: flags.knee_valgus ? 0.78 : 0.04,
        asymmetric: flags.asymmetric ? 0.82 : 0.15,
        trunk_comp: flags.trunk_comp ? 0.75 : 0.06,
      };
    }

    setLastRep({ flags, confidence, score });

    const newScores = [...scores, score];
    setScores(newScores);
    if (!repResult && newScores.length >= 3) {
      const first = newScores.slice(0, Math.floor(newScores.length / 2));
      const second = newScores.slice(Math.floor(newScores.length / 2));
      const avg1 = first.reduce((a, b) => a + b, 0) / first.length;
      const avg2 = second.reduce((a, b) => a + b, 0) / second.length;
      setQualityTrend(avg2 > avg1 + 0.05 ? 'improving' : avg2 < avg1 - 0.05 ? 'declining' : 'stable');
    }

    // ── Two-tier feedback routing ──────────────────────────────────
    const errors = Object.entries(flags).filter(([_, v]) => v === 1);

    // Check for HIGH ALERT flags (injury risk)
    const alertErrors = errors.filter(([k]) => HIGH_ALERT_FLAGS.includes(k as keyof PS2ErrorFlags));
    if (alertErrors.length > 0) {
      const alertMsg = `⚠️ INJURY RISK — ${alertErrors.map(([k]) => ERROR_FLAG_LABELS[k as keyof PS2ErrorFlags].label).join(', ')}. Correct your form immediately!`;
      addFeedback(alertMsg, 'alert');
    }

    // Normal post-rep feedback
    if (errors.length === 0) {
      addFeedback(`Rep ${repNumber}: Great form! Keep it up.`, 'good');
    } else {
      const normalErrors = errors.filter(([k]) => !HIGH_ALERT_FLAGS.includes(k as keyof PS2ErrorFlags));
      if (normalErrors.length > 0) {
        const msg = `Rep ${repNumber}: ${normalErrors.map(([k]) => ERROR_FLAG_LABELS[k as keyof PS2ErrorFlags].label).join(', ')}`;
        addFeedback(msg, 'normal');
      }
    }
  };

  const handleEndSession = async () => {
    if (ending) return;
    setEnding(true);
    try {
      if (sendIntervalRef.current) {
        clearInterval(sendIntervalRef.current);
        sendIntervalRef.current = null;
      }
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: 'end' }));
        wsRef.current.close();
      }
      await new Promise((resolve) => setTimeout(resolve, 800));
      await sessionApi.complete(sessionId!);
      toast.success('Session completed! Analyzing your performance...');
      resetSession();
      navigate(`/session/summary/${sessionId}`);
    } catch {
      toast.error('Failed to end session');
      setEnding(false);
    }
  };

  const trendColors = {
    improving: 'text-green-600',
    stable: 'text-amber-600',
    declining: 'text-red-600',
  };

  const sessionScore = scores.length > 0 ? scores.reduce((a, b) => a + b, 0) / scores.length : 0;

  return (
    <div className="min-h-screen bg-samarth-bg flex flex-col">
      {/* Top HUD Bar */}
      <div className="bg-navy text-white px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-6">
          {/* Timer */}
          <div className="flex items-center gap-2">
            <Clock className="w-4 h-4 text-slate-400" />
            <span className="font-mono font-bold text-lg text-white">{formatTime(timerSeconds)}</span>
          </div>
          {/* Rep counter */}
          <div className="flex items-center gap-2">
            <Repeat className="w-4 h-4 text-brand" />
            <span className="font-bold text-xl text-brand">{repCount}</span>
            <span className="text-slate-400 text-sm">reps</span>
          </div>
          {/* Session score */}
          <div className="flex items-center gap-2">
            <Activity className="w-4 h-4 text-accent" />
            <span className="font-bold text-accent">{(sessionScore * 100).toFixed(0)}%</span>
            <span className="text-slate-400 text-sm">score</span>
          </div>
        </div>

        <div className="flex items-center gap-4">
          {/* Quality trend */}
          <div className={`flex items-center gap-1 text-sm font-semibold ${trendColors[qualityTrend]}`}>
            {qualityTrend === 'improving' && <ArrowUpCircle className="w-4 h-4" />}
            {qualityTrend === 'declining' && <ArrowDownCircle className="w-4 h-4" />}
            {qualityTrend === 'stable' && <Activity className="w-4 h-4" />}
            {qualityTrend}
          </div>
          {/* PS3 stub */}
          <div className="flex items-center gap-1 text-slate-400 text-xs">
            <Heart className="w-3 h-3" />
            <span className="badge-mock">PS3 — Not Connected</span>
          </div>
          {/* WS status */}
          {wsConnected ? (
            <div className="flex items-center gap-1 text-green-400 text-xs">
              <Wifi className="w-3 h-3" />
              <span>Live</span>
            </div>
          ) : (
            <div className="flex items-center gap-1 text-red-400 text-xs">
              <WifiOff className="w-3 h-3" />
              <span>Disconnected</span>
            </div>
          )}
        </div>
      </div>

      {/* HIGH ALERT overlay — shown immediately for injury risk */}
      {activeAlert && (
        <div className="bg-red-600 text-white px-6 py-3 flex items-center gap-3 animate-alert-pulse">
          <ShieldAlert className="w-6 h-6 flex-shrink-0" />
          <span className="font-bold text-sm flex-1">{activeAlert.message}</span>
          <button onClick={() => setActiveAlert(null)} className="text-white/70 hover:text-white text-xs">
            Dismiss
          </button>
        </div>
      )}

      {/* Main content */}
      <div className="flex-1 flex flex-col lg:flex-row overflow-hidden">
        {/* Camera Feed (full height left) */}
        <div className="lg:w-3/5 relative bg-slate-900">
          {!cameraReady && (
            <div className="absolute inset-0 flex items-center justify-center z-10">
              <div className="text-center text-white">
                <Activity className="w-10 h-10 mx-auto mb-2 animate-pulse text-brand" />
                <p className="text-sm">Starting camera...</p>
              </div>
            </div>
          )}
          <video ref={videoRef} className="w-full h-full object-contain" muted playsInline style={{ minHeight: '60vh' }} />
          <canvas ref={overlayCanvasRef} className="absolute inset-0 w-full h-full pointer-events-none" style={{ objectFit: 'contain' }} />
          <canvas ref={canvasRef as any} className="hidden" />

          {/* Confidence indicator */}
          <div className="absolute top-4 right-4 bg-black/50 backdrop-blur-sm px-3 py-1.5 rounded-xl">
            <div className="flex items-center gap-2">
              <div className={`w-2 h-2 rounded-full ${poseConfidence > 0.5 ? 'bg-green-400' : poseConfidence > 0.25 ? 'bg-amber-400' : 'bg-red-400'}`} />
              <span className="text-white text-xs">Pose: {(poseConfidence * 100).toFixed(0)}%</span>
            </div>
          </div>

          {/* Paused overlay */}
          {paused && (
            <div className="absolute inset-0 bg-black/60 flex items-center justify-center">
              <div className="text-white text-center">
                <Pause className="w-16 h-16 mx-auto mb-3 text-slate-300" />
                <p className="text-xl font-bold">Session Paused</p>
                <button onClick={() => setPaused(false)} className="mt-4 btn-primary px-8">
                  Resume
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Right Panel */}
        <div className="lg:w-2/5 bg-white border-l border-slate-200 flex flex-col overflow-y-auto">
          {/* Angle Gauges */}
          {liveAngles && (
            <div className="p-5 border-b border-slate-100">
              <h3 className="font-display font-bold text-samarth-text mb-4 text-sm uppercase tracking-wide">
                Live Angles
              </h3>
              <div className="space-y-3">
                <AngleGauge label="Left Knee" value={liveAngles.left_knee} />
                <AngleGauge label="Right Knee" value={liveAngles.right_knee} />
                <AngleGauge label="Left Hip" value={liveAngles.left_hip} />
                <AngleGauge label="Right Hip" value={liveAngles.right_hip} />
              </div>
            </div>
          )}

          {/* PS2 Error Flags from last rep */}
          {lastRep && (
            <div className="p-5 border-b border-slate-100">
              <div className="flex items-center justify-between mb-3">
                <h3 className="font-display font-bold text-samarth-text text-sm uppercase tracking-wide">
                  Last Rep Analysis
                </h3>
                <span className={ps2Mode === 'real' ? 'badge-success' : 'badge-mock'}>
                  {ps2Mode === 'real' ? 'PS2 RehabNet' : 'PS2 Mock'}
                </span>
              </div>
              <div className="grid grid-cols-2 gap-2">
                {Object.entries(ERROR_FLAG_LABELS).map(([key, meta]) => {
                  const flag = lastRep.flags[key as keyof PS2ErrorFlags];
                  const conf = lastRep.confidence[key as keyof PS2Confidence];
                  const isHighAlert = HIGH_ALERT_FLAGS.includes(key as keyof PS2ErrorFlags) && flag;
                  return (
                    <div key={key}
                      className={`flex items-center gap-2 p-2 rounded-xl border text-xs transition-all ${
                        isHighAlert ? 'bg-red-100 border-red-300 text-red-800 font-bold' :
                        flag ? meta.color : 'bg-slate-50 border-slate-200 text-slate-400'
                      }`}>
                      <div>
                        <div className={`font-semibold ${flag ? '' : 'text-slate-400'}`}>
                          {isHighAlert && <AlertTriangle className="w-3 h-3 inline mr-1" />}
                          {meta.label}
                        </div>
                        <div className="opacity-70">{flag ? `${(conf * 100).toFixed(0)}% conf.` : 'No error'}</div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* PS3 Sensor Stub */}
          <div className="p-5 border-b border-slate-100">
            <div className="integration-stub">
              <div className="flex items-center gap-2 mb-2">
                <Zap className="w-4 h-4 text-slate-400" />
                <span className="text-sm font-semibold text-slate-500">PS3 Sensor Hub</span>
                <span className="badge-mock">Not Connected</span>
              </div>
              <p className="text-xs text-slate-400">
                Wearable IMU sensor integration available after PS3 module completion.
                Connect device via Bluetooth or USB serial.
              </p>
            </div>
          </div>

          {/* Two-tier Feedback Section */}
          <div className="p-5 flex-1 overflow-y-auto">
            <h3 className="font-display font-bold text-samarth-text text-sm uppercase tracking-wide mb-3">
              Feedback Log
            </h3>

            {/* Active feedback display (paced) */}
            {activeFeedback && (
              <div className={`mb-3 ${
                activeFeedback.type === 'good' ? 'feedback-good' :
                activeFeedback.type === 'alert' ? 'feedback-alert' :
                'feedback-normal'
              }`}>
                {activeFeedback.message}
              </div>
            )}

            {/* Queued messages indicator */}
            {feedbackQueue.length > 0 && (
              <p className="text-xs text-slate-400 mb-2">
                +{feedbackQueue.length} more messages queued...
              </p>
            )}

            {/* No feedback yet */}
            {!activeFeedback && feedbackQueue.length === 0 && repCount === 0 && (
              <p className="text-sm text-slate-400 italic">Feedback will appear as you complete reps...</p>
            )}
          </div>

          {/* Session Controls */}
          <div className="p-5 border-t border-slate-200 flex gap-3">
            <button
              onClick={() => setPaused(!paused)}
              className="btn-secondary flex-1"
              id="pause-session-btn"
            >
              {paused ? <Activity className="w-4 h-4" /> : <Pause className="w-4 h-4" />}
              {paused ? 'Resume' : 'Pause'}
            </button>
            <button
              onClick={handleEndSession}
              disabled={ending}
              className="btn-danger flex-1"
              id="end-session-btn"
            >
              <Square className="w-4 h-4" />
              {ending ? 'Ending...' : 'End Session'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
