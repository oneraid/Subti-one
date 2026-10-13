import { Link } from 'react-router-dom';
import { Clock, Trash2, ArrowRight, CheckCircle2, AlertCircle, Loader2, StopCircle } from 'lucide-react';
import type { Job } from '../lib/types';
import { formatDuration } from '../lib/format';
import { getLanguageName } from '../lib/languages';

interface JobListProps {
  jobs: Job[];
  isLoading: boolean;
  onDeleteJob: (id: string) => void;
  onCancelJob: (id: string) => void;
}

export default function JobList({ jobs, isLoading, onDeleteJob, onCancelJob }: JobListProps) {
  if (isLoading) {
    return (
      <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-8 text-center text-slate-400">
        <Loader2 className="w-6 h-6 animate-spin mx-auto text-indigo-400 mb-2" />
        <p className="text-sm">Memuat riwayat pekerjaan...</p>
      </div>
    );
  }

  if (jobs.length === 0) {
    return (
      <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-10 text-center text-slate-400">
        <div className="w-12 h-12 rounded-2xl bg-slate-800/80 mx-auto flex items-center justify-center text-slate-500 mb-3">
          <Clock className="w-6 h-6" />
        </div>
        <p className="text-sm font-medium text-slate-300">Belum ada pekerjaan transkripsi</p>
        <p className="text-xs text-slate-500 mt-1">Unggah video atau audio di atas untuk memulai.</p>
      </div>
    );
  }

  const getStatusBadge = (job: Job) => {
    switch (job.status) {
      case 'done':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            <CheckCircle2 className="w-3 h-3" />
            Selesai
          </span>
        );
      case 'failed':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-rose-500/10 text-rose-400 border border-rose-500/20">
            <AlertCircle className="w-3 h-3" />
            Gagal
          </span>
        );
      case 'cancelled':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-500/10 text-amber-400 border border-amber-500/20">
            <StopCircle className="w-3 h-3" />
            Dibatalkan
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
            <Loader2 className="w-3 h-3 animate-spin" />
            <span className="capitalize">{job.status.replace('_', ' ')}</span>
            <span className="font-mono">{Math.round(job.progress * 100)}%</span>
          </span>
        );
    }
  };

  return (
    <div className="bg-slate-900/80 border border-slate-800 rounded-2xl overflow-hidden shadow-xl">
      <div className="p-5 border-b border-slate-800 flex items-center justify-between">
        <h3 className="text-base font-bold text-white flex items-center gap-2">
          <span>Riwayat Pekerjaan</span>
          <span className="text-xs font-normal text-slate-400 bg-slate-800 px-2 py-0.5 rounded-full">
            {jobs.length}
          </span>
        </h3>
      </div>

      <div className="divide-y divide-slate-800/80">
        {jobs.map((job) => {
          const isRunning =
            job.status !== 'done' && job.status !== 'failed' && job.status !== 'cancelled';

          return (
            <div
              key={job.id}
              className="p-4 sm:p-5 hover:bg-slate-800/40 transition-colors flex flex-col sm:flex-row sm:items-center justify-between gap-4"
            >
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-3 flex-wrap mb-1">
                  <Link
                    to={`/jobs/${job.id}`}
                    className="text-sm font-semibold text-slate-200 hover:text-indigo-400 transition-colors truncate max-w-md block"
                  >
                    {job.filename}
                  </Link>
                  {getStatusBadge(job)}
                </div>

                <div className="flex items-center gap-3 text-xs text-slate-400 flex-wrap">
                  <span>
                    Sumber:{' '}
                    <strong className="text-slate-300">
                      {job.source_lang_detected
                        ? `${getLanguageName(job.source_lang_detected)} (${job.source_lang_detected})`
                        : getLanguageName(job.source_lang_requested)}
                    </strong>
                  </span>
                  <span>&bull;</span>
                  <span>
                    Target:{' '}
                    <strong className="text-slate-300">
                      {job.target_langs.length > 0
                        ? job.target_langs.map(getLanguageName).join(', ')
                        : 'Tanpa Terjemahan'}
                    </strong>
                  </span>
                  {job.duration_sec && (
                    <>
                      <span>&bull;</span>
                      <span>Durasi: {formatDuration(job.duration_sec)}</span>
                    </>
                  )}
                  <span>&bull;</span>
                  <span>Model: {job.model_size}</span>
                </div>

                {isRunning && (
                  <div className="mt-3 max-w-md">
                    <div className="h-1.5 w-full bg-slate-800 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-gradient-to-r from-indigo-500 to-purple-500 transition-all duration-300"
                        style={{ width: `${Math.round(job.progress * 100)}%` }}
                      ></div>
                    </div>
                  </div>
                )}
              </div>

              <div className="flex items-center gap-2 self-end sm:self-center">
                {isRunning && (
                  <button
                    onClick={() => onCancelJob(job.id)}
                    className="px-3 py-1.5 rounded-lg text-xs font-medium text-amber-400 hover:bg-amber-500/10 border border-amber-500/20 transition-colors"
                  >
                    Batalkan
                  </button>
                )}
                <button
                  onClick={() => onDeleteJob(job.id)}
                  className="p-2 rounded-lg text-slate-500 hover:text-rose-400 hover:bg-rose-500/10 transition-colors"
                  title="Hapus pekerjaan"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
                <Link
                  to={`/jobs/${job.id}`}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-indigo-600/20 text-indigo-300 border border-indigo-500/30 hover:bg-indigo-600/30 transition-colors"
                >
                  <span>Buka</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </Link>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
