import { Routes, Route, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Sparkles, Languages, AlertCircle, RefreshCw, Film } from 'lucide-react';
import { api } from './lib/api';
import HomePage from './pages/HomePage';
import JobPage from './pages/JobPage';

export default function App() {

  const { data: health, isLoading: healthLoading, isError: healthError, refetch: refetchHealth } = useQuery({
    queryKey: ['health'],
    queryFn: api.getHealth,
    refetchInterval: 15000,
  });

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col selection:bg-indigo-500/30">
      {/* Top Navbar */}
      <header className="sticky top-0 z-50 backdrop-blur-xl bg-slate-950/80 border-b border-slate-800/80">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-3 group">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500 via-purple-500 to-pink-500 flex items-center justify-center shadow-lg shadow-indigo-500/20 group-hover:shadow-indigo-500/40 transition-all duration-300">
              <Languages className="w-5 h-5 text-white" />
            </div>
            <div>
              <span className="text-lg font-bold bg-clip-text text-transparent bg-gradient-to-r from-white via-slate-200 to-slate-400">
                AutoSub
              </span>
              <span className="hidden sm:inline-block ml-2 text-xs px-2 py-0.5 rounded-full bg-indigo-500/10 text-indigo-300 border border-indigo-500/20 font-medium">
                AI Subtitle & Translate
              </span>
            </div>
          </Link>

          {/* System Status Indicators */}
          <div className="flex items-center gap-2 sm:gap-4 text-xs">
            {healthLoading ? (
              <div className="flex items-center gap-1.5 text-slate-400">
                <RefreshCw className="w-3.5 h-3.5 animate-spin text-slate-500" />
                <span className="hidden md:inline">Memeriksa sistem...</span>
              </div>
            ) : healthError ? (
              <div
                onClick={() => refetchHealth()}
                className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-rose-500/10 text-rose-400 border border-rose-500/20 cursor-pointer hover:bg-rose-500/20 transition-colors"
                title="Klik untuk mencoba ulang koneksi backend"
              >
                <AlertCircle className="w-3.5 h-3.5" />
                <span>Backend offline</span>
              </div>
            ) : (
              <div className="flex items-center gap-2">
                {/* FFmpeg Badge */}
                <div
                  className={`flex items-center gap-1 px-2 py-1 rounded-md border ${
                    health?.ffmpeg
                      ? 'bg-emerald-500/10 text-emerald-300 border-emerald-500/20'
                      : 'bg-amber-500/10 text-amber-300 border-amber-500/20'
                  }`}
                  title={health?.ffmpeg ? 'FFmpeg siap' : 'FFmpeg tidak ditemukan di PATH'}
                >
                  <Film className="w-3 h-3" />
                  <span className="hidden sm:inline">FFmpeg</span>
                </div>

                {/* Whisper Model Badge */}
                <div
                  className="flex items-center gap-1 px-2 py-1 rounded-md bg-slate-900 border border-slate-800 text-slate-300"
                  title={`Model Whisper default: ${health?.whisper_model}`}
                >
                  <span className="w-1.5 h-1.5 rounded-full bg-indigo-400"></span>
                  <span className="hidden sm:inline">Whisper:</span>
                  <span className="font-mono text-indigo-300">{health?.whisper_model}</span>
                </div>

                {/* Claude Translator Badge */}
                <div
                  className={`flex items-center gap-1 px-2 py-1 rounded-md border ${
                    health?.translator_ready
                      ? 'bg-purple-500/10 text-purple-300 border-purple-500/20'
                      : 'bg-slate-800/60 text-slate-400 border-slate-700/50'
                  }`}
                  title={
                    health?.translator_ready
                      ? 'Claude API Key siap untuk terjemahan'
                      : 'ANTHROPIC_API_KEY belum diisi di .env'
                  }
                >
                  <Sparkles className="w-3 h-3" />
                  <span className="hidden sm:inline">Claude:</span>
                  <span>{health?.translator_ready ? 'Siap' : 'Kunci belum ada'}</span>
                </div>
              </div>
            )}
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/jobs/:id" element={<JobPage />} />
        </Routes>
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-800/80 bg-slate-950/60 py-6 text-center text-xs text-slate-500">
        <div className="max-w-7xl mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-2">
          <p>AutoSub &copy; 2026 — Speech-to-Text & Subtitle Translator</p>
          <p className="flex items-center gap-2">
            <span>faster-whisper</span>
            <span>&bull;</span>
            <span>Claude 3.5/5</span>
            <span>&bull;</span>
            <span>ffmpeg</span>
          </p>
        </div>
      </footer>
    </div>
  );
}
