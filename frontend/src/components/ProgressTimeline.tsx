import { Clock, AlertCircle, FileAudio, Sparkles, MessageSquareQuote, Check } from 'lucide-react';
import type { Job } from '../lib/types';

interface ProgressTimelineProps {
  job: Job;
}

export default function ProgressTimeline({ job }: ProgressTimelineProps) {
  const stages = [
    {
      key: 'extracting_audio',
      label: 'Ekstraksi Audio',
      desc: 'Konversi media ke WAV 16kHz mono',
      icon: FileAudio,
    },
    {
      key: 'transcribing',
      label: 'Transkripsi Speech-to-Text',
      desc: `Whisper (${job.model_size}) mendeteksi ujaran`,
      icon: MessageSquareQuote,
    },
    {
      key: 'segmenting',
      label: 'Segmentasi Subtitle',
      desc: 'Pengaturan batas waktu dan panjang baris cue',
      icon: Clock,
    },
    {
      key: 'translating',
      label: 'Terjemahan AI',
      desc:
        job.target_langs.length > 0
          ? `Menerjemahkan ke ${job.target_langs.join(', ').toUpperCase()}`
          : 'Dilewati (tanpa target terjemahan)',
      icon: Sparkles,
      skipped: job.target_langs.length === 0,
    },
  ];

  const getStageStatus = (stageKey: string, isSkipped?: boolean) => {
    if (isSkipped) return 'skipped';
    if (job.status === 'failed') return 'failed';
    if (job.status === 'cancelled') return 'cancelled';
    if (job.status === 'done') return 'done';

    const stageOrder = ['extracting_audio', 'transcribing', 'segmenting', 'translating'];
    const currentIndex = stageOrder.indexOf(job.status);
    const thisIndex = stageOrder.indexOf(stageKey);

    if (thisIndex < currentIndex) return 'done';
    if (thisIndex === currentIndex) return 'active';
    return 'pending';
  };

  return (
    <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-6 shadow-xl">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-6">
        <div>
          <h3 className="text-base font-bold text-white">Status & Alur Kerja</h3>
          <p className="text-xs text-slate-400 mt-0.5">
            Pekerjaan ID: <span className="font-mono text-slate-300">{job.id}</span>
          </p>
        </div>
        <div className="text-right">
          <span className="text-2xl font-extrabold font-mono text-indigo-400">
            {Math.round(job.progress * 100)}%
          </span>
          <span className="text-xs text-slate-400 block">Total Progres</span>
        </div>
      </div>

      {/* Main Total Progress Bar */}
      <div className="h-2.5 w-full bg-slate-950 rounded-full overflow-hidden p-0.5 border border-slate-800 mb-8">
        <div
          className="h-full bg-gradient-to-r from-indigo-500 via-purple-500 to-emerald-400 rounded-full transition-all duration-300 shadow-sm"
          style={{ width: `${Math.round(job.progress * 100)}%` }}
        ></div>
      </div>

      {/* Timeline Steps */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {stages.map((stage) => {
          const status = getStageStatus(stage.key, stage.skipped);
          const Icon = stage.icon;

          return (
            <div
              key={stage.key}
              className={`p-4 rounded-xl border transition-all ${
                status === 'active'
                  ? 'bg-indigo-500/10 border-indigo-500/40 shadow-lg shadow-indigo-500/10'
                  : status === 'done'
                  ? 'bg-emerald-500/5 border-emerald-500/20'
                  : status === 'skipped'
                  ? 'bg-slate-950/30 border-slate-800/50 opacity-50'
                  : 'bg-slate-950/40 border-slate-800/80 opacity-70'
              }`}
            >
              <div className="flex items-center justify-between mb-2">
                <div
                  className={`w-8 h-8 rounded-lg flex items-center justify-center ${
                    status === 'active'
                      ? 'bg-indigo-600 text-white animate-pulse'
                      : status === 'done'
                      ? 'bg-emerald-600/20 text-emerald-400 border border-emerald-500/30'
                      : 'bg-slate-800 text-slate-400'
                  }`}
                >
                  {status === 'done' ? (
                    <Check className="w-4 h-4 text-emerald-400" />
                  ) : (
                    <Icon className="w-4 h-4" />
                  )}
                </div>
                {status === 'active' && (
                  <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
                    {Math.round(job.stage_progress * 100)}%
                  </span>
                )}
              </div>

              <h4 className="text-xs font-bold text-slate-200">{stage.label}</h4>
              <p className="text-[11px] text-slate-400 mt-1 leading-snug">{stage.desc}</p>
            </div>
          );
        })}
      </div>

      {job.error && (
        <div className="mt-6 p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs flex items-center gap-3">
          <AlertCircle className="w-5 h-5 text-rose-400 flex-shrink-0" />
          <div>
            <strong className="font-semibold block">Gagal:</strong>
            <span>{job.error}</span>
          </div>
        </div>
      )}

      {job.warnings && job.warnings.length > 0 && (
        <div className="mt-4 p-4 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-300 text-xs space-y-1">
          <strong className="font-semibold block">Peringatan:</strong>
          {job.warnings.map((w, i) => (
            <p key={i}>&bull; {w}</p>
          ))}
        </div>
      )}
    </div>
  );
}
