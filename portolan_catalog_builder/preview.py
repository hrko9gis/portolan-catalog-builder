"""Loopback-only preview server with byte-range support."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import secrets
import threading
from urllib.parse import unquote, urlsplit

class Handler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def translate_path(self, path):
        url = unquote(urlsplit(path).path)
        if not url.startswith('/' + self.server.token + '/'):
            return str(self.server.root / '__not_found__')
        relative = url[len(self.server.token) + 2:]
        base = self.server.root
        if relative.startswith('_app/'):
            base = Path(__file__).parent / 'preview'
            relative = relative[5:]
        target = (base / relative).resolve()
        if not target.is_relative_to(base.resolve()):
            return str(base / '__not_found__')
        return str(target)

    def list_directory(self, path):
        self.send_error(403)
        return None

    def send_head(self):
        self.byte_range = None
        target = Path(self.translate_path(self.path))
        if not target.is_file():
            self.send_error(404)
            return None
        size = target.stat().st_size
        start, end = 0, size - 1
        value = self.headers.get('Range')
        if value:
            match = re.fullmatch(r'bytes=(\d*)-(\d*)', value)
            if not match or not any(match.groups()):
                self.send_error(416)
                return None
            first, last = match.groups()
            if not first:
                start = max(0, size - int(last))
            else:
                start = int(first)
                end = min(size - 1, int(last)) if last else size - 1
            if start >= size or start > end:
                self.send_response(416)
                self.send_header('Content-Range', f'bytes */{size}')
                self.end_headers()
                return None
            self.byte_range = (start, end)
        self.send_response(206 if value else 200)
        self.send_header('Content-Type', self.guess_type(str(target)))
        self.send_header('Content-Length', str(end - start + 1))
        self.send_header('Accept-Ranges', 'bytes')
        self.send_header('Cache-Control', 'no-store')
        if value:
            self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
        self.end_headers()
        stream = target.open('rb')
        stream.seek(start)
        return stream

    def copyfile(self, source, outputfile):
        remaining = self.byte_range[1] - self.byte_range[0] + 1 if self.byte_range else None
        try:
            while remaining is None or remaining > 0:
                data = source.read(min(65536, remaining) if remaining is not None else 65536)
                if not data:
                    break
                outputfile.write(data)
                if remaining is not None:
                    remaining -= len(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

class PreviewServer:
    def __init__(self, root):
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.server.daemon_threads = True
        self.server.root = Path(root).resolve()
        self.server.token = secrets.token_urlsafe(24)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def url(self, collection, lang='en'):
        from urllib.parse import urlencode
        port = self.server.server_address[1]
        return f'http://127.0.0.1:{port}/{self.server.token}/_app/index.html?' + urlencode({'collection': collection, 'lang': lang})

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

