import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { ArrowLeft, Languages, Sparkles, Loader2, RefreshCw } from 'lucide-react';
import { api } from '../lib/api';
import { useJob } from '../hooks/useJob';
import ProgressTimeline from '../components/ProgressTimeline';
import VideoPreview from '../components/VideoPreview';
import SegmentEditor from '../components/SegmentEditor';
import DownloadMenu from '../components/DownloadMenu';
import { getLanguageName, TARGET_LANGUAGES } from '../lib/languages';
import type { Segment } from '../lib/types';

export default function JobPage() {
  const { id } = useParams<{ id: string }>();
  const queryClient = useQueryClient();
  const { job, isLoading: jobLoading, refetch: refetchJob } = useJob(id);

  const [activeLang, setActiveLang] = useState<string>('');
  const [seekTime, setSeekTime] = useState<number | null>(null);
  const [videoCurrentTime, setVideoCurrentTime] = useState<number>(0);
  const [translatingTarget, setTranslatingTarget] = useState<string | null>(null);

  // Set default active language once available_langs is populated
  useEffect(() => {
    if (job?.available_langs && job.available_langs.length > 0) {
      if (!activeLang || !job.available_langs.includes(activeLang)) {
        setActiveLang(job.available_langs[0]);
      }
    }
  }, [job?.available_langs, activeLang]);

  // Fetch segments for active language
  const {
    data: subData,
    isLoading: subLoading,
  } = useQuery({
    queryKey: ['subtitles', id, activeLang],
    queryFn: () => (id && activeLang ? api.getSubtitles(id, activeLang) : Promise.reject('No lang')),
    enabled: !!id && !!activeLang && (job?.available_langs?.includes(activeLang) ?? false),
  });

  // Save subtitle edits mutation
  const saveSubtitlesMutation = useMutation({
    mutationFn: (updatedSegments: Segment[]) => {
      if (!id || !activeLang) throw new Error('Missing job or lang');
      return api.updateSubtitles(id, activeLang, updatedSegments);
    },
    onSuccess: (data) => {
      queryClient.setQueryData(['subtitles', id, activeLang], data);
    },
  });

  // Additional translation trigger
  const handleTranslateExtra = async (targetLang: string) => {
    if (!id) return;
    try {
      setTranslatingTarget(targetLang);
      await api.translateJob(id, [targetLang]);
      refetchJob();
    } catch (err: any) {
      alert(`Gagal memulai terjemahan: ${err.message || err}`);
    } finally {
      setTranslatingTarget(null);
    }
  };

  if (jobLoading) {
    return (
      <div className="py-20 text-center text-slate-400">
        <Loader2 className="w-8 h-8 animate-spin mx-auto text-indigo-400 mb-3" />
        <p className="text-sm">Memuat detail pekerjaan...</p>
      </div>
    );
  }

  if (!job) {
    return (
      <div className="py-20 text-center text-slate-400">
        <p className="text-base font-semibold text-rose-400">Pekerjaan tidak ditemukan</p>
        <Link to="/" className="mt-4 inline-block text-xs text-indigo-400 hover:underline">
          &larr; Kembali ke Beranda
        </Link>
      </div>
    );
  }

  const isCompleted = job.status === 'done';
  const hasSubtitles = job.available_langs && job.available_langs.length > 0;
  const untranslatedTargets = TARGET_LANGUAGES.filter(
    (t) =>
      !job.available_langs.includes(t.code) &&
      t.code !== (job.source_lang_detected || job.source_lang_requested)
  );

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Top Bar Navigation */}
      <div className="flex items-center justify-between gap-4">
        <Link
          to="/"
          className="inline-flex items-center gap-2 text-xs font-semibold text-slate-400 hover:text-slate-200 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Kembali ke Beranda</span>
        </Link>

        <button
          onClick={() => refetchJob()}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition-colors"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          <span>Segarkan</span>
        </button>
      </div>

      {/* Progress Timeline */}
      <ProgressTimeline job={job} />

      {/* Language Tabs & Translation Buttons */}
      {hasSubtitles && (
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-4 rounded-2xl bg-slate-900/60 border border-slate-800">
          {/* Language Selector Tabs */}
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs font-bold text-slate-400 mr-1 flex items-center gap-1">
              <Languages className="w-3.5 h-3.5" />
              <span>Bahasa:</span>
            </span>
            {job.available_langs.map((lang) => {
              const active = activeLang === lang;
              const isSource =
                lang === (job.source_lang_detected || job.source_lang_requested);

              return (
                <button
                  key={lang}
                  onClick={() => setActiveLang(lang)}
                  className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition-all flex items-center gap-1.5 border ${
                    active
                      ? 'bg-indigo-600 text-white border-indigo-500 shadow-md shadow-indigo-600/30'
                      : 'bg-slate-950/60 text-slate-300 border-slate-800 hover:border-slate-700 hover:bg-slate-950'
                  }`}
                >
                  <span>{getLanguageName(lang)}</span>
                  {isSource && (
                    <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-slate-800 text-slate-400 font-normal">
                      Sumber
                    </span>
                  )}
                </button>
              );
            })}
          </div>

          {/* Translate Extra Button */}
          {isCompleted && untranslatedTargets.length > 0 && (
            <div className="flex items-center gap-2 flex-wrap">
              {untranslatedTargets.map((target) => (
                <button
                  key={target.code}
                  onClick={() => handleTranslateExtra(target.code)}
                  disabled={translatingTarget === target.code}
                  className="px-3 py-1.5 rounded-xl text-xs font-semibold bg-purple-600/20 text-purple-200 border border-purple-500/30 hover:bg-purple-600/30 transition-all flex items-center gap-1.5"
                >
                  <Sparkles className="w-3.5 h-3.5" />
                  <span>
                    {translatingTarget === target.code
                      ? 'Menerjemahkan...'
                      : `Terjemahkan ke ${target.label}`}
                  </span>
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Main Workspace (Preview + Editor) */}
      {hasSubtitles && activeLang && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Left Column: Video / Audio Player Preview */}
          <div className="lg:col-span-5 space-y-6">
            <VideoPreview
              mediaUrl={api.getMediaUrl(job.id)}
              filename={job.filename}
              currentSegments={subData?.segments}
              activeLang={activeLang}
              seekTime={seekTime}
              onTimeUpdate={(t) => setVideoCurrentTime(t)}
            />

            {/* Download Options */}
            <DownloadMenu
              job={job}
              activeLang={activeLang}
              onBurnRequested={() => refetchJob()}
            />
          </div>

          {/* Right Column: Segment Table Editor */}
          <div className="lg:col-span-7">
            {subLoading ? (
              <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-16 text-center text-slate-400">
                <Loader2 className="w-6 h-6 animate-spin mx-auto text-indigo-400 mb-2" />
                <p className="text-xs">Memuat cue subtitle {activeLang.toUpperCase()}...</p>
              </div>
            ) : (
              <SegmentEditor
                segments={subData?.segments || []}
                lang={activeLang}
                currentTime={videoCurrentTime}
                onSeek={(time) => setSeekTime(time)}
                onSave={async (updated) => {
                  await saveSubtitlesMutation.mutateAsync(updated);
                }}
                isSaving={saveSubtitlesMutation.isPending}
              />
            )}
          </div>
        </div>
      )}
    </div>
  );
}
