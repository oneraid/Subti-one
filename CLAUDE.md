# CLAUDE.md — Panduan untuk AI agent

Kamu mengerjakan **AutoSub**: auto subtitle + auto translate. Baca `README.md`, lalu
`docs/ARCHITECTURE.md`, `docs/API.md`, dan `docs/TASKS.md` sebelum menulis kode.

## Cara kerja

1. Kerjakan `docs/TASKS.md` **berurutan per fase**. Jangan lompat fase.
2. Satu fase selesai = semua acceptance criteria terpenuhi **dan** test fase itu hijau.
3. Centang tugas di `docs/TASKS.md` setelah selesai (`- [x]`).
4. Jika spesifikasi bertentangan dengan kenyataan (library berubah, API beda), ikuti kenyataan,
   lalu **perbarui dokumen** di `docs/` agar tetap benar dan catat di bagian "Catatan keputusan"
   pada `docs/ARCHITECTURE.md`.
5. Jangan menambah fitur di luar spesifikasi. Hal-hal di "Di luar cakupan" jangan dikerjakan.

## Batasan penting

- Bahasa STT yang didukung: `id`, `en`, `zh` (+ `auto`). Target terjemahan: `en`, `id`.
  Jangan hardcode di banyak tempat; satu sumber kebenaran di `backend/app/languages.py`
  dan `frontend/src/lib/languages.ts` (nilainya harus sama).
- Jangan commit `.env`, `data/`, file model, atau video contoh besar.
- Jangan pernah mencetak API key ke log.
- Backend tidak boleh memblokir event loop: kerja berat (ffmpeg, whisper) di thread/proses terpisah.
- Semua jalur file harus lewat helper yang mencegah path traversal (`job_id` divalidasi UUID).
- Panggilan API Claude harus punya timeout, retry dengan backoff, dan validasi keluaran.

## Konvensi

**Backend (Python)**
- Python 3.11+, type hints wajib, `ruff` untuk lint/format, `pytest` untuk test.
- Pydantic v2 untuk skema. Modul kecil dan murni (tanpa efek samping) untuk logika inti
  (`segment.py`, `subtitle.py`) supaya mudah dites.
- Test tidak boleh memanggil API Claude sungguhan atau mengunduh model Whisper:
  pakai fake/mocking. Satu test integrasi opsional ditandai `@pytest.mark.slow`.

**Frontend (TypeScript)**
- React 18 + Vite + TypeScript strict + Tailwind. State server pakai TanStack Query.
- Tidak ada `any` tanpa alasan. Tipe API ada di `src/lib/types.ts` dan mengikuti `docs/API.md`.
- UI berbahasa Indonesia (label), kode dan komentar boleh Inggris.
- Responsif dan aksesibel (label form, fokus keyboard, kontras cukup).

**Git**: commit kecil per tugas, pesan format `feat(scope): ...`, `fix(scope): ...`, `test(scope): ...`.

## Definisi selesai (seluruh proyek)

- `pytest` hijau, `ruff check` bersih, `npm run build` dan `npm run lint` bersih.
- Alur end-to-end jalan: upload klip pendek → subtitle sumber → terjemahan → unduh SRT.
- README berisi cara menjalankan yang benar-benar sudah diuji.

## Perintah yang diharapkan ada

```bash
cd backend && pytest -q && ruff check .
cd frontend && npm run lint && npm run build
```
