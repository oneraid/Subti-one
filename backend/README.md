# AutoSub

Aplikasi web untuk **auto subtitle** (speech-to-text) dan **auto translate subtitle**.

- **Speech-to-text**: Indonesia (`id`), Inggris (`en`), Mandarin (`zh`), dengan auto-detect bahasa.
- **Terjemahan**: ke Inggris (`en`) dan Indonesia (`id`).
- **Backend**: Python 3.11+, FastAPI, faster-whisper, ffmpeg.
- **Frontend**: React + TypeScript + Vite + Tailwind.
- **Terjemahan**: Claude API (default), dengan antarmuka backend yang bisa diganti.

> Status: **tahap spesifikasi**. Belum ada kode implementasi. Semua keputusan desain ada di `docs/`.
> Agent AI yang mengerjakan proyek ini: mulai dari `CLAUDE.md`.

## Alur singkat

```
Upload video/audio
  → ffmpeg ekstrak audio (WAV 16kHz mono)
  → faster-whisper transkripsi (bahasa auto/id/en/zh) + word timestamps
  → segmentasi ulang jadi cue subtitle yang enak dibaca
  → simpan subtitle sumber (SRT)
  → terjemahan per batch dengan konteks (en/id) lewat Claude API
  → simpan subtitle terjemahan (SRT/VTT)
  → (opsional) burn-in ke video dengan ffmpeg
Frontend: progress real-time, preview video + subtitle, edit teks, unduh.
```

## Dokumen

| File | Isi |
|---|---|
| `CLAUDE.md` | Aturan kerja, konvensi, dan definisi "selesai" untuk AI agent |
| `docs/ARCHITECTURE.md` | Struktur proyek, modul, model data, algoritma, keputusan teknis |
| `docs/API.md` | Kontrak REST + SSE antara frontend dan backend |
| `docs/TASKS.md` | Daftar tugas bertahap dengan acceptance criteria |
| `.env.example` | Variabel lingkungan |

## Menjalankan (target setelah implementasi)

```bash
# Prasyarat: Python 3.11+, Node 20+, ffmpeg
cp .env.example .env            # isi ANTHROPIC_API_KEY

# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000

# Frontend (terminal lain)
cd frontend
npm install
npm run dev                     # http://localhost:5173
```
