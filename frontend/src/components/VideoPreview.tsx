import { useRef, useEffect, useState } from 'react';
import { Volume2, Video as VideoIcon, RotateCcw } from 'lucide-react';
import type { Segment } from '../lib/types';
import { createVttBlobUrl } from '../lib/srt';
import { formatTimestamp } from '../lib/format';

interface VideoPreviewProps {
  mediaUrl: string;
  filename: string;
  currentSegments?: Segment[];
  activeLang?: string;
  onTimeUpdate?: (currentTime: number) => void;
  seekTime?: number | null;
}

export default function VideoPreview({
  mediaUrl,
  filename,
  currentSegments,
  activeLang,
  onTimeUpdate,
  seekTime,
}: VideoPreviewProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [vttBlobUrl, setVttBlobUrl] = useState<string | null>(null);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [isVideoError, setIsVideoError] = useState(false);

  const isAudioOnly = filename.match(/\.(mp3|wav|m4a|flac|aac|ogg)$/i);

  // Convert segments to WebVTT track
  useEffect(() => {
    if (currentSegments && currentSegments.length > 0) {
      const url = createVttBlobUrl(currentSegments);
      setVttBlobUrl(url);

      return () => {
        URL.revokeObjectURL(url);
      };
    } else {
      setVttBlobUrl(null);
    }
  }, [currentSegments]);

  // Handle external seek requests
  useEffect(() => {
    if (seekTime != null && videoRef.current) {
      videoRef.current.currentTime = seekTime;
      if (videoRef.current.paused) {
        videoRef.current.play().catch(() => {});
      }
    }
  }, [seekTime]);

  const handleTimeUpdate = () => {
    if (videoRef.current) {
      const cur = videoRef.current.currentTime;
      setCurrentTime(cur);
      onTimeUpdate?.(cur);
    }
  };

  const handleLoadedMetadata = () => {
    if (videoRef.current) {
      setDuration(videoRef.current.duration);
    }
  };

  return (
    <div className="bg-slate-900/80 border border-slate-800 rounded-2xl overflow-hidden shadow-xl flex flex-col">
      <div className="p-4 border-b border-slate-800 flex items-center justify-between">
        <div className="flex items-center gap-2">
          {isAudioOnly ? (
            <Volume2 className="w-4 h-4 text-indigo-400" />
          ) : (
            <VideoIcon className="w-4 h-4 text-indigo-400" />
          )}
          <span className="text-sm font-bold text-slate-200 truncate max-w-xs">{filename}</span>
        </div>
        {activeLang && (
          <span className="text-xs px-2.5 py-0.5 rounded-full bg-indigo-500/10 text-indigo-300 border border-indigo-500/20 font-medium">
            Subtitle: {activeLang.toUpperCase()}
          </span>
        )}
      </div>

      <div className="relative bg-black flex items-center justify-center min-h-[260px] sm:min-h-[360px]">
        {isAudioOnly ? (
          <div className="text-center p-8 w-full flex flex-col items-center justify-center">
            <div className="w-20 h-20 rounded-full bg-indigo-600/20 border border-indigo-500/30 flex items-center justify-center text-indigo-400 mb-4 animate-pulse">
              <Volume2 className="w-10 h-10" />
            </div>
            <p className="text-sm font-medium text-slate-300">File Audio</p>
            <p className="text-xs text-slate-500 mt-1">{filename}</p>

            <audio
              ref={videoRef as any}
              src={mediaUrl}
              onTimeUpdate={handleTimeUpdate}
              onLoadedMetadata={handleLoadedMetadata}
              className="mt-6 w-full max-w-md"
              controls
            />
          </div>
        ) : (
          <video
            ref={videoRef}
            src={mediaUrl}
            onTimeUpdate={handleTimeUpdate}
            onLoadedMetadata={handleLoadedMetadata}
            onError={() => setIsVideoError(true)}
            controls
            playsInline
            className="max-h-[520px] max-w-full object-contain mx-auto"
          >
            {vttBlobUrl && (
              <track
                key={vttBlobUrl}
                kind="subtitles"
                label={activeLang || 'Subtitle'}
                src={vttBlobUrl}
                default
              />
            )}
            Browser Anda tidak mendukung tag video HTML5.
          </video>
        )}

        {isVideoError && (
          <div className="absolute inset-0 bg-slate-950/80 flex items-center justify-center p-6 text-center">
            <div className="max-w-md">
              <p className="text-sm font-semibold text-rose-400">Media tidak dapat diputar langsung</p>
              <p className="text-xs text-slate-400 mt-1">
                Format container atau codec mungkin tidak didukung peramban. Anda tetap bisa mengunduh subtitle SRT.
              </p>
            </div>
          </div>
        )}
      </div>

      <div className="p-3 bg-slate-950/40 border-t border-slate-800 flex items-center justify-between text-xs text-slate-400">
        <span className="font-mono">
          {formatTimestamp(currentTime)} / {formatTimestamp(duration)}
        </span>
        <button
          onClick={() => {
            if (videoRef.current) videoRef.current.currentTime = 0;
          }}
          className="flex items-center gap-1 hover:text-slate-200 transition-colors"
        >
          <RotateCcw className="w-3.5 h-3.5" />
          <span>Ulangi dari awal</span>
        </button>
      </div>
    </div>
  );
}
