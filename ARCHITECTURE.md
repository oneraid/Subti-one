# Arsitektur AutoSub

## 1. Struktur proyek

```
autosub/
├── README.md
├── CLAUDE.md
├── .env.example
├── docs/
├── backend/
│   ├── pyproject.toml
│   ├── app/
│   │   ├── main.py            # FastAPI app, CORS, router, lifespan (cleanup job lama)
│   │   ├── config.py          # Settings (pydantic-settings, baca .env)
│   │   ├── languages.py       # Sumber kebenaran bahasa: STT {auto,id,en,zh}, target {en,id}
│   │   ├── models.py          # Pydantic: Segment, Job, JobStatus, request/response
│   │   ├── storage.py         # Folder job, path aman, baca/tulis meta.json & segmen
│   │   ├── jobs.py            # JobManager: antrean, worker, progress, event pub/sub
│   │   ├── pipeline.py        # Orkestrasi: audio → transcribe → segment → translate → output
│   │   ├── audio.py           # ffmpeg: ekstrak WAV, probe durasi, burn-in
│   │   ├── transcribe.py      # Wrapper faster-whisper (lazy load model, progress callback)
│   │   ├── segment.py         # Segmentasi ulang jadi cue (fungsi murni)
│   │   ├── subtitle.py        # Parse/tulis SRT & VTT, gabung dwibahasa (fungsi murni)
│   │   ├── translate/
│   │   │   ├── base.py        # Protocol Translator
│   │   │   ├── claude.py      # Implementasi Claude API
│   │   │   └── batching.py    # Pembagian batch + konteks, validasi keluaran
│   │   └── routers/
│   │       ├── jobs.py        # /api/jobs...
│   │       └── meta.py        # /api/health, /api/config
│   └── tests/
│       ├── test_segment.py
│       ├── test_subtitle.py
│       ├── test_batching.py
│       ├── test_translate_claude.py   # mock SDK
│       ├── test_pipeline.py           # fake transcriber + fake translator
│       └── test_api.py
├── frontend/
│   ├── package.json  vite.config.ts  tailwind.config.ts  tsconfig.json
│   └── src/
│       ├── main.tsx  App.tsx
│       ├── lib/ { api.ts, types.ts, languages.ts, srt.ts, format.ts }
│       ├── hooks/ { useJob.ts (polling + SSE), useUpload.ts }
│       ├── pages/ { HomePage.tsx, JobPage.tsx }
│       └── components/
│           ├── UploadForm.tsx        # drop file, pilih bahasa sumber & target, ukuran model
│           ├── ProgressTimeline.tsx  # tahap pipeline + persen
│           ├── VideoPreview.tsx      # <video> + <track> dari VTT blob, pilih track
│           ├── SegmentEditor.tsx     # tabel cue: waktu + teks sumber + teks terjemahan, edit inline
│           ├── DownloadMenu.tsx      # SRT/VTT per bahasa, dwibahasa, video burn-in
│           └── JobList.tsx           # riwayat job (dari API)
└── data/                      # runtime, di-.gitignore
    ├── models/                # cache model whisper
    └── jobs/<job_id>/
        ├── meta.json          # status, opsi, tahap, error
        ├── input.<ext>        # file asli
        ├── audio.wav
        ├── segments.<lang>.json
        ├── subtitle.<lang>.srt
        └── burned.<lang>.mp4  # opsional
```

## 2. Model data

```python
class Segment(BaseModel):
    index: int            # 1-based, berurutan
    start: float          # detik
    end: float            # detik
    text: str             # boleh mengandung "\n" (maks 2 baris)

class JobStatus(str, Enum):
    queued, extracting_audio, transcribing, segmenting, translating, done, failed, cancelled

class Job(BaseModel):
    id: UUID
    filename: str
    status: JobStatus
    stage_progress: float          # 0..1 untuk tahap berjalan
    progress: float                # 0..1 total (bobot di bawah)
    source_lang_requested: Literal["auto","id","en","zh"]
    source_lang_detected: str | None
    target_langs: list[Literal["en","id"]]
    model_size: str
    duration_sec: float | None
    available_langs: list[str]     # bahasa yang subtitle-nya sudah siap
    error: str | None
    created_at: datetime
```

Bobot progres total: extracting 5%, transcribing 60%, segmenting 2%, translating 33%
(dibagi rata per bahasa target). Tanpa terjemahan: transcribing 93%.

## 3. Pipeline (`pipeline.py`)

1. **audio.py** — `ffmpeg -i input -vn -ac 1 -ar 16000 -c:a pcm_s16le audio.wav`.
   Probe durasi dengan `ffprobe`. Gagal bila tidak ada stream audio → error jelas.
