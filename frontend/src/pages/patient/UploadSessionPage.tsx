import React, { useState, useRef, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Upload, FileVideo, CheckCircle, ArrowLeft, Loader2, XCircle, RefreshCw } from 'lucide-react';
import { sessionApi } from '@/api';
import { toast } from 'sonner';
import type { PS2SessionResult, Session } from '@/types';

// Pipeline processing steps
const PIPELINE_STEPS = [
  { key: 'uploading', label: 'Uploading video', icon: Upload },
  { key: 'validating_video', label: 'Checking video conditions', icon: null },
  { key: 'enhancing', label: 'Enhancing video quality', icon: null },
  { key: 'pose_detection', label: 'Detecting body landmarks', icon: null },
  { key: 'storing_results', label: 'Calculating joint angles', icon: null },
  { key: 'exercise_analysis', label: 'Analyzing exercise form', icon: null },
  { key: 'completing', label: 'Finalizing results', icon: null },
  { key: 'done', label: 'Analysis complete', icon: CheckCircle },
];

function getStepIndex(step: string): number {
  const idx = PIPELINE_STEPS.findIndex((s) => s.key === step);
  return idx >= 0 ? idx : 0;
}

export default function UploadSessionPage() {
  const { sessionId } = useParams<{ sessionId: string; exerciseId: string }>();
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [dragActive, setDragActive] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [processingError, setProcessingError] = useState('');
  const [currentStep, setCurrentStep] = useState('uploading');
  const [progressPct, setProgressPct] = useState(0);
  const pollCountRef = useRef(0);
  const [completed, setCompleted] = useState(false);
  const [videoUrl, setVideoUrl] = useState<string | null>(null);
  const [sessionResult, setSessionResult] = useState<Session | null>(null);
  const [ps2Result, setPs2Result] = useState<PS2SessionResult | null>(null);
  const [angleData, setAngleData] = useState<any>(null);

  // Drag handlers
  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const droppedFile = e.dataTransfer.files[0];
      if (droppedFile.type.startsWith('video/')) {
        setFile(droppedFile);
      } else {
        toast.error('Only video files are supported.');
      }
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const selectedFile = e.target.files[0];
      if (selectedFile.type.startsWith('video/')) {
        setFile(selectedFile);
      } else {
        toast.error('Only video files are supported.');
      }
    }
  };

  const handleUpload = async () => {
    if (!file || !sessionId) return;
    setUploading(true);
    setProcessingError('');
    try {
      await sessionApi.uploadVideo(sessionId, file);
      toast.success('Video uploaded successfully! Starting AI analysis...');
      setUploading(false);
      setProcessing(true);
      setCurrentStep('validating_video');
      setProgressPct(12);
      pollCountRef.current = 0;
    } catch (err: any) {
      const message = err?.response?.data?.detail || 'Upload failed. Please try again.';
      toast.error(message);
      setProcessingError(message);
      setUploading(false);
    }
  };

  // Poll processing status using the new endpoint
  useEffect(() => {
    if (!processing || !sessionId) return;
    const interval = setInterval(async () => {
      try {
        const status = await sessionApi.getProcessingStatus(sessionId);
        setCurrentStep(status.step);
        setProgressPct(status.progress_pct);
        const nextPollCount = pollCountRef.current + 1;
        pollCountRef.current = nextPollCount;

        if (status.status === 'completed') {
          clearInterval(interval);
          toast.success('AI biomechanical analysis complete!');
          setCurrentStep('done');
          setProgressPct(100);
          // Fetch session to get annotated video URL
          try {
            const sess = await sessionApi.get(sessionId);
            setSessionResult(sess);
            if (sess.video_url) setVideoUrl(sess.video_url);
            const [angles, ps2] = await Promise.all([
              sessionApi.getAngleData(sessionId),
              sessionApi.getPS2Results(sessionId),
            ]);
            setAngleData(angles);
            setPs2Result(ps2);
          } catch {}
          setProcessing(false);
          setCompleted(true);
        } else if (status.status === 'failed') {
          clearInterval(interval);
          setProcessingError(status.error_message || 'Processing failed. The video may be corrupted or unsupported.');
          setProcessing(false);
        }
      } catch (err) {
        // Don't kill polling on transient network errors - retry
        const nextPollCount = pollCountRef.current + 1;
        pollCountRef.current = nextPollCount;
        if (nextPollCount > 60) {
          // After ~3 minutes of polling, give up
          setProcessingError('Processing is taking too long. Please try again with a shorter video.');
          clearInterval(interval);
          setProcessing(false);
        }
      }
    }, 3000); // Check every 3 seconds

    return () => clearInterval(interval);
  }, [processing, sessionId, navigate]);

  const activeStepIdx = getStepIndex(currentStep);

  return (
    <div className="min-h-screen bg-samarth-bg pb-12">
      {/* Header */}
      <div className="bg-white border-b border-slate-200">
        <div className="max-w-7xl mx-auto px-6 py-5 flex items-center justify-between">
          <div>
            <button
              onClick={() => navigate('/exercises')}
              className="flex items-center gap-2 text-slate-400 hover:text-slate-700 mb-3 transition-colors"
            >
              <ArrowLeft className="w-4 h-4" />
              <span className="text-sm">Exercises</span>
            </button>
            <h1 className="text-2xl font-display font-bold text-samarth-text">Upload Video</h1>
            <p className="text-slate-500 mt-1">Upload a recording of your exercise for batch CV pipeline analysis</p>
          </div>
        </div>
      </div>

      <div className="max-w-3xl mx-auto px-6 pt-10">
        <div className="samarth-card p-8 md:p-10 space-y-8">
          
          {/* Form Step: Ingestion */}
          {!uploading && !processing && !processingError && !completed && (
            <div className="space-y-6">
              <div
                className={`border-2 border-dashed rounded-3xl p-10 flex flex-col items-center justify-center transition-all ${
                  dragActive ? 'border-brand bg-brand-50' : 'border-slate-300 hover:border-slate-400 bg-slate-50'
                }`}
                onClick={() => !file && fileInputRef.current?.click()}
                onDragEnter={handleDrag}
                onDragLeave={handleDrag}
                onDragOver={handleDrag}
                onDrop={handleDrop}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => {
                  if (!file && (e.key === 'Enter' || e.key === ' ')) {
                    e.preventDefault();
                    fileInputRef.current?.click();
                  }
                }}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="video/*"
                  onChange={handleFileChange}
                  className="hidden"
                />
                
                {file ? (
                  <div className="text-center space-y-4">
                    <div className="w-16 h-16 bg-brand-50 text-brand rounded-2xl flex items-center justify-center mx-auto border border-brand-100">
                      <FileVideo className="w-8 h-8" />
                    </div>
                    <div>
                      <p className="font-semibold text-slate-800 max-w-xs truncate mx-auto">{file.name}</p>
                      <p className="text-xs text-slate-400 mt-1">{(file.size / (1024 * 1024)).toFixed(2)} MB</p>
                    </div>
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        setFile(null);
                      }}
                      className="text-xs font-semibold text-red-500 hover:underline"
                    >
                      Remove file
                    </button>
                  </div>
                ) : (
                  <div className="text-center space-y-4">
                    <div className="w-16 h-16 bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400 rounded-2xl flex items-center justify-center mx-auto">
                      <Upload className="w-7 h-7" />
                    </div>
                    <div>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          fileInputRef.current?.click();
                        }}
                        className="text-brand font-bold hover:underline"
                      >
                        Click to upload
                      </button>
                      <span className="text-slate-500"> or drag and drop</span>
                      <p className="text-xs text-slate-400 mt-1.5">MP4, MOV, or AVI video up to 50MB</p>
                    </div>
                  </div>
                )}
              </div>

              {/* Upload Action */}
              {file && (
                <button
                  onClick={handleUpload}
                  className="w-full btn-primary py-4 text-base rounded-2xl"
                  id="upload-submit-btn"
                >
                  Upload & Analyze
                </button>
              )}
            </div>
          )}

          {/* Form Step: Uploading Progress */}
          {uploading && (
            <div className="text-center py-10 space-y-6">
              <Loader2 className="w-12 h-12 text-brand animate-spin mx-auto" />
              <div>
                <h3 className="text-lg font-bold text-slate-800">Uploading Video...</h3>
                <p className="text-slate-500 text-sm mt-1">Please keep this window open while the video uploads to the server.</p>
              </div>
            </div>
          )}

          {/* Form Step: Processing Pipeline - Multi-step stepper */}
          {processing && (
            <div className="py-8 space-y-8">
              {/* Progress bar */}
              <div className="space-y-2">
                <div className="flex justify-between text-xs text-slate-500">
                  <span>Processing...</span>
                  <span className="font-semibold text-brand">{progressPct}%</span>
                </div>
                <div className="h-2.5 bg-slate-100 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-brand to-accent rounded-full transition-all duration-700 ease-out"
                    style={{ width: `${progressPct}%` }}
                  />
                </div>
              </div>

              {/* Pipeline stepper */}
              <div className="space-y-1.5">
                {PIPELINE_STEPS.map((step, idx) => {
                  const isActive = idx === activeStepIdx;
                  const isDone = idx < activeStepIdx || currentStep === 'done';
                  const isPending = idx > activeStepIdx && currentStep !== 'done';

                  return (
                    <div
                      key={step.key}
                      className={`flex items-center gap-3 px-4 py-3 rounded-xl transition-all ${
                        isActive
                          ? 'bg-brand-50 border border-brand-100'
                          : isDone
                          ? 'bg-green-50/50 border border-green-100/50'
                          : 'bg-slate-50/50 border border-transparent'
                      }`}
                    >
                      {isDone ? (
                        <CheckCircle className="w-5 h-5 text-green-500 flex-shrink-0" />
                      ) : isActive ? (
                        <Loader2 className="w-5 h-5 text-brand animate-spin flex-shrink-0" />
                      ) : (
                        <div className="w-5 h-5 rounded-full border-2 border-slate-200 flex-shrink-0" />
                      )}
                      <span
                        className={`text-sm font-medium ${
                          isActive
                            ? 'text-brand font-semibold'
                            : isDone
                            ? 'text-green-700'
                            : isPending
                            ? 'text-slate-400'
                            : 'text-slate-600'
                        }`}
                      >
                        {step.label}
                      </span>
                    </div>
                  );
                })}
              </div>

              <p className="text-xs text-slate-400 text-center">
                This may take 30-90 seconds depending on video length.
              </p>
            </div>
          )}

          {/* Error state */}
          {processingError && (
            <div className="text-center py-10 space-y-6">
              <div className="w-16 h-16 bg-red-100 text-red-500 rounded-2xl flex items-center justify-center mx-auto">
                <XCircle className="w-8 h-8" />
              </div>
              <div className="space-y-2 max-w-sm mx-auto">
                <h3 className="text-lg font-bold text-slate-800">Processing Failed</h3>
                <p className="text-slate-500 text-sm">{processingError}</p>
              </div>
              <button
                onClick={() => {
                  setProcessingError('');
                  setFile(null);
                  setProcessing(false);
                  setCurrentStep('uploading');
                  setProgressPct(0);
                  setSessionResult(null);
                  setPs2Result(null);
                  setAngleData(null);
                  setVideoUrl(null);
                  pollCountRef.current = 0;
                }}
                className="btn-secondary"
              >
                <RefreshCw className="w-4 h-4" />
                Try Again
              </button>
            </div>
          )}

          {/* Completed: Show annotated video + navigate to summary */}
          {completed && (
            <div className="py-8 space-y-6 text-center">
              <div className="w-16 h-16 bg-green-100 text-green-500 rounded-2xl flex items-center justify-center mx-auto">
                <CheckCircle className="w-8 h-8" />
              </div>
              <div className="space-y-2">
                <h3 className="text-lg font-bold text-slate-800">Analysis Complete!</h3>
                <p className="text-slate-500 text-sm">Your exercise has been processed with AI biomechanical analysis.</p>
              </div>

              {videoUrl && (
                <div className="bg-slate-900 rounded-2xl overflow-hidden max-w-xl mx-auto">
                  <video
                    src={videoUrl}
                    controls
                    className="w-full"
                    style={{ maxHeight: '400px' }}
                    playsInline
                  />
                  <p className="text-xs text-slate-400 py-2">Annotated exercise video with pose overlay</p>
                </div>
              )}

              {sessionResult && (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-left">
                  {[
                    ['Reps', sessionResult.total_reps],
                    ['Left ROM', `${sessionResult.avg_left_rom.toFixed(1)} deg`],
                    ['Symmetry', `${sessionResult.symmetry_score.toFixed(1)}%`],
                    ['Score', `${((sessionResult.session_score ?? 0) * 100).toFixed(0)}%`],
                  ].map(([label, value]) => (
                    <div key={label} className="bg-brand-50 border border-brand-100 rounded-xl p-4">
                      <p className="text-xs text-slate-500">{label}</p>
                      <p className="text-lg font-bold text-samarth-text">{value}</p>
                    </div>
                  ))}
                </div>
              )}

              {ps2Result && (
                <div className="text-left bg-slate-50 border border-slate-100 rounded-2xl p-5 space-y-4">
                  <div className="flex items-center justify-between gap-3">
                    <h4 className="font-bold text-samarth-text">Exercise Feedback</h4>
                    <span className="badge-success">RehabNet real analysis</span>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    <div>
                      <p className="text-xs text-slate-500">Analyzed reps</p>
                      <p className="font-bold text-samarth-text">{ps2Result.total_reps_analyzed}</p>
                    </div>
                    <div>
                      <p className="text-xs text-slate-500">Quality trend</p>
                      <p className="font-bold capitalize text-samarth-text">{ps2Result.quality_trend}</p>
                    </div>
                    <div>
                      <p className="text-xs text-slate-500">Pipeline frames</p>
                      <p className="font-bold text-samarth-text">{angleData?.time_series?.frames?.length ?? 0}</p>
                    </div>
                  </div>
                  {ps2Result.dominant_errors.length > 0 && (
                    <div>
                      <p className="text-xs font-semibold text-slate-500 mb-2">Detected issues</p>
                      <div className="flex flex-wrap gap-2">
                        {ps2Result.dominant_errors.map((issue) => (
                          <span key={issue} className="badge-error">{issue.replace(/_/g, ' ')}</span>
                        ))}
                      </div>
                    </div>
                  )}
                  <ul className="space-y-2">
                    {ps2Result.recommendations.map((rec, idx) => (
                      <li key={idx} className="text-sm text-slate-600">{rec}</li>
                    ))}
                  </ul>
                </div>
              )}

              <button
                onClick={() => navigate(`/session/summary/${sessionId}`)}
                className="btn-primary py-3 px-8 text-base"
                id="view-results-btn"
              >
                View Detailed Results
              </button>
            </div>
          )}

          {/* General instructions */}
          <div className="border-t border-slate-100 pt-6">
            <h4 className="font-bold text-slate-700 text-sm mb-2">Video Requirements for best AI accuracy:</h4>
            <ul className="space-y-1.5 text-xs text-slate-500">
              <li>Record in landscape mode with high stability (use a tripod if possible)</li>
              <li>Your whole body must remain visible in the frame throughout the exercise</li>
              <li>Wear contrasting clothing relative to your background to assist segmentation</li>
              <li>Only one person should be visible in the video</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}
