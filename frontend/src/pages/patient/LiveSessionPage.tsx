import { useEffect, useRef, useState, useCallback } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  Pause, Square, Activity,
  ArrowUpCircle, ArrowDownCircle, Clock, Repeat,
  Wifi, WifiOff, Zap, Heart, AlertTriangle, ShieldAlert
} from 'lucide-react';
import { useSessionStore } from '@/stores/sessionStore';
import { useAuthStore } from '@/stores/authStore';
import { sessionApi, sensorApi } from '@/api';
import { drawPoseOverlay } from '@/api/poseOverlay';
import { getSharedCameraStream, releaseSharedCameraStream } from '@/stores/cameraStore';
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

// Angle range thresholds for correctness feedback
const ANGLE_RANGES: Record<string, { good: [number, number]; warning: [number, number] }> = {
  left_knee:   { good: [80, 170], warning: [60, 175] },
  right_knee:  { good: [80, 170], warning: [60, 175] },
  left_hip:    { good: [90, 175], warning: [70, 180] },
  right_hip:   { good: [90, 175], warning: [70, 180] },
};

// Minimum pose confidence to display angle gauges in the side panel
const MIN_DISPLAY_CONFIDENCE = 0.25;

function getAngleStatus(key: string, value: number): 'good' | 'warning' | 'bad' {
  const range = ANGLE_RANGES[key];
  if (!range) return 'good';
  if (value >= range.good[0] && value <= range.good[1]) return 'good';
  if (value >= range.warning[0] && value <= range.warning[1]) return 'warning';
  return 'bad';
}

const STATUS_BADGE = {
  good:    { icon: '✓', label: 'Good', bg: 'bg-green-50', text: 'text-green-600', bar: 'bg-green-500', border: 'border-green-200' },
  warning: { icon: '!', label: 'Adjust', bg: 'bg-amber-50', text: 'text-amber-600', bar: 'bg-amber-500', border: 'border-amber-200' },
  bad:     { icon: '✗', label: 'Incorrect', bg: 'bg-red-50', text: 'text-red-600', bar: 'bg-red-500', border: 'border-red-200' },
};

