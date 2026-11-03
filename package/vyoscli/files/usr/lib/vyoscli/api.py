"""Read-only HTTP API for vyoscli.

Started by ``service https`` (see config.py:_apply_https). Every request needs
``Authorization: Bearer <api-key>``; only GET is implemented, so the API can
never modify the candidate/running configuration.
"""

from __future__ import annotations

import argparse
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

VERSION = "0.1.0"


def _load(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _lookup(data: dict, dotted: str):
    cur = data
    for part in dotted.split("."):
        if not part:
            continue
        if isinstance(cur, dict):
            if part not in cur:
                raise KeyError(dotted)
            cur = cur[part]
        elif isinstance(cur, list):
            cur = cur[int(part)]
        else:
            raise KeyError(dotted)
    return cur


def make_handler(store_path: str, api_key: str):
    class Handler(BaseHTTPRequestHandler):
        server_version = "vyoscli/" + VERSION

        def _json(self, code: int, payload) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _authorized(self) -> bool:
            if not api_key:
                return False
            return self.headers.get("Authorization", "") == f"Bearer {api_key}"

        def do_GET(self) -> None:  # noqa: N802 (http.server API)
            if not self._authorized():
                self._json(401, {"error": "unauthorized"})
                return
            url = urlparse(self.path)
            running = _load(store_path)
            if url.path == "/api/version":
                self._json(200, {
                    "version": VERSION,
                    "hostname": ((running.get("system") or {}).get("host-name")
                                 or ""),
                })
            elif url.path == "/api/configuration":
                self._json(200, running)
            elif url.path == "/api/show":
                path = (parse_qs(url.query).get("path") or [""])[0]
                try:
                    self._json(200, {"path": path, "value": _lookup(running, path)})
                except (KeyError, IndexError, ValueError):
                    self._json(404, {"error": f"no such path: {path}"})
            else:
                self._json(404, {"error": "not found"})

        def log_message(self, *_args) -> None:
            pass

    return Handler


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="vyoscli-api")
    parser.add_argument("--bind", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8443)
    parser.add_argument("--key", required=True)
    parser.add_argument("--store", default="/etc/vyoscli/running.json")
    args = parser.parse_args(argv)
    server = ThreadingHTTPServer((args.bind, args.port),
                                 make_handler(args.store, args.key))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
