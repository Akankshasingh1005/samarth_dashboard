import { useEffect, useRef, useState, useCallback } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  CheckCircle2, XCircle, AlertCircle, CameraOff,
  ChevronRight, Loader2, Info, SkipForward
} from 'lucide-react';
import { useSessionStore } from '@/stores/sessionStore';
import { useAuthStore } from '@/stores/authStore';
import { drawPoseOverlay } from '@/api/poseOverlay';
import { getSharedCameraStream } from '@/stores/cameraStore';
import type { ValidationStatus } from '@/types';
import { toast } from 'sonner';

const VALIDATION_LABELS: Record<keyof Omit<ValidationStatus, 'all_valid' | 'guidance_message'>, string> = {
  left_hip_visible: 'Left Hip Visible',
  right_hip_visible: 'Right Hip Visible',
  left_knee_visible: 'Left Knee Visible',
  right_knee_visible: 'Right Knee Visible',
  left_ankle_visible: 'Left Ankle Visible',
  right_ankle_visible: 'Right Ankle Visible',
  full_lower_body_visible: 'Full Lower Body Visible',
  inside_zone: 'Inside Exercise Zone',
  adequate_lighting: 'Adequate Lighting',
  camera_stable: 'Camera Stable',
};

// Minimum checks to allow starting (relaxed)
const MIN_CHECKS_TO_START = 4;