function AngleGauge({ label, value, angleKey, maxAngle = 180 }: { label: string; value: number; angleKey: string; maxAngle?: number }) {
  const pct = Math.min((value / maxAngle) * 100, 100);
  const status = getAngleStatus(angleKey, value);
  const badge = STATUS_BADGE[status];
  return (
    <div className={`p-2.5 rounded-xl border ${badge.border} ${badge.bg} transition-all duration-200`}>
      <div className="flex justify-between items-center text-xs mb-1.5">
        <span className="font-medium text-slate-600">{label}</span>
        <div className="flex items-center gap-1.5">
          <span className={`font-bold text-base ${badge.text}`}>{value.toFixed(1)}°</span>
          <span className={`inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded-full text-[10px] font-bold ${badge.bg} ${badge.text} border ${badge.border}`}>
            {badge.icon} {badge.label}
          </span>
        </div>
      </div>
      <div className="h-2 bg-white/60 rounded-full overflow-hidden">
        <div
          className={`h-full ${badge.bar} rounded-full transition-all duration-150`}
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
    validationStatus, setValidation,
    sensorConnected, sensorDeviceId, sensorBattery, sensorCalibration,
    sensorFootForce, sensorStance,
    sensorMotorsActive, sensorKneeMotor, sensorHipMotor,
    lastModeCommand, setSensorReading, setLastModeCommand,
  } = useSessionStore();

  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const overlayCanvasRef = useRef<HTMLCanvasElement>(null);
  const cameraStageRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const sendIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const keepAliveRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const landmarksRef = useRef<Record<string, any>>({});
  // Ref mirrors paused state so the frame-sending interval closure always reads current value
  const pausedRef = useRef(false);
  // Prevents double-sending the 'end' WS message (on button click + unmount)
  const wsEndedRef = useRef(false);
  // Throttle: only send a new frame after the previous one got a response
  const readyToSendRef = useRef(true);
  // Ref mirrors repCount so WS onmessage closure always reads the latest value
  const repCountRef = useRef(0);
  // Ref mirrors timerSeconds so handleEndSession always reads the latest value
  const timerSecondsRef = useRef(0);

  const [paused, setPaused] = useState(false);
  const [ending, setEnding] = useState(false);

  // Helper: stop camera stream and clear video element
  const stopCamera = useCallback(() => {
    // Release the shared camera stream (stops all tracks globally)
    releaseSharedCameraStream();
    streamRef.current = null;
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
  }, []);

  // Helper: start camera stream and attach to video element
  const startCamera = useCallback(async () => {
    try {
      // Use shared camera store — reuses the already-running stream from
      // CameraValidationPage so joints carry forward instantly.
      const stream = await getSharedCameraStream();
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
        setCameraReady(true);
      }
    } catch {
      toast.error('Camera not available. Please check permissions.');
    }
  }, []);

  const [lastRep, setLastRep] = useState<{ flags: PS2ErrorFlags; confidence: PS2Confidence; score: number } | null>(null);
  const [qualityTrend, setQualityTrend] = useState<'improving' | 'stable' | 'declining'>('stable');
  const [scores, setScores] = useState<number[]>([]);
  const [espUrl, setEspUrl] = useState('http://192.168.1.100');
  const [calibratingSensor, setCalibratingSensor] = useState(false);
  const [cameraReady, setCameraReady] = useState(false);

  // -- Two-tier feedback system ------------------------------------
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
      // HIGH ALERT - show immediately, overrides everything
      setActiveAlert(item);
      // Auto-dismiss after 5 seconds
      setTimeout(() => {
        setActiveAlert((current) => (current?.id === item.id ? null : current));
      }, 5000);
    } else {
      // Normal/good feedback - queue it
      setFeedbackQueue((prev) => [...prev, item]);
    }
  }, []);
 
  // Process feedback queue - show one at a time with 3-second minimum display
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

  // Keep pausedRef in sync with paused state
  useEffect(() => {
    pausedRef.current = paused;
  }, [paused]);

  // Keep timerSecondsRef in sync with timerSeconds for handleEndSession
  useEffect(() => {
    timerSecondsRef.current = timerSeconds;
  }, [timerSeconds]);

  // Start timer on mount
  useEffect(() => {
    startTimer();
    timerRef.current = setInterval(() => {
      if (!pausedRef.current) tickTimer();
    }, 1000);
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, []);

  // Keep-alive pings when paused (prevents backend WebSocket timeout)
  useEffect(() => {
    if (paused) {
      keepAliveRef.current = setInterval(() => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
          wsRef.current.send(JSON.stringify({ type: 'ping' }));
        }
      }, 15000); // Ping every 15 seconds while paused
    } else {
      if (keepAliveRef.current) {
        clearInterval(keepAliveRef.current);
        keepAliveRef.current = null;
      }
    }
    return () => {
      if (keepAliveRef.current) {
        clearInterval(keepAliveRef.current);
        keepAliveRef.current = null;
      }
    };
  }, [paused]);

  // Load sensor status and auto-connect on mount
  useEffect(() => {
    const initSensor = async () => {
      try {
        const status = await sensorApi.status();
        setSensorReading(status);
        if (status.esp_url) {
          setEspUrl(status.esp_url);
          if (!status.connected) {
            // Background try connection to warm up backend hub
            await sensorApi.connect(status.esp_url).catch(() => null);
            const updated = await sensorApi.status().catch(() => null);
            if (updated) setSensorReading(updated);
          }
        }
      } catch (err) {
        console.error('Failed to initialize sensor:', err);
      }
    };
    initSensor();
  }, [setSensorReading]);

  // Camera + WebSocket setup
  useEffect(() => {
    const setup = async () => {
      try {
        await startCamera();
      } catch {
        // startCamera already handles errors internally
      }

      if (!accessToken || !sessionId) return;
      const ws = new WebSocket(`ws://localhost:8000/ws/session/${sessionId}/${accessToken}`);
      wsRef.current = ws;

      ws.onopen = () => {
        setWsConnected(true);
        sendIntervalRef.current = setInterval(() => {
          // Read from ref (not closure) so pause actually stops frame sending
          if (pausedRef.current || !videoRef.current || !canvasRef.current || ws.readyState !== WebSocket.OPEN || !readyToSendRef.current) return;
          readyToSendRef.current = false; // Wait for response before sending next frame
          const canvas = canvasRef.current;
          const ctx = canvas.getContext('2d');
          if (!ctx) { readyToSendRef.current = true; return; }
          const sourceWidth = videoRef.current.videoWidth || 480;
          const sourceHeight = videoRef.current.videoHeight || 640;
          const scale = Math.min(1, 640 / Math.max(sourceWidth, sourceHeight));
          canvas.width = Math.max(1, Math.round(sourceWidth * scale));
          canvas.height = Math.max(1, Math.round(sourceHeight * scale));
          ctx.drawImage(videoRef.current, 0, 0, canvas.width, canvas.height);
          canvas.toBlob((blob) => {
            if (blob && ws.readyState === WebSocket.OPEN) {
              blob.arrayBuffer().then((buf) => ws.send(buf));
            } else {
              readyToSendRef.current = true; // Re-enable if blob failed
            }
          }, 'image/jpeg', 0.6);
        }, 66); // 15fps max, but throttled by readyToSend
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === 'frame_result' || data.type === 'frame_dropped') {
            readyToSendRef.current = true; // Backend processed or dropped the frame, ready for next
            if (data.type === 'frame_dropped') return;
            if (data.pose_confidence !== undefined) setConfidence(data.pose_confidence);
            if (data.validation) setValidation(data.validation);

            // Update live PS3 sensor values
            if (data.sensor_data) {
              setSensorReading(data.sensor_data);
              if (data.sensor_data.esp_url && data.sensor_data.esp_url !== espUrl) {
                setEspUrl(data.sensor_data.esp_url);
              }
            }
            if (data.rep_result?.mode_command) {
              setLastModeCommand(data.rep_result.mode_command);
            }

            if (data.rep_count !== undefined && data.rep_count !== repCountRef.current) {
              repCountRef.current = data.rep_count;
              setRepCount(data.rep_count);
              handleRepCompleted(data.rep_count, data.rep_result);
            }

            // Always clear the overlay canvas first to prevent stale skeleton persistence
            const overlay = overlayCanvasRef.current;
            if (overlay) {
              const ctx = overlay.getContext('2d');
              if (ctx) ctx.clearRect(0, 0, overlay.width, overlay.height);
            }

            // Render landmarks and angles whenever landmarks are detected, exactly like validation page
            if (data.landmarks && Object.keys(data.landmarks).length > 0) {
              if (data.angles) setAngles(data.angles);
              // Draw skeleton overlay using received landmarks
              landmarksRef.current = data.landmarks;
              if (overlay) {
                overlay.width = videoRef.current?.videoWidth || overlay.clientWidth;
                overlay.height = videoRef.current?.videoHeight || overlay.clientHeight;
                const ctx = overlay.getContext('2d');
                if (ctx) {
                  drawPoseOverlay(ctx, overlay.width, overlay.height, data.landmarks, data.angles, {
                    showAngles: true,
                    showArcs: true,
                    showCorrectness: true,
                  });
                }
              }
            } else {
              // Reset angles display if no landmarks returned, UNLESS exoskeleton sensor is connected
              const hasExoSensor = data.sensor_data?.connected || (data.angles && (data.angles.left_knee > 0 || data.angles.left_hip > 0));
              if (hasExoSensor && data.angles) {
                setAngles(data.angles);
              } else {
                setAngles({ left_knee: 0, right_knee: 0, left_hip: 0, right_hip: 0, left_ankle: 0, right_ankle: 0 });
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
      if (keepAliveRef.current) clearInterval(keepAliveRef.current);
      // Only send 'end' if handleEndSession didn't already do it
      if (!wsEndedRef.current && wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: 'end' }));
      }
      wsRef.current?.close();
      stopCamera();
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
      addFeedback(`Rep ${repNumber}: waiting for RehabNet analysis.`, 'normal');
      return;
    }

    setLastRep({ flags, confidence, score });

    const newScores = [...scores, score];
    setScores(newScores);
    // -- Two-tier feedback routing ----------------------------------
    const errors = Object.entries(flags).filter(([_, v]) => v === 1);

    // Check for HIGH ALERT flags (injury risk)
    const alertErrors = errors.filter(([k]) => HIGH_ALERT_FLAGS.includes(k as keyof PS2ErrorFlags));
    if (alertErrors.length > 0) {
      const alertMsg = `⚠️ INJURY RISK - ${alertErrors.map(([k]) => ERROR_FLAG_LABELS[k as keyof PS2ErrorFlags].label).join(', ')}. Correct your form immediately!`;
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



  const handleSensorCalibrate = async () => {
    if (calibratingSensor) return;
    setCalibratingSensor(true);
    try {
      const res = await sensorApi.calibrate();
      if (res.success) {
        toast.success('Exoskeleton calibrated successfully!');
      } else {
        toast.error(res.message || 'Calibration failed');
      }
    } catch (err: any) {
      toast.error(`Calibration error: ${err.message}`);
    } finally {
      setCalibratingSensor(false);
    }
  };

  const handleEndSession = async () => {
    if (ending) return;
    setEnding(true);

    // 1. Stop everything immediately — no waiting
    if (sendIntervalRef.current) {
      clearInterval(sendIntervalRef.current);
      sendIntervalRef.current = null;
    }
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    if (keepAliveRef.current) {
      clearInterval(keepAliveRef.current);
      keepAliveRef.current = null;
    }

    // 2. Send 'end' to WS and WAIT for 'end_ack' before closing.
    // The backend's finally block runs _save_live_session_data after the
    // end_ack is sent and the loop breaks. We must wait for the WS to close
    // (meaning the backend finished its finally block) to ensure all data
    // is saved before we call complete_session.
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      try {
        await new Promise<void>((resolve) => {
          const ws = wsRef.current!;
          const timeout = setTimeout(() => {
            // Fallback: if no end_ack after 3 seconds, proceed anyway
            resolve();
          }, 3000);

          // Listen for end_ack or WS close (whichever comes first)
          const origOnMessage = ws.onmessage;
          const origOnClose = ws.onclose;

          ws.onmessage = (event) => {
            try {
              const data = JSON.parse(event.data);
              if (data.type === 'end_ack') {
                clearTimeout(timeout);
                // Wait a brief moment for the backend's finally block to complete
                // after the break from the loop (save to DB happens in finally)
                setTimeout(() => resolve(), 300);
                return;
              }
            } catch { /* ignore parse errors */ }
            // Forward to original handler for other messages
            if (origOnMessage) (origOnMessage as any).call(ws, event);
          };

          ws.onclose = (event) => {
            clearTimeout(timeout);
            resolve();
            if (origOnClose) (origOnClose as any).call(ws, event);
          };

          ws.send(JSON.stringify({ type: 'end' }));
        });
      } catch { /* ignore errors during end sequence */ }
      wsEndedRef.current = true;
      wsRef.current?.close();
    } else {
      wsEndedRef.current = true;
    }

    // 3. Stop camera immediately — this is what the user sees
    stopCamera();

    // 4. Complete session in backend (await so summary page has latest data).
    const sid = sessionId!;
    const finalSeconds = timerSecondsRef.current;
    try {
      await sessionApi.complete(sid, undefined, finalSeconds);
    } catch (err) {
      console.error("Failed to complete session:", err);
    }

    // 5. Navigate to summary
    navigate(`/session/summary/${sid}`);
  };

  const trendColors = {
    improving: 'text-green-600',
    stable: 'text-amber-600',
    declining: 'text-red-600',
  };

  const sessionScore = (() => {
    if (scores.length === 0) return 0;
    const sorted = [...scores].sort((a, b) => b - a);
    const topScores = sorted.slice(0, 10);
    return topScores.reduce((sum, val) => sum + val, 0) / topScores.length;
  })();

  const allValid = validationStatus?.all_valid ?? false;
  const passedCount = validationStatus
    ? Object.entries(validationStatus).filter(([k, v]) => k !== 'all_valid' && k !== 'guidance_message' && v === true).length
    : 0;
  const canStart = allValid || passedCount >= 4;

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
          {/* PS3 Exoskeleton connection */}
          {sensorConnected ? (
            <div className="flex items-center gap-2 text-xs">
              <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full font-bold bg-green-50 text-green-600 border border-green-200`}>
                <Zap className="w-3 h-3 text-green-500 animate-pulse" />
                Exo: {sensorDeviceId || 'ESP32'}
              </span>
              {sensorBattery > 0 && (
                <span className="text-slate-600 flex items-center gap-0.5">
                  🔋 {sensorBattery}%
                </span>
              )}
              {sensorCalibration !== 'uncalibrated' && (
                <span className={`inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded-full text-[10px] font-medium border ${
                  sensorCalibration === 'calibrated' ? 'bg-blue-50 text-blue-600 border-blue-200' : 'bg-amber-50 text-amber-600 border-amber-200 animate-pulse'
                }`}>
                  {sensorCalibration}
                </span>
              )}
            </div>
          ) : (
            <div className="flex items-center gap-1 text-slate-400 text-xs">
              <Heart className="w-3 h-3" />
              <span className="text-slate-400 text-xs">PS3 - Not Connected</span>
            </div>
          )}
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

      {/* HIGH ALERT overlay - shown immediately for injury risk */}
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
        <div ref={cameraStageRef} className="lg:w-[42%] relative bg-slate-900 min-h-[60vh] flex items-center justify-center p-4">
          {!cameraReady && (
            <div className="absolute inset-0 flex items-center justify-center z-10">
              <div className="text-center text-white">
                <Activity className="w-10 h-10 mx-auto mb-2 animate-pulse text-brand" />
                <p className="text-sm">Starting camera...</p>
              </div>
            </div>
          )}
          <div className="relative bg-slate-900 rounded-2xl overflow-hidden aspect-[3/4] w-full max-w-[480px] mx-auto shadow-lg">
            <video
              ref={videoRef}
              className="w-full h-full object-cover"
              muted
              playsInline
            />
            <canvas ref={overlayCanvasRef} className="absolute inset-0 w-full h-full pointer-events-none" style={{ objectFit: 'cover' }} />

            {/* Exercise zone overlay bounding box */}
            <div className="absolute inset-0 pointer-events-none">
              <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[75%] h-[85%]
                border-2 border-dashed rounded-2xl transition-colors duration-500"
                style={{ borderColor: allValid ? '#22C55E' : canStart ? '#14919B' : '#F59E0B' }}
              />
            </div>

          </div>
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
                <p className="text-sm text-slate-400 mt-1">Camera is off. Resume to continue.</p>
                <button onClick={async () => {
                  // Restart the camera first
                  await startCamera();
                  // Set ref directly so the sendInterval reads new value immediately
                  pausedRef.current = false;
                  setPaused(false);
                  // Notify backend to resume processing frames
                  if (wsRef.current?.readyState === WebSocket.OPEN) {
                    wsRef.current.send(JSON.stringify({ type: 'resume' }));
                  }
                }} className="mt-4 btn-primary px-8">
                  Resume
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Right Panel */}
        <div className="lg:w-[58%] bg-white border-l border-slate-200 flex flex-col overflow-y-auto">
          {/* Angle Gauges - only show when confidence is sufficient */}
          {liveAngles && (poseConfidence >= MIN_DISPLAY_CONFIDENCE || sensorConnected) && (
            <div className="p-5 border-b border-slate-100">
              <h3 className="font-display font-bold text-samarth-text mb-4 text-sm uppercase tracking-wide">
                Live Angles
              </h3>
              <div className="space-y-3">
                <AngleGauge label="Left Knee" value={liveAngles.left_knee} angleKey="left_knee" />
                <AngleGauge label="Right Knee" value={liveAngles.right_knee} angleKey="right_knee" />
                <AngleGauge label="Left Hip" value={liveAngles.left_hip} angleKey="left_hip" />
                <AngleGauge label="Right Hip" value={liveAngles.right_hip} angleKey="right_hip" />
              </div>
            </div>
          )}
          {liveAngles && poseConfidence < MIN_DISPLAY_CONFIDENCE && poseConfidence > 0 && (
            <div className="p-5 border-b border-slate-100">
              <p className="text-sm text-slate-400 italic">Low pose confidence. Please step fully into the camera frame.</p>
            </div>
          )}

          {/* PS2 Error Flags from last rep */}
          {lastRep && (
            <div className="p-5 border-b border-slate-100">
              <div className="flex items-center justify-between mb-3">
                <h3 className="font-display font-bold text-samarth-text text-sm uppercase tracking-wide">
                  Last Rep Analysis
                </h3>
                <span className="badge-success">
                  RehabNet
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

          {/* PS3 Exoskeleton Controller Card */}
          <div className="p-5 border-b border-slate-100 bg-slate-50/50">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <Zap className={`w-5 h-5 ${sensorConnected ? 'text-accent animate-pulse' : 'text-slate-400'}`} />
                <h3 className="font-display font-bold text-samarth-text text-sm uppercase tracking-wide">
                  PS3 Exoskeleton Controller
                </h3>
              </div>
              <span className={`inline-flex items-center gap-0.5 px-2 py-0.5 rounded-full text-[10px] font-bold border ${
                sensorConnected
                  ? 'bg-green-50 text-green-600 border-green-200'
                  : 'bg-slate-100 text-slate-500 border-slate-200'
              }`}>
                {sensorConnected ? 'Connected' : 'Offline'}
              </span>
            </div>

            {/* Connection Status / Auto-connect Indicator */}
            {!sensorConnected ? (
              <div className="p-4 bg-white rounded-xl border border-slate-200 shadow-sm flex flex-col items-center justify-center text-center space-y-3">
                <div className="w-12 h-12 bg-slate-50 text-slate-400 rounded-full flex items-center justify-center border border-slate-100">
                  <Activity className="w-6 h-6 animate-pulse" />
                </div>
                <div>
                  <h4 className="text-xs font-bold text-slate-700">Searching for Exoskeleton...</h4>
                  <p className="text-[11px] text-slate-500 mt-1 max-w-[220px]">
                    Auto-connecting to <code className="bg-slate-100 px-1 py-0.5 rounded text-brand font-mono">{espUrl || 'http://10.81.192.229'}</code>.
                  </p>
                  <p className="text-[11px] text-slate-400 mt-1">
                    Running in webcam & AI-only mode until hardware connects.
                  </p>
                </div>
              </div>
            ) : (
              <div className="space-y-4">
                {/* Device Status & Battery */}
                <div className="flex justify-between items-center text-xs p-2 bg-white rounded-lg border border-slate-100">
                  <span className="text-slate-500">Device ID: <strong className="text-slate-700">{sensorDeviceId || 'ESP32'}</strong></span>
                  <span className="text-slate-500">Mode: <strong className="text-brand capitalize">{lastModeCommand ? (lastModeCommand.mode_name.toLowerCase().includes('assist') ? 'Assist' : 'Resist') : 'Standby'}</strong></span>
                  <span className="text-slate-700 font-bold flex items-center gap-1">
                    🔋 {sensorBattery}%
                  </span>
                </div>

                {/* Exoskeleton Motor Status & PWM feedback loop */}
                <div className="space-y-2 p-3 bg-white rounded-xl border border-slate-100">
                  <div className="flex justify-between items-center">
                    <span className="text-xs font-bold text-slate-600">Motor Loop Status</span>
                    <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                      sensorMotorsActive ? 'bg-green-100 text-green-700' : 'bg-slate-100 text-slate-500'
                    }`}>
                      {sensorMotorsActive ? 'Active' : 'Standby'}
                    </span>
                  </div>

                  {/* Last command sent from PS2 */}
                  {lastModeCommand && (
                    <div className="text-[10px] text-slate-500 bg-slate-50 p-1.5 rounded border border-slate-100">
                      Last Loop: <strong className="text-slate-700">{lastModeCommand.mode_name}</strong> @ {lastModeCommand.target_torque} Nm
                    </div>
                  )}

                  {/* Knee motor PWM */}
                  {sensorKneeMotor && (
                    <div className="space-y-1 text-xs">
                      <div className="flex justify-between text-slate-500">
                        <span>Knee Actuator ({sensorKneeMotor.direction})</span>
                        <span className="font-mono">{sensorKneeMotor.pwm} / 255 PWM</span>
                      </div>
                      <div className="h-1 bg-slate-100 rounded-full overflow-hidden">
                        <div className="h-full bg-accent" style={{ width: `${(sensorKneeMotor.pwm / 255) * 100}%` }} />
                      </div>
                    </div>
                  )}

                  {/* Hip motor PWM */}
                  {sensorHipMotor && (
                    <div className="space-y-1 text-xs mt-2">
                      <div className="flex justify-between text-slate-500">
                        <span>Hip Actuator ({sensorHipMotor.direction})</span>
                        <span className="font-mono">{sensorHipMotor.pwm} / 255 PWM</span>
                      </div>
                      <div className="h-1 bg-slate-100 rounded-full overflow-hidden">
                        <div className="h-full bg-indigo-500" style={{ width: `${(sensorHipMotor.pwm / 255) * 100}%` }} />
                      </div>
                    </div>
                  )}
                </div>

                {/* Foot Force & Stance indicator */}
                <div className="p-3 bg-white rounded-xl border border-slate-100 flex items-center justify-between">
                  <div>
                    <span className="text-xs font-bold text-slate-600 block">Foot Pressure</span>
                    <span className="text-xs text-slate-400">{sensorFootForce !== null ? `${sensorFootForce.toFixed(2)} N` : '0.00 N'}</span>
                  </div>
                  <div className={`px-2.5 py-1 rounded-lg text-xs font-bold ${
                    sensorStance ? 'bg-amber-100 text-amber-800 border border-amber-200' : 'bg-slate-50 text-slate-400'
                  }`}>
                    {sensorStance ? '👣 Stance Phase' : 'Swing Phase'}
                  </div>
                </div>

                {/* Action Buttons: Calibrate */}
                <div>
                  <button
                    onClick={handleSensorCalibrate}
                    disabled={calibratingSensor}
                    className="w-full text-xs py-2 font-bold border border-slate-200 rounded-lg hover:bg-slate-100 transition-all flex items-center justify-center gap-1.5 shadow-sm"
                  >
                    {calibratingSensor ? (
                      <>
                        <Activity className="w-3 h-3 animate-spin" />
                        Homing...
                      </>
                    ) : (
                      'Calibrate Exoskeleton'
                    )}
                  </button>
                </div>
              </div>
            )}
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
              onClick={() => {
                const newPaused = !paused;
                // Set ref directly so the frame-sending interval reads new value immediately
                // (React's setPaused is async and would leave a gap where frames keep sending)
                pausedRef.current = newPaused;
                setPaused(newPaused);
                // Notify backend so it stops/resumes processing frames server-side too
                if (wsRef.current?.readyState === WebSocket.OPEN) {
                  wsRef.current.send(JSON.stringify({ type: newPaused ? 'pause' : 'resume' }));
                }
                if (newPaused) {
                  // Stop the camera when pausing
                  stopCamera();
                } else {
                  // Restart camera when resuming
                  startCamera();
                }
              }}
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
