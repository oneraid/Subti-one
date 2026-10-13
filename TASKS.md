# Rencana Tugas (kerjakan berurutan)

Centang `[x]` setelah selesai. Tiap fase punya **Acceptance** yang harus lolos sebelum lanjut.

## Fase 0 — Scaffolding
- [x] `backend/pyproject.toml` (fastapi, uvicorn[standard], pydantic-settings, python-multipart,
      faster-whisper, anthropic, pytest, pytest-asyncio, httpx, ruff)
- [x] `backend/app/` kerangka: `main.py`, `config.py`, `languages.py`, `models.py`, `storage.py`
- [x] `GET /api/health` & `GET /api/config`
- [x] `frontend/` Vite + React + TS + Tailwind + TanStack Query + react-router; proxy `/api`
- [x] `.gitignore` (data/, .env, node_modules, .venv, __pycache__, dist)
- **Acceptance**: `uvicorn` & `npm run dev` jalan; halaman depan memanggil `/api/config`
  dan menampilkan daftar bahasa; `pytest` & `ruff` & `npm run build` hijau.

## Fase 1 — Inti subtitle (murni, tanpa jaringan)
- [x] `subtitle.py`: parse/tulis SRT & VTT, format waktu `HH:MM:SS,mmm`, gabung dwibahasa
- [x] `segment.py`: kata berwaktu → cue sesuai `ARCHITECTURE.md §4`, termasuk `wrap_lines()`
- [x] Test: round-trip SRT; batas karakter latin & CJK; potong di kalimat; tanpa tumpang tindih;
      jeda panjang memotong cue; buang halusinasi berulang; CPS
- **Acceptance**: semua test fase ini hijau, cakupan modul ini ≥ 90%.

## Fase 2 — Audio & transkripsi
- [x] `audio.py`: ekstrak WAV, probe durasi, error jelas bila tanpa audio / file rusak
- [x] `transcribe.py`: faster-whisper, lazy load, progress callback, deteksi bahasa,
      penanganan bahasa tak didukung (lihat §3)
- [x] CLI dev `python -m app.cli transcribe <file> --lang auto` yang menulis SRT (alat debug)
- [x] Test dengan **fake transcriber** (protocol) untuk pipeline; satu test `@slow` memakai model
      `tiny` dan klip pendek yang dihasilkan lokal (mis. TTS/espeak atau sine+file kecil di `tests/fixtures`)
- **Acceptance**: CLI menghasilkan SRT valid dari klip Inggris, Indonesia, dan Mandarin (manual/slow test);
  progress callback bergerak 0→1.

## Fase 3 — Job manager & API
- [x] `jobs.py` (antrean, worker, persist `meta.json` atomik, cancel, pub/sub event, cleanup)
- [x] `pipeline.py` tahap audio → transkripsi → segmentasi → simpan SRT (terjemahan di fase 4)
- [x] Router: `POST/GET /jobs`, `GET /jobs/{id}`, `/events` (SSE), `/cancel`, `DELETE`,
      `/subtitles/{lang}` (GET/PUT/download), `/media` (Range)
- [x] Validasi upload (ukuran, ffprobe), path aman, error seragam
- [x] Test API dengan `httpx.AsyncClient` + fake transcriber: upload → poll → `done` → unduh SRT;
      upload bukan media → 415; path traversal ditolak; cancel bekerja
- **Acceptance**: alur upload→subtitle sumber jalan via `curl` dengan model asli pada klip pendek;
  test hijau.

## Fase 4 — Terjemahan
- [x] `translate/base.py` (Protocol), `batching.py` (batch + konteks + validasi + split-retry)
- [x] `translate/claude.py` (SDK `anthropic`, structured output/tool use, timeout, retry/backoff,
      konkurensi ≤ 3, glossary)
- [x] Integrasi ke `pipeline.py` (per target, progres terbagi, `warnings` bila fallback)
- [x] `POST /jobs/{id}/translate`
- [x] Test: batching & konteks; validasi id; retry → split → fallback; wrap ulang baris panjang;
      mock SDK (tanpa jaringan); target sama dengan sumber dilewati
- **Acceptance**: dengan API key asli, klip Inggris → `id` dan klip Mandarin → `en`/`id` menghasilkan
  jumlah & timestamp cue identik dengan sumber; test mock hijau.

## Fase 5 — Frontend inti
- [x] `lib/types.ts`, `lib/api.ts` (fetch + error), `lib/languages.ts`
- [x] `UploadForm` (+ upload progress via XHR/fetch stream), `JobList`
- [x] `useJob` (SSE + fallback polling), `ProgressTimeline`
- [x] `JobPage` dengan tab bahasa, `DownloadMenu`
- **Acceptance**: dari browser: unggah klip → lihat progres real-time → unduh SRT sumber & terjemahan.

## Fase 6 — Preview & editor
- [x] `VideoPreview` (VTT blob → `<track>`, ganti bahasa mulus; audio-only tampilkan waveform sederhana/pemutar audio)
- [x] `SegmentEditor` (inline edit, klik-loncat, indikator pelanggaran, simpan via `PUT`, virtualisasi >500 baris)
- [x] Tombol "Terjemahkan ke…" (memanggil `/translate`) setelah job selesai
- **Acceptance**: edit teks → simpan → unduh SRT mencerminkan edit; subtitle tampil sinkron di video.

## Fase 7 — Burn-in & polish
- [x] `audio.burn_subtitles()` + endpoint `/burn` + `/burned/{lang}` + UI
- [x] Penanganan font CJK; pesan error ramah
- [x] Empty/loading/error states di semua halaman; responsif; aksesibilitas dasar
- [x] README: cara menjalankan (sudah diuji), catatan keamanan (tanpa auth), perkiraan kecepatan
      model per perangkat
- [x] (Opsional, bila diminta) Dockerfile + docker-compose
- **Acceptance**: seluruh "Definisi selesai" di `CLAUDE.md` terpenuhi; satu demo end-to-end
  terdokumentasi (langkah + hasil) di README.

## Kasus uji manual (jalankan di akhir)

| # | Input | Sumber | Target | Harapan |
|---|---|---|---|---|
| 1 | Klip 30 dtk bicara Inggris | auto | id | Terdeteksi `en`, SRT en + id, jumlah cue sama |
| 2 | Klip Indonesia | auto | en | Terdeteksi `id`, SRT id + en |
| 3 | Klip Mandarin | auto | en,id | Terdeteksi `zh`, ≤16 karakter/baris, terjemahan en & id |
| 4 | Audio saja (mp3) | en | - | Subtitle tanpa terjemahan, pemutar audio di UI |
| 5 | File teks diubah jadi .mp4 | auto | - | Ditolak 415 dengan pesan jelas |
| 6 | Video tanpa suara | auto | - | Job gagal dengan pesan "tidak ada audio/ucapan" |
| 7 | Batalkan di tengah transkripsi | auto | id | Status `cancelled`, tidak ada proses menggantung |
| 8 | Restart server saat job berjalan | auto | id | Job tidak membuat server crash; status sesuai keputusan di §6 |
