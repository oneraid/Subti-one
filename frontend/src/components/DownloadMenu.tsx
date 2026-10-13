import { useState, useEffect } from 'react';
import {
  Download,
  FileText,
  Film,
  Layers,
  Loader2,
  Check,
  Subtitles,
  Zap,
} from 'lucide-react';
import type { Job } from '../lib/types';
import { api } from '../lib/api';
import { getLanguageName } from '../lib/languages';

interface DownloadMenuProps {
  job: Job;
  activeLang: string;
  onBurnRequested?: () => void;
}

export default function DownloadMenu({ job, activeLang, onBurnRequested }: DownloadMenuProps) {
  const [isBurningHard, setIsBurningHard] = useState(false);
  const [isBurningSoft, setIsBurningSoft] = useState(false);

  const srcLang = job.source_lang_detected || job.source_lang_requested;
  const isTranslatedLang = activeLang !== srcLang;

  const hasHardSub = job.burned_langs?.includes(activeLang);
  const hasSoftSub = job.softsub_langs?.includes(activeLang);

  const burnProgressVal = job.burn_progress?.[activeLang];
  const isHardSubInProgress =
    isBurningHard || (burnProgressVal !== undefined && burnProgressVal < 1.0 && !hasHardSub);
  const hardPercent = burnProgressVal ? Math.round(burnProgressVal * 100) : 5;

  // Active polling while hard sub burn-in is encoding
  useEffect(() => {
    if (!isHardSubInProgress) return;
    const interval = setInterval(() => {
      onBurnRequested?.();
    }, 1200);
    return () => clearInterval(interval);
  }, [isHardSubInProgress, onBurnRequested]);

  const handleExport = async (mode: 'hard' | 'soft') => {
    try {
      if (mode === 'hard') {
        setIsBurningHard(true);
        await api.burnJob(job.id, activeLang, 'hard');
        onBurnRequested?.();
      } else {
        setIsBurningSoft(true);
        await api.burnJob(job.id, activeLang, 'soft');
        // Softsub takes ~0.5s - 1s with ffmpeg copy. Poll briefly to refresh state
        for (let i = 0; i < 5; i++) {
          await new Promise((r) => setTimeout(r, 600));
          onBurnRequested?.();
        }
      }
    } catch (err: any) {
      alert(`Gagal memproses ekspor video: ${err.message || err}`);
    } finally {
      if (mode === 'hard') {
        setIsBurningHard(false);
      } else {
        setIsBurningSoft(false);
      }
    }
  };

  return (
    <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-5 shadow-2xl space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-800/80 pb-3">
        <h3 className="text-sm font-bold text-white flex items-center gap-2">
          <Download className="w-4 h-4 text-indigo-400" />
          <span>Unduh Subtitle & Media</span>
        </h3>
        <span className="text-xs font-semibold px-2.5 py-0.5 rounded-full bg-indigo-500/10 text-indigo-300 border border-indigo-500/20">
          Bahasa: {getLanguageName(activeLang)}
        </span>
      </div>

      {/* Bagian 1: File Teks Subtitle */}
      <div>
        <div className="text-xs font-semibold text-slate-400 mb-2.5 flex items-center gap-1.5">
          <FileText className="w-3.5 h-3.5 text-slate-500" />
          <span>Format Teks Subtitle (Standalone)</span>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
          {/* SRT */}
          <a
            href={api.getDownloadUrl(job.id, activeLang, 'srt', false)}
            download
            className="p-3 rounded-xl bg-slate-950/70 border border-slate-800 hover:border-indigo-500/40 hover:bg-slate-950 transition-all flex items-center gap-3 group"
          >
            <div className="w-8 h-8 rounded-lg bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400 group-hover:bg-indigo-600 group-hover:text-white transition-colors shrink-0">
              <FileText className="w-4 h-4" />
            </div>
            <div className="min-w-0">
              <div className="text-xs font-semibold text-slate-200">File SRT</div>
              <div className="text-[11px] text-slate-400 truncate">Format teks umum</div>
            </div>
          </a>

          {/* WebVTT */}
          <a
            href={api.getDownloadUrl(job.id, activeLang, 'vtt', false)}
            download
            className="p-3 rounded-xl bg-slate-950/70 border border-slate-800 hover:border-purple-500/40 hover:bg-slate-950 transition-all flex items-center gap-3 group"
          >
            <div className="w-8 h-8 rounded-lg bg-purple-500/10 border border-purple-500/20 flex items-center justify-center text-purple-400 group-hover:bg-purple-600 group-hover:text-white transition-colors shrink-0">
              <FileText className="w-4 h-4" />
            </div>
            <div className="min-w-0">
              <div className="text-xs font-semibold text-slate-200">File WebVTT</div>
              <div className="text-[11px] text-slate-400 truncate">Untuk pemutar web</div>
            </div>
          </a>

          {/* Bilingual SRT */}
          {isTranslatedLang ? (
            <a
              href={api.getDownloadUrl(job.id, activeLang, 'srt', true, 'source_first')}
              download
              className="p-3 rounded-xl bg-slate-950/70 border border-slate-800 hover:border-pink-500/40 hover:bg-slate-950 transition-all flex items-center gap-3 group"
            >
              <div className="w-8 h-8 rounded-lg bg-pink-500/10 border border-pink-500/20 flex items-center justify-center text-pink-400 group-hover:bg-pink-600 group-hover:text-white transition-colors shrink-0">
                <Layers className="w-4 h-4" />
              </div>
              <div className="min-w-0">
                <div className="text-xs font-semibold text-slate-200">SRT Dwibahasa</div>
                <div className="text-[11px] text-slate-400 truncate">
                  {getLanguageName(srcLang)} + {getLanguageName(activeLang)}
                </div>
              </div>
            </a>
          ) : (
            <div className="p-3 rounded-xl bg-slate-950/30 border border-slate-800/40 flex items-center gap-3 opacity-40">
              <div className="w-8 h-8 rounded-lg bg-slate-800/40 flex items-center justify-center text-slate-600 shrink-0">
                <Layers className="w-4 h-4" />
              </div>
              <div className="min-w-0">
                <div className="text-xs font-medium text-slate-400">SRT Dwibahasa</div>
                <div className="text-[11px] text-slate-500 truncate">Tersedia pada hasil terjemahan</div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Bagian 2: Ekspor Video MP4 (Pilihan Hard Sub vs Soft Sub) */}
      <div className="pt-2 border-t border-slate-800/80">
        <div className="text-xs font-semibold text-slate-400 mb-2.5 flex items-center justify-between">
          <div className="flex items-center gap-1.5">
            <Film className="w-3.5 h-3.5 text-indigo-400" />
            <span>Ekspor Video MP4 Lengkap</span>
          </div>
          <span className="text-[10px] text-slate-500">Pilih jenis subtitle video</span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {/* 1. Hard Sub (Burn-in) Card */}
          <div className="p-3.5 rounded-xl bg-slate-950/80 border border-slate-800 flex flex-col justify-between space-y-3">
            <div>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="w-7 h-7 rounded-lg bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-400">
                    <Film className="w-3.5 h-3.5" />
                  </div>
                  <div>
                    <span className="text-xs font-bold text-slate-200">Hard Sub (Burn-in)</span>
                    <span className="ml-1.5 text-[10px] px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-300 font-medium">
                      Permanen
                    </span>
                  </div>
                </div>
              </div>
              <p className="text-[11px] text-slate-400 mt-2 leading-relaxed">
                Teks dicetak permanen menyatu pada video. Wajib untuk TikTok, Reels, Shorts, dan WhatsApp.
              </p>
            </div>

            {/* Action State */}
            {hasHardSub ? (
              <a
                href={api.getBurnedUrl(job.id, activeLang)}
                download
                className="w-full py-2 px-3 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-xs flex items-center justify-center gap-1.5 transition-all shadow-md shadow-emerald-600/20"
              >
                <Check className="w-3.5 h-3.5" />
                <span>Unduh MP4 Hard Sub</span>
              </a>
            ) : isHardSubInProgress ? (
              <div className="space-y-1.5 bg-slate-900/90 border border-slate-800 p-2.5 rounded-lg">
                <div className="flex items-center justify-between text-[11px]">
                  <span className="text-amber-300 font-medium flex items-center gap-1.5">
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    Sedang proses burn-in...
                  </span>
                  <span className="font-mono font-bold text-amber-400">{hardPercent}%</span>
                </div>
                <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-amber-500 to-indigo-500 transition-all duration-300 rounded-full"
                    style={{ width: `${Math.max(5, hardPercent)}%` }}
                  />
                </div>
              </div>
            ) : (
              <button
                onClick={() => handleExport('hard')}
                className="w-full py-2 px-3 rounded-lg bg-slate-800 hover:bg-amber-600 hover:text-white text-slate-200 font-semibold text-xs flex items-center justify-center gap-1.5 transition-all border border-slate-700"
              >
                <Film className="w-3.5 h-3.5" />
                <span>Render Hard Sub</span>
              </button>
            )}
          </div>

          {/* 2. Soft Sub (Embedded Track) Card */}
          <div className="p-3.5 rounded-xl bg-slate-950/80 border border-slate-800 flex flex-col justify-between space-y-3">
            <div>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="w-7 h-7 rounded-lg bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center text-cyan-400">
                    <Subtitles className="w-3.5 h-3.5" />
                  </div>
                  <div>
                    <span className="text-xs font-bold text-slate-200">Soft Sub (Track MP4)</span>
                    <span className="ml-1.5 text-[10px] px-1.5 py-0.5 rounded bg-cyan-500/10 text-cyan-300 font-medium flex-inline items-center gap-1">
                      <Zap className="w-2.5 h-2.5 inline mr-0.5" />
                      Instan
                    </span>
                  </div>
                </div>
              </div>
              <p className="text-[11px] text-slate-400 mt-2 leading-relaxed">
                Subtitle disematkan ke dalam MP4 tanpa render ulang video. Subtitle bisa dihidupkan/dimatikan di VLC/player.
              </p>
            </div>

            {/* Action State */}
            {hasSoftSub ? (
              <a
                href={api.getSoftsubUrl(job.id, activeLang)}
                download
                className="w-full py-2 px-3 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-xs flex items-center justify-center gap-1.5 transition-all shadow-md shadow-emerald-600/20"
              >
                <Check className="w-3.5 h-3.5" />
                <span>Unduh MP4 Soft Sub</span>
              </a>
            ) : isBurningSoft ? (
              <div className="w-full py-2 px-3 rounded-lg bg-slate-900 border border-slate-800 text-cyan-300 font-medium text-xs flex items-center justify-center gap-1.5">
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                <span>Membuat Soft Sub (sekejap)...</span>
              </div>
            ) : (
              <button
                onClick={() => handleExport('soft')}
                className="w-full py-2 px-3 rounded-lg bg-slate-800 hover:bg-cyan-600 hover:text-white text-slate-200 font-semibold text-xs flex items-center justify-center gap-1.5 transition-all border border-slate-700"
              >
                <Zap className="w-3.5 h-3.5 text-cyan-400" />
                <span>Buat Soft Sub (1 Detik)</span>
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
