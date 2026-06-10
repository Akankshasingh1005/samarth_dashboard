import { useEffect, useRef, useState, useCallback } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  CheckCircle2, XCircle, AlertCircle, CameraOff,
  ChevronRight, Loader2, Info
} from 'lucide-react';
import { useSessionStore } from '@/stores/sessionStore';
import { useAuthStore } from '@/stores/authStore';
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

export default function CameraValidationPage() {
  const { exerciseId, sessionId } = useParams<{ exerciseId: string; sessionId: string }>();
  const navigate = useNavigate();
  const { accessToken } = useAuthStore();
  const { setValidation, setAngles, setWsConnected, validationStatus } = useSessionStore();

  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const sendIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const [cameraError, setCameraError] = useState('');
  const [wsStatus, setWsStatus] = useState<'connecting' | 'connected' | 'error'>('connecting');
  const [frameCount, setFrameCount] = useState(0);

  const allValid = validationStatus?.all_valid ?? false;
  const checks = validationStatus
    ? Object.entries(VALIDATION_LABELS).map(([key, label]) => ({
        key,
        label,
        valid: validationStatus[key as keyof ValidationStatus] as boolean,
      }))
    : Object.entries(VALIDATION_LABELS).map(([key, label]) => ({ key, label, valid: false }));

  const connectCamera = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: 640, height: 480, facingMode: 'user' },
        audio: false,
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
    } catch (err) {
      setCameraError('Camera access denied. Please allow camera access and reload.');
    }
  }, []);

  const connectWebSocket = useCallback(() => {
    if (!accessToken) return;
    const ws = new WebSocket(`ws://localhost:8000/ws/camera/${accessToken}`);
    wsRef.current = ws;

    ws.onopen = () => {
      setWsStatus('connected');
      setWsConnected(true);

      // Send frames at ~5fps
      sendIntervalRef.current = setInterval(() => {
        if (!videoRef.current || !canvasRef.current || ws.readyState !== WebSocket.OPEN) return;
        const canvas = canvasRef.current;
        const ctx = canvas.getContext('2d');
        if (!ctx) return;
        canvas.width = 640;
        canvas.height = 480;
        ctx.drawImage(videoRef.current, 0, 0, 640, 480);
        canvas.toBlob((blob) => {
          if (blob && ws.readyState === WebSocket.OPEN) {
            blob.arrayBuffer().then((buf) => ws.send(buf));
            setFrameCount((n) => n + 1);
          }
        }, 'image/jpeg', 0.7);
      }, 200); // 5fps
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'validation') {
          setValidation(data.validation);
          if (data.angles) setAngles(data.angles);
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
      streamRef.current?.getTracks().forEach((t) => t.stop());
    };
  }, [connectCamera, connectWebSocket]);

  const handleStart = () => {
    if (!allValid) {
      toast.error('Please complete all positioning checks before starting.');
      return;
    }
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
          <div className="lg:col-span-3 space-y-4">
            <div className="relative bg-slate-900 rounded-2xl overflow-hidden aspect-video shadow-lg">
              {cameraError ? (
                <div className="absolute inset-0 flex flex-col items-center justify-center text-white gap-4">
                  <CameraOff className="w-16 h-16 text-red-400" />
                  <p className="text-center px-8 text-red-300">{cameraError}</p>
                </div>
              ) : (
                <>
                  <video ref={videoRef} className="w-full h-full object-cover" muted playsInline />
                  <canvas ref={canvasRef} className="hidden" />
                  {/* Exercise zone overlay */}
                  <div className="absolute inset-0 pointer-events-none">
                    <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-2/5 h-4/5
                      border-2 border-dashed rounded-2xl transition-colors duration-500
                      flex items-start justify-center pt-3"
                      style={{ borderColor: allValid ? '#22C55E' : '#F59E0B' }}>
                      <span className="text-xs font-semibold px-2 py-1 rounded-lg"
                        style={{ backgroundColor: allValid ? 'rgba(34,197,94,0.15)' : 'rgba(245,158,11,0.15)',
                                 color: allValid ? '#22C55E' : '#F59E0B' }}>
                        Exercise Zone
                      </span>
                    </div>

                    {/* Skeleton dots from landmark data */}
                    {validationStatus?.left_knee_visible && (
                      <div className="absolute" style={{ left: '40%', top: '60%' }}>
                        <div className="w-3 h-3 bg-green-400 rounded-full opacity-80" />
                      </div>
                    )}
                  </div>

                  {/* Guidance message overlay */}
                  {validationStatus?.guidance_message && (
                    <div className="absolute bottom-4 left-1/2 -translate-x-1/2 z-10">
                      <div className={`px-5 py-2.5 rounded-xl text-sm font-semibold shadow-lg backdrop-blur-sm
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
                <span className={`badge-${allValid ? 'success' : 'warning'}`}>
                  {checks.filter(c => c.valid).length}/{checks.length} passed
                </span>
              </div>

              <div className="space-y-2">
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
              disabled={!allValid}
              id="start-session-btn"
              className={`w-full py-4 rounded-2xl text-base font-bold flex items-center justify-center gap-2 transition-all duration-300
                ${allValid
                  ? 'bg-brand text-white hover:-translate-y-0.5 active:translate-y-0'
                  : 'bg-slate-100 text-slate-400 cursor-not-allowed'
                }`}
            >
              {allValid ? (
                <>
                  <CheckCircle2 className="w-5 h-5" />
                  Start Session
                  <ChevronRight className="w-5 h-5" />
                </>
              ) : (
                <>
                  <AlertCircle className="w-5 h-5" />
                  Complete All Checks First
                </>
              )}
            </button>

            <button
              onClick={() => {
                wsRef.current?.send(JSON.stringify({ type: 'stop' }));
                navigate(`/session/live/${sessionId}/${exerciseId}`);
              }}
              className="w-full mt-2 py-3 rounded-2xl text-sm font-semibold text-slate-600 hover:text-slate-800 bg-slate-100 hover:bg-slate-200 border border-slate-200 transition-all duration-200 flex items-center justify-center gap-2"
              id="bypass-validation-btn"
            >
              Demo Mode: Skip Positioning Check
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
