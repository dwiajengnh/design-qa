#!/usr/bin/env python3
"""Serve the Design QA form on localhost and wait for one submission.

Usage: python3 form_server.py [--timeout SECONDS] [--no-open]

Opens form.html in the default browser at http://127.0.0.1:<port>/<secret>/ and
blocks until the user clicks Start QA. Then prints one JSON line to stdout:
  {"staging": ..., "figma_desktop": ..., "figma_mobile": ..., "notion": ...}
and exits 0. Exits 2 on timeout.

Safety: listens on 127.0.0.1 only, the form lives under a random one-time path,
it accepts a single submission, and it only accepts the four expected links
(staging http(s) URL, figma.com/design links with node-id, a notion link).
Nothing it receives is run as a command; it is printed as data.
"""
import json, os, re, secrets, socket, sys, threading, webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
FORM = os.path.join(os.path.dirname(HERE), 'form.html')
PREFERRED_PORT = 47321  # fixed so the browser remembers the saved Notion link between runs
TOKEN = secrets.token_urlsafe(16)

FIGMA = re.compile(r'^https://(www\.)?figma\.com/design/[^/\s]+/\S*node-id=\d+-\d+\S*$', re.I)
NOTION = re.compile(r'^https://([a-z0-9-]+\.)?notion\.(so|com|site)/\S+$', re.I)
HTTP = re.compile(r'^https?://[^\s]+$', re.I)

result = {}
done = threading.Event()


def valid(d):
    if not isinstance(d, dict):
        return 'bad request'
    checks = [('staging', HTTP), ('figma_desktop', FIGMA), ('figma_mobile', FIGMA), ('notion', NOTION)]
    for key, rx in checks:
        v = d.get(key)
        if not isinstance(v, str) or len(v) > 2000 or not rx.match(v.strip()):
            return f'invalid {key}'
    return None


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype='text/plain; charset=utf-8'):
        b = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(b)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        if self.path.split('?')[0] in (f'/{TOKEN}/', f'/{TOKEN}'):
            with open(FORM, 'rb') as f:
                return self._send(200, f.read(), 'text/html; charset=utf-8')
        self._send(404, 'not found')

    def do_POST(self):
        if self.path != f'/{TOKEN}/submit' or done.is_set():
            return self._send(404, 'not found')
        origin = self.headers.get('Origin', '')
        if origin and not origin.startswith(f'http://127.0.0.1:{self.server.server_port}'):
            return self._send(403, 'forbidden')
        try:
            n = min(int(self.headers.get('Content-Length', '0')), 20000)
            data = json.loads(self.rfile.read(n) or b'{}')
        except Exception:
            return self._send(400, 'bad request')
        err = valid(data)
        if err:
            return self._send(400, err)
        result.update({k: data[k].strip() for k in ('staging', 'figma_desktop', 'figma_mobile', 'notion')})
        self._send(200, 'ok')
        done.set()


def make_server():
    for port in (PREFERRED_PORT, 0):
        try:
            return HTTPServer(('127.0.0.1', port), Handler)
        except OSError:
            continue
    raise SystemExit('could not start local server')


def main():
    timeout = 1800
    if '--timeout' in sys.argv:
        timeout = int(sys.argv[sys.argv.index('--timeout') + 1])
    srv = make_server()
    url = f'http://127.0.0.1:{srv.server_port}/{TOKEN}/'
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    print(f'FORM_URL {url}', file=sys.stderr, flush=True)
    if '--no-open' not in sys.argv:
        webbrowser.open(url)
    if not done.wait(timeout):
        print('TIMEOUT no submission', file=sys.stderr)
        srv.shutdown()
        sys.exit(2)
    srv.shutdown()
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