2. **transcribe.py** — `faster_whisper.WhisperModel` (lazy singleton per `model_size`).
   - `language=None` bila `auto`, selain itu kode `id|en|zh`.
   - `word_timestamps=True`, `vad_filter=True` (`min_silence_duration_ms=500`),
     `condition_on_previous_text=False` (kurangi halusinasi berulang), `beam_size=5`.
   - Progress = `segment.end / duration`.
   - Output: daftar kata `(start, end, word)` + bahasa terdeteksi + probabilitasnya.
   - Jika bahasa terdeteksi di luar `{id,en,zh}` → pakai kandidat terbaik di antara tiga itu
     (jalankan ulang dengan bahasa itu bila probabilitas rendah), atau gagal dengan pesan
     "Bahasa tidak didukung" bila yang terdeteksi jelas lain. Tentukan perilaku dan catat di "Catatan keputusan".
3. **segment.py** — ubah kata → cue (lihat §4).
4. Simpan `segments.<src>.json` dan `subtitle.<src>.srt`. Status `available_langs` bertambah.
5. **translate** — untuk tiap target ≠ bahasa sumber: terjemahkan (lihat §5), simpan
   `segments.<tgt>.json` + `subtitle.<tgt>.srt`. Jika target == bahasa sumber → lewati.
6. Status `done`. Kegagalan terjemahan **tidak** menghapus subtitle sumber: job tetap
   dapat dipakai; `error` diisi dan status `failed` hanya jika sumber pun gagal. Untuk
   kegagalan terjemahan saja, pakai status `done` dengan field `warnings`.

Pembatalan: `POST /cancel` men-set flag; pipeline mengecek antar-segmen/antar-batch.

## 4. Segmentasi (aturan baku, fungsi murni + test)

Input: daftar kata berwaktu. Output: cue.

| Parameter | Latin (en, id) | CJK (zh) |
|---|---|---|
| Maks karakter per baris | 42 | 16 |
| Maks baris per cue | 2 | 2 |
| Maks durasi cue | 7.0 s | 7.0 s |
| Min durasi cue | 1.0 s (perpanjang bila ada ruang) | 1.0 s |
| Target kecepatan baca (CPS) | ≤ 17 | ≤ 9 |
| Jeda ≥ 0.8 s antar kata | paksa potong cue | sama |

Aturan:
1. Potong di akhir kalimat (`. ? ! 。？！`) bila cue sudah ≥ ~1.5 s.
2. Bila melebihi batas, potong di koma/jeda/konjungsi terdekat sebelum batas; terakhir
   baru potong di batas kata. Untuk `zh` potong di tanda baca CJK (`，、；`) atau antar karakter.
3. Bagi teks cue menjadi ≤ 2 baris seimbang (selisih panjang baris minimal).
4. Cue tidak boleh saling tumpang tindih; `end` ≤ `start` cue berikutnya.
5. Teks Mandarin: tanpa spasi antar karakter; normalisasi ke satu varian aksara
   (default: ikuti keluaran Whisper; jangan konversi otomatis).
6. Buang cue kosong / hanya tanda baca; buang pengulangan halusinasi (cue identik ≥ 3 kali berturut-turut).

## 5. Terjemahan

### Antarmuka
```python
class Translator(Protocol):
    async def translate(
        self, segments: list[Segment], source: str, target: str,
        glossary: dict[str, str] | None, on_progress: Callable[[float], None],
    ) -> list[Segment]: ...   # jumlah & timestamp SAMA dengan input
```
Hanya `ClaudeTranslator` yang wajib. Backend lain di luar cakupan awal, tetapi antarmuka
harus memungkinkan.

### Strategi batch (`batching.py`)
- Batch ±40 cue (atau ≤ ~3000 karakter), plus **konteks**: 5 cue sebelum dan 5 sesudah
  (hanya dibaca, tidak diterjemahkan).
- Kirim sebagai JSON: `{"context_before":[...], "items":[{"id":1,"text":"..."}], "context_after":[...]}`.
- Minta keluaran **JSON saja**: `{"items":[{"id":1,"text":"..."}]}`. Gunakan tool use /
  structured output milik SDK bila tersedia agar skema dipaksa; jika tidak, parse JSON
  dengan toleransi (buang code fence).
- **Validasi**: set `id` keluaran harus sama persis dengan masukan; tidak ada teks kosong
  untuk masukan tak kosong. Gagal → retry (maks 3, backoff eksponensial). Masih gagal →
  bagi batch jadi dua dan ulangi; untuk batch 1 cue yang tetap gagal, pakai teks sumber
  dan tambahkan ke `warnings`.
- Pertahankan jumlah baris maksimal 2 per cue: bila hasil terjemahan > batas karakter/baris,
  bungkus ulang dengan fungsi `wrap_lines()` yang sama dengan segmentasi (jangan ubah waktu).
- Konkurensi: maks 3 batch paralel; urutan hasil dipertahankan.

