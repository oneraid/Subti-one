import { useState, useEffect } from 'react';
import { Save, AlertTriangle, Play, Check, Undo2 } from 'lucide-react';
import type { Segment } from '../lib/types';
import { formatTimestamp } from '../lib/format';

interface SegmentEditorProps {
  segments: Segment[];
  lang: string;
  currentTime?: number;
  onSeek: (time: number) => void;
  onSave: (updatedSegments: Segment[]) => Promise<void>;
  isSaving: boolean;
}

export default function SegmentEditor({
  segments,
  lang,
  currentTime = 0,
  onSeek,
  onSave,
  isSaving,
}: SegmentEditorProps) {
  const [editedSegments, setEditedSegments] = useState<Segment[]>(segments);
  const [dirty, setDirty] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);

  useEffect(() => {
    setEditedSegments(segments);
    setDirty(false);
  }, [segments, lang]);

  const isCJK = lang === 'zh';
  const maxCharsPerLine = isCJK ? 16 : 38;
  const maxCps = isCJK ? 9 : 17;

  const handleTextChange = (index: number, newText: string) => {
    setEditedSegments((prev) =>
      prev.map((seg) => (seg.index === index ? { ...seg, text: newText } : seg))
    );
    setDirty(true);
    setSaveSuccess(false);
  };

  const handleSave = async () => {
    try {
      await onSave(editedSegments);
      setDirty(false);
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch (err) {
      alert('Gagal menyimpan perubahan');
    }
  };

  const handleReset = () => {
    setEditedSegments(segments);
    setDirty(false);
  };

  const checkViolations = (seg: Segment) => {
    const lines = seg.text.split('\n');
    const lineCountViolation = lines.length > 2;
    const charViolations = lines.some((line) => line.length > maxCharsPerLine);
    const duration = Math.max(0.01, seg.end - seg.start);
    const charCount = seg.text.replace(/\s+/g, '').length;
    const cps = charCount / duration;
    const cpsViolation = cps > maxCps;

    return {
      lineCountViolation,
      charViolations,
      cpsViolation,
      cps: cps.toFixed(1),
      hasViolation: lineCountViolation || charViolations || cpsViolation,
    };
  };

  return (
    <div className="bg-slate-900/80 border border-slate-800 rounded-2xl overflow-hidden shadow-xl flex flex-col h-full">
      {/* Editor Header */}
      <div className="p-4 border-b border-slate-800 flex items-center justify-between gap-4 flex-wrap bg-slate-950/40">
        <div>
          <h3 className="text-sm font-bold text-white flex items-center gap-2">
            <span>Editor Subtitle ({lang.toUpperCase()})</span>
            <span className="text-xs font-normal text-slate-400 bg-slate-800 px-2 py-0.5 rounded-full font-mono">
              {editedSegments.length} cue
            </span>
          </h3>
          <p className="text-[11px] text-slate-400 mt-0.5">
            Klik baris atau waktu untuk memutar dari titik tersebut.
          </p>
        </div>

        <div className="flex items-center gap-2">
          {dirty && (
            <button
              onClick={handleReset}
              className="px-3 py-1.5 rounded-lg text-xs font-medium text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition-colors flex items-center gap-1.5"
            >
              <Undo2 className="w-3.5 h-3.5" />
              <span>Batal</span>
            </button>
          )}

          <button
            onClick={handleSave}
            disabled={!dirty || isSaving}
            className={`px-4 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all ${
              saveSuccess
                ? 'bg-emerald-600 text-white'
                : dirty
                ? 'bg-indigo-600 hover:bg-indigo-500 text-white shadow-md shadow-indigo-600/30'
                : 'bg-slate-800 text-slate-500 cursor-not-allowed'
            }`}
          >
            {saveSuccess ? (
              <>
                <Check className="w-3.5 h-3.5" />
                <span>Tersimpan!</span>
              </>
            ) : isSaving ? (
              <span>Menyimpan...</span>
            ) : (
              <>
                <Save className="w-3.5 h-3.5" />
                <span>Simpan Perubahan</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Cue Table */}
      <div className="flex-1 overflow-y-auto max-h-[550px] divide-y divide-slate-800/60 font-sans">
        {editedSegments.length === 0 ? (
          <div className="p-8 text-center text-slate-500 text-xs">Tidak ada cue subtitle</div>
        ) : (
          editedSegments.map((seg) => {
            const isActive = currentTime >= seg.start && currentTime <= seg.end;
            const violations = checkViolations(seg);

            return (
              <div
                key={seg.index}
                className={`p-3 sm:p-4 transition-colors flex items-start gap-3 sm:gap-4 ${
                  isActive
                    ? 'bg-indigo-500/15 border-l-4 border-indigo-500'
                    : 'hover:bg-slate-800/30'
                }`}
              >
                {/* Index & Seek Play Button */}
                <div className="flex flex-col items-center gap-1.5 flex-shrink-0 pt-0.5">
                  <span className="text-[11px] font-mono text-slate-500">{seg.index}</span>
                  <button
                    onClick={() => onSeek(seg.start)}
                    className="p-1 rounded-md bg-slate-800 hover:bg-indigo-600 text-slate-400 hover:text-white transition-colors"
                    title="Putar dari cue ini"
                  >
                    <Play className="w-3 h-3 fill-current" />
                  </button>
                </div>

                {/* Timestamps */}
                <div className="flex-shrink-0 text-[11px] font-mono text-slate-400 space-y-1 w-24 sm:w-28 pt-1">
                  <div
                    onClick={() => onSeek(seg.start)}
                    className="cursor-pointer hover:text-indigo-300"
                  >
                    {formatTimestamp(seg.start)}
                  </div>
                  <div className="text-slate-600 text-[10px]">&darr;</div>
                  <div
                    onClick={() => onSeek(seg.end)}
                    className="cursor-pointer hover:text-indigo-300"
                  >
                    {formatTimestamp(seg.end)}
                  </div>
                  <div className="text-[10px] text-slate-500 pt-0.5">
                    {(seg.end - seg.start).toFixed(2)}s
                  </div>
                </div>

                {/* Editable Text Area */}
                <div className="flex-1 min-w-0">
                  <textarea
                    value={seg.text}
                    onChange={(e) => handleTextChange(seg.index, e.target.value)}
                    rows={seg.text.includes('\n') ? 2 : 1}
                    className={`w-full bg-slate-950/70 border rounded-lg p-2 text-xs sm:text-sm text-slate-200 focus:outline-none focus:ring-1 transition-all resize-y ${
                      violations.hasViolation
                        ? 'border-amber-500/40 focus:border-amber-500 focus:ring-amber-500/20'
                        : 'border-slate-800 focus:border-indigo-500 focus:ring-indigo-500/20'
                    }`}
                  />

                  {/* Violation Warnings if any */}
                  {violations.hasViolation && (
                    <div className="flex items-center gap-2 mt-1 text-[11px] text-amber-400 flex-wrap">
                      <AlertTriangle className="w-3 h-3 flex-shrink-0" />
                      {violations.lineCountViolation && <span>Maksimal 2 baris</span>}
                      {violations.charViolations && (
                        <span>Maks {maxCharsPerLine} karakter/baris</span>
                      )}
                      {violations.cpsViolation && (
                        <span>Kecepatan baca tinggi ({violations.cps} CPS &gt; {maxCps})</span>
                      )}
                    </div>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
