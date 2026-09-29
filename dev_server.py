"""
Run the player backend without a desktop window (for development / browser testing).

    python dev_server.py            # http://127.0.0.1:8765/
    python dev_server.py --port 9000

Native file dialogs are unavailable in this mode; the UI falls back to browser pickers.
"""
import argparse
import os
import sys
import threading
import types

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)

# Stub pywebview if it is not installed (e.g. Linux CI). app.py only needs the names at import time.
try:
    import webview  # noqa: F401
except Exception:
    stub = types.ModuleType("webview")
    stub.OPEN_DIALOG = 10
    stub.FOLDER_DIALOG = 20
    stub.settings = {}
    stub.create_window = lambda *a, **k: None
    stub.start = lambda *a, **k: None
    sys.modules["webview"] = stub

parser = argparse.ArgumentParser()
parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8765")))
args = parser.parse_args()
os.environ["MODERNPLAYER_PORT"] = str(args.port)

import app as player  # noqa: E402

player.PORT = args.port
player._BridgeHelpers.PORT = args.port
api = player.PlayerAPI()
player.API_INSTANCE = api
player._init_services(api)
print(f"[dev] serving http://127.0.0.1:{args.port}/  (no desktop window)")
t = threading.Thread(target=player.run_server, daemon=True)
t.start()
try:
    t.join()
except KeyboardInterrupt:
    pass
