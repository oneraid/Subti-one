# AutoSub 🎬

Aplikasi web modern untuk **auto subtitle** (speech-to-text) dan **auto translate subtitle** berbasis AI.

- 🎙️ **Speech-to-text**: Indonesia (`id`), Inggris (`en`), Mandarin (`zh`), dengan deteksi bahasa otomatis menggunakan **faster-whisper**.
- 🌐 **Terjemahan Subtitle**: Terjemahan otomatis ke Inggris (`en`) dan Indonesia (`id`) menggunakan **Google Translate** (Gratis, default tanpa API key) atau **Claude API** (opsional berkonteks).
- ⚡ **Backend**: Python 3.11+, FastAPI, Faster-Whisper, FFmpeg, Async Worker Queue, Server-Sent Events (SSE).
- 🎨 **Frontend**: React 18, TypeScript, Vite, Tailwind CSS, TanStack Query, Lucide Icons.
- 📺 **Fitur Video**: Streaming HTTP 206 Range, preview subtitle WebVTT langsung di pemutar, editor segmen interaktif, dan hardcode burn-in subtitle ke video.

---

## 🚀 Fitur Unggulan

1. **Segmentasi Cerdas**: Mengonversi timestamp per kata dari Whisper menjadi cue subtitle yang nyaman dibaca sesuai standar broadcast (Latin ≤ 42 karakter/baris, CJK ≤ 16 karakter/baris, maksimal 2 baris).
2. **Terjemahan Kontekstual Berkelompok**: Membagi subtitle ke dalam batch (≤ 40 cue / 3000 karakter) dengan konteks 5 kalimat sebelum & sesudah agar hasil terjemahan tetap padu dan alami.
3. **Format Unduhan Lengkap**: Mendukung unduhan format `.srt` dan `.vtt`, baik satu bahasa maupun dwibahasa (*bilingual* sumber & target).
4. **Editor Subtitle Interaktif**: Klik segmen subtitle untuk langsung melompat ke detik video terkait, lakukan koreksi teks secara langsung, dan simpan perubahan secara instan.
5. **Burn-in Subtitle**: Membakar subtitle langsung ke dalam video MP4 dengan styling kontras tinggi yang siap diputar di perangkat apa pun.
6. **Pemantauan Real-Time**: Status dan persentase proses pemrosesan disiarkan langsung melalui Server-Sent Events (SSE).

---

## 🛠️ Prasyarat Sistem

1. **Python 3.11+**
2. **Node.js 20+** dan **npm**
3. **FFmpeg**: Terpasang di sistem dan terdaftar di `PATH`.
   - Windows: `winget install Gyan.FFmpeg` atau unduh dari `ffmpeg.org`.
   - Linux: `sudo apt install ffmpeg`
   - macOS: `brew install ffmpeg`
4. **API Key Anthropic (Opsional)**: Untuk fitur terjemahan otomatis.

---

## 📦 Panduan Instalasi & Menjalankan

### Cara Cepat (Windows) — Sekali Klik:
Cukup klik ganda (double-click) file **`run.bat`** (atau jalankan `run.bat` dari terminal).
Skrip ini akan secara otomatis:
1. Memeriksa file `.env` (membuat dari contoh bila belum ada).
2. Menjalankan Backend FastAPI di port 8000.
3. Menjalankan Frontend Vite di port 5173.
4. Membuka browser ke `http://localhost:5173`.

---

### Cara Manual:

### 1. Salin Konfigurasi Lingkungan
```bash
cp .env.example .env
```
Buka file `.env` dan tambahkan `ANTHROPIC_API_KEY` Anda jika ingin mengaktifkan fitur terjemahan Claude.

### 2. Menjalankan Backend (FastAPI)
```bash
cd backend

# Buat virtual environment
python -m venv .venv

# Aktifkan virtual environment
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# Windows (CMD):
.venv\Scripts\activate.bat
# Linux/macOS:
source .venv/bin/activate

# Install dependensi
pip install -e ".[dev]"

# Jalankan server API
uvicorn app.main:app --reload --port 8000
```
Server backend akan aktif di: `http://localhost:8000` (Dokumentasi API Swagger di `/docs`).

### 3. Menjalankan Frontend (Vite + React)
Buka terminal baru:
```bash
cd frontend

# Install dependensi
npm install

# Jalankan development server
npm run dev
```
Buka browser Anda di `http://localhost:5173`.

---

## 🧪 Pengujian & Verifikasi

Proyek dilengkapi dengan pengujian unit dan integrasi komprehensif tanpa memerlukan panggilan jaringan eksternal:

```bash
# Menjalankan pengujian backend (41 unit & integration tests)
cd backend
.venv\Scripts\python -m pytest -v

# Pemeriksaan linter backend
.venv\Scripts\python -m ruff check .

# Build frontend production bundle
cd ../frontend
npm run build
```

---

## 📊 Rekomendasi Model Whisper

| Model | Kecepatan | Kebutuhan RAM / VRAM | Rekomendasi Penggunaan |
|---|---|---|---|
| `tiny` | Sangat Cepat | ~1 GB | Pengujian lokal cepat & perangkat terbatas |
| `base` | Cepat | ~1.5 GB | Rekaman audio jernih |
| `small` (Default) | Seimbang | ~2 GB | Keseimbangan terbaik antara akurasi dan kecepatan CPU/GPU |
| `medium` | Sedang | ~5 GB | Konten multi-aksen / audio dengan kebisingan latar belakang |
| `large-v3` | Akurasi Tertinggi | ~10 GB | Produksi profesional dengan GPU Nvidia CUDA |

---

## 🔒 Catatan Keamanan

- **Akses Lokal / Single-tenant**: Aplikasi dirancang untuk penggunaan lokal atau internal. Tidak ada sistem multi-user atau autentikasi akun.
- **Keamanan File**: Akses file divalidasi dengan format UUID dan batasan direktori kerja (`DATA_DIR`) untuk mencegah kerentanan *path traversal*.
- **Retensi File**: Job dan file media lama dibersihkan secara otomatis berdasarkan konfigurasi `FILE_RETENTION_HOURS` di `.env`.

---

## 📄 Lisensi
MIT License.
