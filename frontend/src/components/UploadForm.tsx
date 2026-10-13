import React, { useState, useRef } from 'react';
import { UploadCloud, FileVideo, Music, AlertTriangle, Settings2, Sparkles, X, Check } from 'lucide-react';
import type { ConfigResponse, Job, SourceLangCode, TargetLangCode } from '../lib/types';
import { SOURCE_LANGUAGES, TARGET_LANGUAGES, WHISPER_MODELS } from '../lib/languages';
import { formatFileSize } from '../lib/format';
import { useUpload } from '../hooks/useUpload';

interface UploadFormProps {
  config?: ConfigResponse;
  onJobCreated: (job: Job) => void;
}

export default function UploadForm({ config, onJobCreated }: UploadFormProps) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [sourceLang, setSourceLang] = useState<SourceLangCode>('auto');
  const [targetLangs, setTargetLangs] = useState<TargetLangCode[]>(['en']);
  const [modelSize, setModelSize] = useState<string>(config?.default_model || 'small');
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [glossaryText, setGlossaryText] = useState('');
  const [dragActive, setDragActive] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const { uploadFile, isUploading, uploadProgress, error, clearError } = useUpload();

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      validateAndSetFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      validateAndSetFile(e.target.files[0]);
    }
  };

  const validateAndSetFile = (file: File) => {
    clearError();
    const maxBytes = (config?.max_upload_mb || 2048) * 1024 * 1024;
    if (file.size > maxBytes) {
      alert(`Ukuran file melebihi batas maksimal (${config?.max_upload_mb || 2048} MB)`);
      return;
    }
    setSelectedFile(file);
  };

  const toggleTargetLang = (code: TargetLangCode) => {
    if (targetLangs.includes(code)) {
      setTargetLangs(targetLangs.filter((l) => l !== code));
    } else {
      setTargetLangs([...targetLangs, code]);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile) return;

    let parsedGlossary: Record<string, string> | undefined = undefined;
    if (glossaryText.trim()) {
      try {
        parsedGlossary = JSON.parse(glossaryText.trim());
      } catch {
        // Try line-by-line format: key=value or key:value
        const lines = glossaryText.split('\n');
        const map: Record<string, string> = {};
        for (const line of lines) {
          const parts = line.includes('=') ? line.split('=') : line.split(':');
          if (parts.length >= 2) {
            map[parts[0].trim()] = parts.slice(1).join(':').trim();
          }
        }
        if (Object.keys(map).length > 0) {
          parsedGlossary = map;
        }
      }
    }

    uploadFile(selectedFile, {
      sourceLang,
      targetLangs,
      modelSize,
      glossary: parsedGlossary,
      onSuccess: (job) => {
        setSelectedFile(null);
        if (fileInputRef.current) fileInputRef.current.value = '';
        onJobCreated(job);
      },
    });
  };

  const isVideo = selectedFile?.type.startsWith('video/') || selectedFile?.name.match(/\.(mp4|mkv|mov|avi|webm)$/i);

  return (
    <div className="bg-slate-900/80 backdrop-blur-md border border-slate-800 rounded-2xl p-6 sm:p-8 shadow-xl relative overflow-hidden">
      {/* Background glow accent */}
      <div className="absolute top-0 right-0 w-80 h-80 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none -mr-20 -mt-20"></div>

      <h2 className="text-xl font-bold text-white mb-2 flex items-center gap-2">
        <Sparkles className="w-5 h-5 text-indigo-400" />
        Mulai Subtitle Baru
      </h2>
      <p className="text-sm text-slate-400 mb-6">
        Unggah file video atau audio untuk ditranskripsi otomatis dengan Whisper dan diterjemahkan.
      </p>

      {error && (
        <div className="mb-6 p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-sm flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 flex-shrink-0 text-rose-400 mt-0.5" />
          <div className="flex-1">
            <p className="font-semibold">Terjadi Kesalahan</p>
            <p className="text-xs text-rose-300/90 mt-0.5">{error}</p>
          </div>
          <button onClick={clearError} className="text-rose-400 hover:text-rose-200">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Dropzone */}
        {!selectedFile ? (
          <div
            onDragEnter={handleDrag}
            onDragLeave={handleDrag}
            onDragOver={handleDrag}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            className={`border-2 border-dashed rounded-2xl p-8 sm:p-12 text-center cursor-pointer transition-all duration-300 ${
              dragActive
                ? 'border-indigo-400 bg-indigo-500/10 scale-[1.01]'
                : 'border-slate-700/80 hover:border-slate-600 bg-slate-950/40 hover:bg-slate-950/60'
            }`}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept="video/*,audio/*,.mkv,.mp4,.mov,.avi,.webm,.mp3,.wav,.m4a,.flac,.aac"
              className="hidden"
              onChange={handleFileInput}
              disabled={isUploading}
            />
            <div className="w-14 h-14 mx-auto mb-4 rounded-2xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400 group-hover:scale-110 transition-transform">
              <UploadCloud className="w-7 h-7" />
            </div>
            <p className="text-base font-semibold text-slate-200">
              Tarik & letakkan file di sini, atau <span className="text-indigo-400 underline decoration-indigo-400/40">pilih dari perangkat</span>
            </p>
            <p className="text-xs text-slate-500 mt-2">
              Mendukung MP4, MKV, MOV, WEBM, MP3, WAV, dsb. (Maksimal {config?.max_upload_mb || 2048} MB)
            </p>
          </div>
        ) : (
          <div className="p-4 sm:p-5 rounded-2xl bg-slate-950/60 border border-slate-800 flex items-center justify-between gap-4">
            <div className="flex items-center gap-3 overflow-hidden">
              <div className="w-12 h-12 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center flex-shrink-0 text-indigo-400">
                {isVideo ? <FileVideo className="w-6 h-6" /> : <Music className="w-6 h-6" />}
              </div>
              <div className="overflow-hidden">
                <p className="text-sm font-semibold text-slate-200 truncate">{selectedFile.name}</p>
                <p className="text-xs text-slate-500 mt-0.5">{formatFileSize(selectedFile.size)}</p>
              </div>
            </div>
            {!isUploading && (
              <button
                type="button"
                onClick={() => setSelectedFile(null)}
                className="p-2 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition-colors"
                title="Ganti file"
              >
                <X className="w-5 h-5" />
              </button>
            )}
          </div>
        )}

        {/* Upload Progress Bar if uploading */}
        {isUploading && (
          <div className="space-y-2">
            <div className="flex justify-between text-xs text-slate-400 font-medium">
              <span>Mengunggah file ke server...</span>
              <span className="font-mono text-indigo-400">{uploadProgress}%</span>
            </div>
            <div className="h-2 w-full bg-slate-800 rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-indigo-500 to-purple-500 transition-all duration-200 rounded-full"
                style={{ width: `${uploadProgress}%` }}
              ></div>
            </div>
          </div>
        )}

        {/* Options Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5 pt-2">
          {/* Source Language */}
          <div>
            <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
              Bahasa Sumber (STT)
            </label>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              {(config?.source_languages || SOURCE_LANGUAGES).map((lang) => {
                const active = sourceLang === lang.code;
                return (
                  <button
                    key={lang.code}
                    type="button"
                    onClick={() => setSourceLang(lang.code as SourceLangCode)}
                    disabled={isUploading}
                    className={`px-3 py-2.5 rounded-xl text-xs font-medium border text-center transition-all ${
                      active
                        ? 'bg-indigo-600 text-white border-indigo-500 shadow-md shadow-indigo-600/30'
                        : 'bg-slate-950/40 text-slate-400 border-slate-800 hover:border-slate-700 hover:text-slate-200'
                    }`}
                  >
                    {lang.label}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Target Languages */}
          <div>
            <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
              Target Terjemahan
            </label>
            <div className="grid grid-cols-2 gap-2">
              {(config?.target_languages || TARGET_LANGUAGES).map((lang) => {
                const active = targetLangs.includes(lang.code as TargetLangCode);
                return (
                  <button
                    key={lang.code}
                    type="button"
                    onClick={() => toggleTargetLang(lang.code as TargetLangCode)}
                    disabled={isUploading}
                    className={`px-3 py-2.5 rounded-xl text-xs font-medium border flex items-center justify-between transition-all ${
                      active
                        ? 'bg-purple-600/20 text-purple-200 border-purple-500/50 shadow-sm'
                        : 'bg-slate-950/40 text-slate-400 border-slate-800 hover:border-slate-700 hover:text-slate-200'
                    }`}
                  >
                    <span>{lang.label}</span>
                    <div
                      className={`w-4 h-4 rounded flex items-center justify-center border ${
                        active
                          ? 'bg-purple-600 border-purple-400 text-white'
                          : 'border-slate-700 bg-slate-900'
                      }`}
                    >
                      {active && <Check className="w-3 h-3" />}
                    </div>
                  </button>
                );
              })}
            </div>
            <p className="text-[11px] text-slate-500 mt-1.5">
              Kosongkan jika hanya ingin transkripsi tanpa terjemahan.
            </p>
          </div>
        </div>

        {/* Advanced Settings Toggle */}
        <div className="pt-2 border-t border-slate-800/80">
          <button
            type="button"
            onClick={() => setShowAdvanced(!showAdvanced)}
            className="flex items-center gap-2 text-xs font-medium text-slate-400 hover:text-slate-200 transition-colors"
          >
            <Settings2 className="w-4 h-4 text-slate-500" />
            <span>{showAdvanced ? 'Sembunyikan Opsi Lanjutan' : 'Tampilkan Opsi Lanjutan (Ukuran Model & Glosarium)'}</span>
          </button>

          {showAdvanced && (
            <div className="mt-4 p-4 rounded-xl bg-slate-950/50 border border-slate-800 space-y-4">
              {/* Whisper Model Size */}
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                  Ukuran Model Whisper
                </label>
                <select
                  value={modelSize}
                  onChange={(e) => setModelSize(e.target.value)}
                  disabled={isUploading}
                  className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-indigo-500 font-mono"
                >
                  {(config?.whisper_models || WHISPER_MODELS).map((m) => (
                    <option key={m} value={m}>
                      {m} {m === 'small' ? '(rekomendasi, seimbang)' : m === 'tiny' ? '(sangat cepat, akurasi rendah)' : ''}
                    </option>
                  ))}
                </select>
              </div>

              {/* Glossary */}
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                  Glosarium Khusus (Opsional)
                </label>
                <textarea
                  value={glossaryText}
                  onChange={(e) => setGlossaryText(e.target.value)}
                  placeholder={`Contoh JSON atau baris teks:\nAutoSub=AutoSub\nmachine learning=pembelajaran mesin`}
                  rows={3}
                  disabled={isUploading}
                  className="w-full bg-slate-900 border border-slate-700 rounded-lg p-2.5 text-xs text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-indigo-500 font-mono"
                />
              </div>
            </div>
          )}
        </div>

        {/* Submit Button */}
        <button
          type="submit"
          disabled={!selectedFile || isUploading}
          className={`w-full py-3.5 px-6 rounded-xl font-semibold text-sm transition-all flex items-center justify-center gap-2 ${
            !selectedFile || isUploading
              ? 'bg-slate-800 text-slate-500 cursor-not-allowed'
              : 'bg-gradient-to-r from-indigo-500 via-purple-500 to-pink-500 text-white shadow-lg shadow-indigo-500/25 hover:shadow-indigo-500/40 hover:scale-[1.01] active:scale-[0.99]'
          }`}
        >
          {isUploading ? (
            <span>Mengunggah... ({uploadProgress}%)</span>
          ) : (
            <>
              <Sparkles className="w-4 h-4" />
              <span>Proses Subtitle Sekarang</span>
            </>
          )}
        </button>
      </form>
    </div>
  );
}
