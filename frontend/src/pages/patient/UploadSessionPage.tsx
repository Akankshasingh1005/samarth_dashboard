import React, { useState, useRef, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Upload, FileVideo, CheckCircle, AlertTriangle, ArrowLeft, Loader2 } from 'lucide-react';
import { sessionApi } from '@/api';
import { toast } from 'sonner';

export default function UploadSessionPage() {
  const { sessionId } = useParams<{ sessionId: string; exerciseId: string }>();
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [dragActive, setDragActive] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [processingError, setProcessingError] = useState('');

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
      setFile(e.target.files[0]);
    }
  };

  const handleUpload = async () => {
    if (!file || !sessionId) return;
    setUploading(true);
    try {
      await sessionApi.uploadVideo(sessionId, file);
      toast.success('Video uploaded successfully! Starting AI analysis...');
      setUploading(false);
      setProcessing(true);
    } catch (err: any) {
      toast.error('Upload failed. Please try again.');
      setUploading(false);
    }
  };

  // Poll processing state
  useEffect(() => {
    if (!processing || !sessionId) return;
    const interval = setInterval(async () => {
      try {
        const session = await sessionApi.get(sessionId);
        if (session.ps1_processed && session.ps2_processed) {
          clearInterval(interval);
          // Mark session complete in backend just in case
          await sessionApi.complete(sessionId).catch(() => {});
          toast.success('AI biomechanical analysis complete!');
          navigate(`/session/summary/${sessionId}`);
        }
      } catch (err) {
        setProcessingError('Unable to verify processing status.');
        clearInterval(interval);
      }
    }, 3000); // Check every 3 seconds

    return () => clearInterval(interval);
  }, [processing, sessionId, navigate]);

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
          {!uploading && !processing && (
            <div className="space-y-6">
              <div
                className={`border-2 border-dashed rounded-3xl p-10 flex flex-col items-center justify-center transition-all ${
                  dragActive ? 'border-brand bg-brand-50' : 'border-slate-300 hover:border-slate-400 bg-slate-50'
                }`}
                onDragEnter={handleDrag}
                onDragLeave={handleDrag}
                onDragOver={handleDrag}
                onDrop={handleDrop}
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
                      onClick={() => setFile(null)}
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
                        onClick={() => fileInputRef.current?.click()}
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

          {/* Form Step: Processing Engine */}
          {processing && (
            <div className="text-center py-10 space-y-6">
              <div className="relative w-16 h-16 mx-auto">
                <Loader2 className="w-16 h-16 text-accent animate-spin" />
                <div className="absolute inset-0 flex items-center justify-center font-display font-black text-xs text-accent">
                  AI
                </div>
              </div>
              <div className="space-y-2 max-w-sm mx-auto">
                <h3 className="text-lg font-bold text-slate-800">KinemaFlow analysis in progress...</h3>
                <p className="text-slate-500 text-sm">
                  Our computer vision pipeline is segmenting the background, identifying joint landmarks, and calculating kinematics.
                </p>
                <div className="pt-4 flex flex-col gap-2">
                  <div className="flex items-center gap-2 text-xs font-semibold text-green-600 bg-green-50 px-3 py-1.5 rounded-lg border border-green-100 justify-center">
                    <CheckCircle className="w-4 h-4" />
                    <span>Video saved successfully</span>
                  </div>
                  <div className="flex items-center gap-2 text-xs font-semibold text-slate-600 bg-slate-50 px-3 py-1.5 rounded-lg border border-slate-100 justify-center">
                    <Loader2 className="w-3.5 h-3.5 animate-spin text-slate-400" />
                    <span>Extracting joints & angles</span>
                  </div>
                </div>
              </div>

              {processingError && (
                <div className="p-4 bg-red-50 border border-red-200 rounded-xl text-red-700 text-sm flex items-start gap-2.5 text-left max-w-md mx-auto">
                  <AlertTriangle className="w-5 h-5 flex-shrink-0 mt-0.5" />
                  <div>
                    <p className="font-semibold">Processing error</p>
                    <p className="text-xs mt-0.5 opacity-90">{processingError}</p>
                  </div>
                </div>
              )}
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
