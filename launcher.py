import os
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = ROOT_DIR / "backend"
FRONTEND_DIR = ROOT_DIR / "frontend"
UVICORN_EXE = BACKEND_DIR / ".venv" / "Scripts" / "uvicorn.exe"

print("=" * 60)
print("                   AUTOSUB LAUNCHER")
print("=" * 60)
print()


def free_port(port: int) -> None:
    """Tutup proses lama yang masih menahan port jika ada."""
    try:
        res = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True,
            text=True,
            check=False,
        )
        for line in res.stdout.splitlines():
            if f":{port}" in line and "LISTENING" in line:
                parts = line.strip().split()
                pid = parts[-1]
                if pid and pid != "0" and int(pid) != os.getpid():
                    print(f"[INFO] Menutup proses lama (PID {pid}) pada port {port}...")
                    subprocess.run(
                        ["taskkill", "/F", "/PID", pid],
                        capture_output=True,
                        check=False,
                    )
    except Exception:
        pass


def kill_proc_tree(proc: subprocess.Popen | None) -> None:
    if proc and proc.poll() is None:
        try:
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                capture_output=True,
                check=False,
            )
        except Exception:
            try:
                proc.terminate()
            except Exception:
                pass


# 1. Bersihkan port jika ada server sebelumnya yang masih aktif
free_port(8000)
free_port(5173)

if not UVICORN_EXE.exists():
    print(f"[ERROR] uvicorn tidak ditemukan di {UVICORN_EXE}")
    print("Pastikan virtual environment telah dibuat di backend\\.venv")
    input("\nTekan Enter untuk keluar...")
    sys.exit(1)

# 2. Jalankan Backend
print("[1/2] Menjalankan Backend (FastAPI di http://127.0.0.1:8000)...")
backend_cmd = [
    str(UVICORN_EXE),
    "app.main:app",
    "--reload",
    "--host",
    "127.0.0.1",
    "--port",
    "8000",
]

backend_proc = subprocess.Popen(
    backend_cmd,
    cwd=str(BACKEND_DIR),
)

# 3. Jalankan Frontend
print("[2/2] Menjalankan Frontend (Vite di http://localhost:5173)...")
frontend_proc = subprocess.Popen(
    "npm run dev",
    cwd=str(FRONTEND_DIR),
    shell=True,
)

print()
print("=" * 60)
print(" AutoSub Berjalan di 1 Terminal Ini!")
print(" - Web UI     : http://localhost:5173")
print(" - Backend API: http://127.0.0.1:8000")
print(" - Swagger API: http://127.0.0.1:8000/docs")
print(" Tekan Ctrl+C untuk menghentikan kedua server.")
print("=" * 60)
print()

# 4. Buka browser otomatis setelah 3 detik
time.sleep(3)
try:
    webbrowser.open("http://localhost:5173")
except Exception:
    pass

# 5. Monitor kedua proses
try:
    while True:
        time.sleep(0.5)
        if backend_proc.poll() is not None:
            print(f"\n[INFO] Backend server berhenti (exit code {backend_proc.poll()}).")
            break
        if frontend_proc.poll() is not None:
            print(f"\n[INFO] Frontend server berhenti (exit code {frontend_proc.poll()}).")
            break
except KeyboardInterrupt:
    print("\n[INFO] Menghentikan semua layanan AutoSub...")
finally:
    kill_proc_tree(frontend_proc)
    kill_proc_tree(backend_proc)
    print("[OK] Semua layanan telah dihentikan dengan aman.")
