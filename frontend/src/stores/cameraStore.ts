/**
 * Shared Camera Store
 * ====================
 * Persists the camera MediaStream across page navigations so that
 * CameraValidationPage → LiveSessionPage transition doesn't need
 * to re-acquire the camera or re-detect joints from scratch.
 *
 * The stream is stored outside React component lifecycle — it survives
 * route changes and is only stopped when explicitly released.
 */

let _sharedStream: MediaStream | null = null;

/**
 * Acquire or return the existing shared camera stream.
 * If a stream is already active (tracks not ended), reuse it.
 * Otherwise acquire a new one from getUserMedia.
 */
export async function getSharedCameraStream(): Promise<MediaStream> {
  // Reuse existing stream if all video tracks are still live
  if (_sharedStream) {
    const videoTracks = _sharedStream.getVideoTracks();
    const allLive = videoTracks.length > 0 && videoTracks.every(t => t.readyState === 'live');
    if (allLive) return _sharedStream;
  }

  // Acquire new stream
  try {
    _sharedStream = await navigator.mediaDevices.getUserMedia({
      video: { width: { ideal: 720 }, height: { ideal: 1280 }, facingMode: 'user' },
      audio: false,
    });
  } catch {
    // Fallback to minimal constraints
    _sharedStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
  }

  return _sharedStream;
}

/**
 * Get the current shared stream without acquiring a new one.
 * Returns null if no stream exists or all tracks have ended.
 */
export function peekSharedCameraStream(): MediaStream | null {
  if (!_sharedStream) return null;
  const videoTracks = _sharedStream.getVideoTracks();
  const allLive = videoTracks.length > 0 && videoTracks.every(t => t.readyState === 'live');
  return allLive ? _sharedStream : null;
}

/**
 * Stop all tracks and release the shared camera stream.
 * Call this when completely done with the camera (e.g., session ends).
 */
export function releaseSharedCameraStream(): void {
  if (_sharedStream) {
    _sharedStream.getTracks().forEach(t => t.stop());
    _sharedStream = null;
  }
}
