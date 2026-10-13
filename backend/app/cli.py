import argparse
import sys
from pathlib import Path

from app.audio import extract_audio, probe_media
from app.segment import segment_words
from app.subtitle import segments_to_srt
from app.transcribe import FasterWhisperTranscriber


def main():
    parser = argparse.ArgumentParser(description="AutoSub CLI tool")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Subcommand: transcribe
    transcribe_parser = subparsers.add_parser("transcribe", help="Transcribe media file to SRT")
    transcribe_parser.add_argument("file", type=str, help="Path to input audio/video file")
    transcribe_parser.add_argument(
        "--lang", default="auto", help="Source language (auto, id, en, zh)"
    )
    transcribe_parser.add_argument("--model", default="small", help="Whisper model size")
    transcribe_parser.add_argument("--out", default=None, help="Output SRT filepath")

    args = parser.parse_args()

    if args.command == "transcribe":
        input_file = Path(args.file)
        if not input_file.exists():
            print(f"Error: File tidak ditemukan: {input_file}", file=sys.stderr)
            sys.exit(1)

        print(f"Memeriksa media: {input_file}...")
        probe = probe_media(input_file)
        duration = probe.get("duration", 0.0)
        print(f"Durasi media: {duration:.2f} detik")

        wav_path = input_file.with_suffix(".tmp.wav")
        try:
            print("Mengekstrak audio WAV...")
            extract_audio(input_file, wav_path)

            print(
                f"Mentranskripsi dengan Faster-Whisper (model: {args.model}, lang: {args.lang})..."
            )
            transcriber = FasterWhisperTranscriber()

            def progress_callback(p: float):
                sys.stdout.write(f"\rProgres transkripsi: {int(p * 100)}%")
                sys.stdout.flush()

            words, detected_lang, prob = transcriber.transcribe(
                wav_path,
                source_lang=args.lang,
                model_size=args.model,
                duration=duration,
                on_progress=progress_callback,
            )
            print()
            print(f"Bahasa terdeteksi: {detected_lang} (probabilitas: {prob:.2f})")
            print(f"Total kata terdeteksi: {len(words)}")

            print("Menyusun segmen subtitle...")
            segments = segment_words(words, lang=detected_lang)
            srt_output = segments_to_srt(segments)

            default_out = input_file.with_suffix(f".{detected_lang}.srt")
            out_path = Path(args.out) if args.out else default_out
            out_path.write_text(srt_output, encoding="utf-8")
            print(f"Subtitle berhasil disimpan ke: {out_path} ({len(segments)} cue)")
        finally:
            if wav_path.exists():
                wav_path.unlink()


if __name__ == "__main__":
    main()