### Prompt sistem (inti, boleh disempurnakan)
```
Kamu penerjemah subtitle profesional. Terjemahkan dari {source_name} ke {target_name}.
Aturan:
- Terjemahkan makna dan nada ujaran, bukan kata per kata; hasil harus terdengar alami
  seperti ucapan lisan.
- Satu item masukan menghasilkan tepat satu item keluaran dengan id yang sama.
  Jangan menggabung, memecah, menambah, atau menghapus item.
- Singkat dan padat: subtitle dibaca cepat. Hindari penjelasan.
- Pertahankan nama orang, merek, dan istilah teknis; ikuti glosarium bila ada.
- Pertahankan tanda baca penting dan "\n" bila relevan; jangan menambahkan tag atau catatan.
- context_before/context_after hanya untuk memahami alur; JANGAN diterjemahkan.
- Bahasa Indonesia: baku-santai, natural (bukan terlalu kaku). Mandarin → gunakan nama
  dan istilah umum; jangan sertakan pinyin.
Keluarkan hanya JSON sesuai skema.
```

### Pasangan bahasa yang valid
`zh→en, zh→id, en→id, id→en`. Target sama dengan sumber dilewati. Bila bahasa terdeteksi
`en` dan target diminta `en,id` → hanya `id` yang diterjemahkan.
Terjemahan `zh→id` boleh langsung (tanpa pivot via Inggris).

## 6. Manajemen job (`jobs.py`)

- `asyncio.Queue` + worker task sejumlah `MAX_CONCURRENT_JOBS`. Kerja sinkron berat lewat
  `asyncio.to_thread`.
- Status dipersist di `meta.json` (tulis atomik: tulis temp lalu rename) → job selamat dari
  restart. Saat startup, job berstatus berjalan ditandai `failed` ("Dihentikan karena server restart")
  atau diantrekan ulang (pilih satu, catat keputusan).
- Event progres via pub/sub in-memory → endpoint SSE. Frontend juga boleh polling `GET /jobs/{id}`
  sebagai fallback.
- Pembersihan: background task periodik menghapus folder job lebih tua dari `FILE_RETENTION_HOURS`.

## 7. Keamanan & validasi

- Validasi upload: ekstensi + `ffprobe` benar-benar media; batas `MAX_UPLOAD_MB` (stream ke disk,
  jangan load penuh ke memori).
- `job_id` UUID; path dibangun lewat `storage.job_dir(job_id)` yang memverifikasi hasil resolve
  ada di bawah `DATA_DIR`.
- Subprocess ffmpeg: pakai list argumen (tanpa `shell=True`); nama file input disanitasi
  (disimpan sebagai `input.<ext>`, nama asli hanya di metadata).
- CORS hanya `CORS_ORIGINS`. Tidak ada autentikasi (aplikasi lokal/personal) — catat di README
  bahwa tidak untuk diekspos publik tanpa auth.
- Jangan log isi subtitle penuh pada level INFO; jangan log API key.

## 8. Frontend

- **HomePage**: `UploadForm` (drag & drop, validasi tipe/ukuran sisi klien, pilihan bahasa sumber
  `Otomatis/Indonesia/English/中文`, target `English`/`Indonesia` (multi), ukuran model,
  toggle burn-in) + `JobList` riwayat.
- **JobPage** (`/jobs/:id`): `ProgressTimeline` (SSE, fallback polling) → saat sumber siap tampilkan
  `VideoPreview` + `SegmentEditor`. Saat terjemahan selesai muncul tab bahasa tambahan.
- **SegmentEditor**: tabel virtualisasi bila > 500 baris; klik baris → loncat ke waktu di video;
  edit teks inline lalu simpan via `PUT`; indikator pelanggaran (baris > batas karakter, CPS tinggi).
- **VideoPreview**: konversi segmen → VTT blob → `<track>`; ganti track tanpa reload video.
- **DownloadMenu**: SRT / VTT per bahasa, SRT dwibahasa (sumber + terjemahan), video burn-in
  bila dibuat.
- Dev: Vite proxy `/api` → `http://localhost:8000`. Prod: `npm run build` lalu backend bisa
  menyajikan `frontend/dist` sebagai static (opsional, fase akhir).
- Desain: bersih, fokus alur kerja; gunakan skill `frontend-design` bila tersedia.

## 9. Fitur burn-in (opsional, fase akhir)

`ffmpeg -i input -vf "subtitles=subtitle.<lang>.srt:force_style='FontName=...,FontSize=22,Outline=2'" -c:a copy burned.<lang>.mp4`.
Untuk `zh` pastikan font CJK tersedia (mis. Noto Sans CJK) dan beri pesan jelas jika tidak ada.
Dijalankan sebagai tahap terpisah dan dapat dibatalkan.

## 10. Di luar cakupan (jangan dikerjakan)

Autentikasi/multi-user, pembayaran, diarization pembicara, subtitle live/streaming mikrofon,
backend terjemahan selain Claude, bahasa selain `id/en/zh`, deployment cloud/Docker (boleh
ditambahkan terakhir hanya bila diminta).

## 11. Catatan keputusan

_(Agent: tambahkan keputusan yang diambil saat implementasi di sini, format: tanggal — keputusan — alasan.)_
