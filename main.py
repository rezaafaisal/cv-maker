"""CV Maker – jalankan:  conda activate cv-maker && python main.py

Opsi:
  --port 5055        port server (default 5055; 5000 sering dipakai AirPlay di macOS)
  --no-browser       jangan buka browser otomatis
"""

import argparse
import threading
import webbrowser

from cvmaker.app import create_app


def main() -> None:
    ap = argparse.ArgumentParser(description="CV Maker (lokal)")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=5055)
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--debug", action="store_true", help="auto-reload saat kode berubah")
    args = ap.parse_args()

    url = f"http://{args.host}:{args.port}"
    if not args.no_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    print(f"\n  CV Maker berjalan di {url}  (Ctrl+C untuk berhenti)\n")
    create_app().run(host=args.host, port=args.port, debug=args.debug, use_reloader=args.debug)


if __name__ == "__main__":
    main()