export default function CameraValidationPage() {
  const { exerciseId, sessionId } = useParams<{ exerciseId: string; sessionId: string }>();
  const navigate = useNavigate();
  const { accessToken } = useAuthStore();
  const { setValidation, setAngles, setWsConnected, validationStatus } = useSessionStore();

  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const overlayCanvasRef = useRef<HTMLCanvasElement>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const sendIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const readyToSendRef = useRef(true);

  const [cameraError, setCameraError] = useState('');
  const [wsStatus, setWsStatus] = useState<'connecting' | 'connected' | 'error'>('connecting');
  const [frameCount, setFrameCount] = useState(0);
  const [cameraLoading, setCameraLoading] = useState(true);

  const allValid = validationStatus?.all_valid ?? false;
  const checks = validationStatus
    ? Object.entries(VALIDATION_LABELS).map(([key, label]) => ({
        key,
        label,
        valid: validationStatus[key as keyof ValidationStatus] as boolean,
      }))
    : Object.entries(VALIDATION_LABELS).map(([key, label]) => ({ key, label, valid: false }));

  const passedCount = checks.filter(c => c.valid).length;
  const canStart = allValid || passedCount >= MIN_CHECKS_TO_START;

  const connectCamera = useCallback(async () => {
    setCameraLoading(true);
    try {
      // Use shared camera store — stream persists across page navigations
      const stream = await getSharedCameraStream();
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
      setCameraLoading(false);
    } catch {
      setCameraError('Camera access denied. Please allow camera permissions and reload the page.');
      setCameraLoading(false);
    }
  }, []);

  const connectWebSocket = useCallback(() => {
    if (!accessToken) return;
    const ws = new WebSocket(`ws://localhost:8000/ws/camera/${accessToken}`);
    wsRef.current = ws;

    ws.onopen = () => {
      setWsStatus('connected');
      setWsConnected(true);

      // Send frames at ~5fps, throttled by response
      sendIntervalRef.current = setInterval(() => {
        if (!videoRef.current || !canvasRef.current || ws.readyState !== WebSocket.OPEN || !readyToSendRef.current) return;
        readyToSendRef.current = false;
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
            setFrameCount((n) => n + 1);
          } else {
            readyToSendRef.current = true;
          }
        }, 'image/jpeg', 0.6);
      }, 200); // 5fps
    };

    ws.onmessage = (event) => {
      readyToSendRef.current = true;
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'validation') {
          setValidation(data.validation);
          if (data.angles) setAngles(data.angles);
          // Draw skeleton overlay using landmarks from validation response
          if (data.landmarks) {
            const overlay = overlayCanvasRef.current;
            const video = videoRef.current;
            if (overlay && video) {
              overlay.width = video.videoWidth || video.clientWidth;
              overlay.height = video.videoHeight || video.clientHeight;
              const ctx = overlay.getContext('2d');
              if (ctx) {
                drawPoseOverlay(ctx, overlay.width, overlay.height, data.landmarks, null, {
                  showAngles: false,
                });
              }
            }
          }
        }
      } catch {}
    };

    ws.onerror = () => {
      setWsStatus('error');
      setWsConnected(false);
    };

    ws.onclose = () => {
      setWsConnected(false);
      if (sendIntervalRef.current) clearInterval(sendIntervalRef.current);
    };
  }, [accessToken, setValidation, setAngles, setWsConnected]);

  useEffect(() => {
    connectCamera().then(connectWebSocket);
    return () => {
      if (sendIntervalRef.current) clearInterval(sendIntervalRef.current);
      wsRef.current?.send(JSON.stringify({ type: 'stop' }));
      wsRef.current?.close();
      // NOTE: Do NOT stop the camera stream here — the LiveSessionPage will reuse it
      // so that detected joints carry forward seamlessly without re-detection.
    };
  }, [connectCamera, connectWebSocket]);

  const handleStart = () => {
    if (!canStart) {
      toast.error('Please pass at least 4 positioning checks before starting.');
      return;
    }
    if (!allValid) {
      toast.warning('Some checks are not met. Session quality may be reduced.', {
        duration: 3000,
      });
    }
    wsRef.current?.send(JSON.stringify({ type: 'stop' }));
    navigate(`/session/live/${sessionId}/${exerciseId}`);
  };

  const handleSkipValidation = () => {
    toast.warning('Skipping validation. Camera positioning may affect analysis accuracy.', {
      duration: 4000,
    });
    wsRef.current?.send(JSON.stringify({ type: 'stop' }));
    navigate(`/session/live/${sessionId}/${exerciseId}`);
  };

  return (
    <div className="min-h-screen bg-samarth-bg">
      {/* Header */}
      <div className="bg-white border-b border-slate-200 px-6 py-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div>
            <h1 className="text-xl font-display font-bold text-samarth-text">Camera Setup</h1>
            <p className="text-sm text-slate-500">Position yourself correctly before starting</p>
          </div>
          <div className="flex items-center gap-2 text-sm">
            <div className={`w-2 h-2 rounded-full ${wsStatus === 'connected' ? 'bg-green-500 animate-pulse' : wsStatus === 'error' ? 'bg-red-500' : 'bg-amber-400 animate-pulse'}`} />
            <span className="text-slate-500">
              {wsStatus === 'connected' ? `Live · ${frameCount} frames` : wsStatus === 'error' ? 'Connection error' : 'Connecting...'}
            </span>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-8">
          {/* Camera Feed (left, 60%) */}
          <div className="lg:col-span-3 space-y-1">
            <div className="relative bg-slate-900 rounded-2xl overflow-hidden aspect-[3/4] w-full max-w-[480px] mx-auto shadow-lg">
              {cameraError ? (
                <div className="absolute inset-0 flex flex-col items-center justify-center text-white gap-4">
                  <CameraOff className="w-16 h-16 text-red-400" />
                  <p className="text-center px-8 text-red-300">{cameraError}</p>
                  <button
                    onClick={() => { setCameraError(''); connectCamera(); }}
                    className="btn-primary mt-2"
                  >
                    Retry Camera
                  </button>
                </div>
              ) : (
                <>
                  {cameraLoading && (
                    <div className="absolute inset-0 flex items-center justify-center z-10">
                      <Loader2 className="w-10 h-10 text-brand animate-spin" />
                    </div>
                  )}
                  <video ref={videoRef} className="w-full h-full object-cover" muted playsInline />
                  <canvas ref={overlayCanvasRef} className="absolute inset-0 w-full h-full pointer-events-none" style={{ objectFit: 'cover' }} />
                  <canvas ref={canvasRef} className="hidden" />

                  {/* Exercise zone bounding box overlay */}
                  <div className="absolute inset-0 pointer-events-none">
                    <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[75%] h-[85%]
                      border-2 border-dashed rounded-2xl transition-colors duration-500"
                      style={{ borderColor: allValid ? '#22C55E' : canStart ? '#14919B' : '#F59E0B' }}
                    />
                  </div>

                  {/* Guidance message overlay */}
                  {validationStatus?.guidance_message && (
                    <div className="absolute bottom-4 left-1/2 -translate-x-1/2 z-10 w-[90%] text-center">
                      <div className={`px-4 py-2 rounded-xl text-xs font-semibold shadow-lg backdrop-blur-sm
                        ${allValid ? 'bg-green-500/90 text-white' : 'bg-black/70 text-white'}`}>
                        {validationStatus.guidance_message}
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>

            {/* Instructions */}
            <div className="samarth-card p-4 flex items-start gap-3">
              <Info className="w-5 h-5 text-brand flex-shrink-0 mt-0.5" />
              <div className="text-sm text-slate-600">
                <p className="font-semibold text-slate-800 mb-1">Positioning Tips</p>
                <ul className="space-y-1 text-slate-500">
                  <li>Stand 1.5–2 metres from the camera</li>
                  <li>Ensure your full body (head to feet) is visible</li>
                  <li>Use a well-lit room with light facing you</li>
                  <li>Place your phone/camera at hip height</li>
                </ul>
              </div>
            </div>
          </div>

          {/* Validation Checklist (right, 40%) */}
          <div className="lg:col-span-2 space-y-4">
            <div className="samarth-card p-5">
              <div className="flex items-center justify-between mb-5">
                <h2 className="font-display font-bold text-samarth-text">Validation Checklist</h2>
                <span className={`${allValid ? 'badge-success' : canStart ? 'badge-brand' : 'badge-warning'}`}>
                  {passedCount}/{checks.length} passed
                </span>
              </div>

              <div className="space-y-1">
                {checks.map((check) => (
                  <div
                    key={check.key}
                    className={`validation-item ${check.valid ? 'valid' : wsStatus === 'connected' ? 'invalid' : 'pending'}`}
                  >
                    {check.valid ? (
                      <CheckCircle2 className="w-5 h-5 text-green-600 flex-shrink-0" />
                    ) : wsStatus === 'connected' ? (
                      <XCircle className="w-5 h-5 text-red-400 flex-shrink-0" />
                    ) : (
                      <Loader2 className="w-5 h-5 text-slate-400 animate-spin flex-shrink-0" />
                    )}
                    <span className={`text-sm font-medium ${check.valid ? 'text-green-800' : 'text-slate-600'}`}>
                      {check.label}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {/* Start Button */}
            <button
              onClick={handleStart}
              disabled={!canStart}
              id="start-session-btn"
              className={`w-full py-4 rounded-2xl text-base font-bold flex items-center justify-center gap-2 transition-all duration-300
                ${allValid
                  ? 'bg-brand text-white hover:-translate-y-0.5 active:translate-y-0 shadow-[0_4px_14px_0_rgba(13,115,119,0.3)]'
                  : canStart
                  ? 'bg-brand/80 text-white hover:-translate-y-0.5 active:translate-y-0'
                  : 'bg-slate-100 text-slate-400 cursor-not-allowed'
                }`}
            >
              {allValid ? (
                <>
                  <CheckCircle2 className="w-5 h-5" />
                  Start Session
                  <ChevronRight className="w-5 h-5" />
                </>
              ) : canStart ? (
                <>
                  <AlertCircle className="w-5 h-5" />
                  Start Anyway ({passedCount}/{checks.length} checks)
                  <ChevronRight className="w-5 h-5" />
                </>
              ) : (
                <>
                  <AlertCircle className="w-5 h-5" />
                  Pass {MIN_CHECKS_TO_START}+ Checks to Start
                </>
              )}
            </button>

            {/* Skip validation button */}
            <button
              onClick={handleSkipValidation}
              className="w-full py-2.5 rounded-xl text-sm font-medium text-slate-500 hover:text-slate-700 hover:bg-slate-100 flex items-center justify-center gap-2 transition-all"
              id="skip-validation-btn"
            >
              <SkipForward className="w-4 h-4" />
              Skip Validation & Start
            </button>

            {allValid && (
              <p className="text-center text-sm text-green-600 font-medium animate-fade-in">
              All checks passed! You're ready to begin.
            </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
