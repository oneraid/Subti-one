# Kontrak API

Base path `/api`. JSON UTF-8 kecuali dinyatakan lain. Waktu dalam detik (float).
Error seragam: `{"error": {"code": "string", "message": "string"}}` dengan status HTTP yang sesuai.

Kode bahasa: sumber `auto|id|en|zh`; target `en|id`.

## Meta

### `GET /api/health`
`200 {"status":"ok","ffmpeg":true,"whisper_model":"small","translator":"claude","translator_ready":true}`
(`translator_ready` = API key terisi.)

### `GET /api/config`
```json
{
  "source_languages": [{"code":"auto","label":"Otomatis"},{"code":"id","label":"Indonesia"},
                       {"code":"en","label":"English"},{"code":"zh","label":"中文"}],
  "target_languages": [{"code":"en","label":"English"},{"code":"id","label":"Indonesia"}],
  "whisper_models": ["tiny","base","small","medium","large-v3"],
  "default_model": "small",
  "max_upload_mb": 2048
}
```

## Job

### `POST /api/jobs` — `multipart/form-data`
| Field | Tipe | Wajib | Keterangan |
|---|---|---|---|
| `file` | file | ya | video/audio |
| `source_lang` | string | tidak (`auto`) | |
| `target_langs` | string | tidak | CSV, mis. `en,id`; kosong = tanpa terjemahan |
| `model_size` | string | tidak | salah satu `whisper_models` |
| `glossary` | string (JSON) | tidak | `{"istilah":"terjemahan"}` |

`201` → `Job` (status `queued`). Error: `413 file_too_large`, `415 unsupported_media`,
`422 invalid_option`.

### `GET /api/jobs` → `200 [Job]` (terbaru dulu)

### `GET /api/jobs/{id}` → `200 Job` | `404 not_found`
```json
{
  "id":"uuid","filename":"talk.mp4","status":"transcribing",
  "progress":0.42,"stage_progress":0.6,
  "source_lang_requested":"auto","source_lang_detected":"en",
  "target_langs":["id"],"model_size":"small","duration_sec":312.4,
  "available_langs":[],"warnings":[],"error":null,
  "created_at":"2026-10-12T13:40:00Z"
}
```

### `GET /api/jobs/{id}/events` — SSE (`text/event-stream`)
Event:
- `event: progress` `data: {Job}` setiap perubahan status / ≥1% progres
- `event: done` `data: {Job}` lalu stream ditutup
- `event: error` `data: {Job}` lalu stream ditutup
Kirim komentar `: keepalive` tiap 15 detik.

### `POST /api/jobs/{id}/cancel` → `200 Job` (status `cancelled`)
### `DELETE /api/jobs/{id}` → `204` (hapus file juga)

## Subtitle

### `GET /api/jobs/{id}/subtitles/{lang}` → `200`
```json
{"lang":"id","segments":[{"index":1,"start":0.5,"end":3.2,"text":"Halo semuanya"}]}
```
`404` bila bahasa itu belum tersedia.

### `PUT /api/jobs/{id}/subtitles/{lang}`
Body: `{"segments":[{index,start,end,text}]}`. Validasi: urut, tanpa tumpang tindih, `end>start`,
teks ≤ 2 baris. Menyimpan ulang `segments.<lang>.json` + `.srt`. `200` → isi baru.

### `GET /api/jobs/{id}/subtitles/{lang}/download?format=srt|vtt&bilingual=false`
`bilingual=true` → butuh bahasa sumber dan `{lang}` berbeda; cue = teks sumber di atas, terjemahan di bawah
(atau sebaliknya: `order=source_first|target_first`). `Content-Disposition: attachment; filename="<nama>.<lang>.srt"`.
Content-Type `application/x-subrip` / `text/vtt; charset=utf-8`.

### `POST /api/jobs/{id}/translate`
Body: `{"target_langs":["en"]}` — terjemahkan tambahan setelah job selesai (pakai segmen sumber terbaru,
termasuk hasil edit). `202` → `Job` (status `translating`).

## Media

### `GET /api/jobs/{id}/media` → stream file asli
Dukung `Range` (206) agar bisa di-seek di `<video>`.

### `POST /api/jobs/{id}/burn`
Body: `{"lang":"id"}` → `202 Job`; hasil di `GET /api/jobs/{id}/burned/{lang}` (`video/mp4`, Range didukung).
Job menambahkan `burned_langs: ["id"]` bila siap.

## Catatan implementasi

- Frontend `src/lib/types.ts` harus mencerminkan skema di atas persis.
- Tambahkan skema OpenAPI otomatis FastAPI; pastikan `/docs` menampilkan semua endpoint.
