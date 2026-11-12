#!/usr/bin/env python3
"""Serve the Design QA form on localhost, wait for one submission, then show progress.

Usage: python3 form_server.py [--timeout SECONDS] [--no-open]
       python3 form_server.py --again   # after a QA is done: let the same open page start the next QA

Opens form.html in the default browser at http://127.0.0.1:<port>/<secret>/ and
blocks until the user clicks Start QA. Then it:
  1. starts a detached progress server on the same address (so the page can keep
     showing what Claude is doing; Claude reports with qa_status.py), and
  2. prints one JSON line to stdout and exits 0:
     {"staging": ..., "figma_desktop": ..., "figma_mobile": ..., "notion": ...}
Exits 2 on timeout.

--again takes over the port and secret path of the last form (saved in
~/.design-qa/session.json), stops its progress server, and waits for the next
submission from the page that is still open. It doesn't open a new browser tab.

Safety: listens on 127.0.0.1 only, the page lives under a random one-time path,
it accepts a single submission, and it only accepts the four expected links
(staging http(s) URL, figma.com/design links with node-id, a notion link).
Nothing it receives is run as a command; it is printed as data.
"""
import json, os, re, secrets, subprocess, sys, threading, time, webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
FORM = os.path.join(os.path.dirname(HERE), 'form.html')
STATUS = os.path.expanduser('~/.design-qa/status.json')
SESSION = os.path.expanduser('~/.design-qa/session.json')
HANDOVER = os.path.expanduser('~/.design-qa/handover')
PREFERRED_PORT = 47321  # fixed so the browser remembers the saved Notion link between runs

FIGMA = re.compile(r'^https://(www\.)?figma\.com/design/[^/\s]+/\S*node-id=\d+-\d+\S*$', re.I)
NOTION = re.compile(r'^https://([a-z0-9-]+\.)?notion\.(so|com|site)/\S+$', re.I)
HTTP = re.compile(r'^https?://[^\s]+$', re.I)
KEYS = ('staging', 'figma_desktop', 'figma_mobile', 'notion')

args = sys.argv[1:]
PROGRESS_MODE = '--progress' in args
AGAIN = '--again' in args
_session = {}
if AGAIN:
    try:
        with open(SESSION) as f:
            _session = json.load(f)
    except Exception:
        raise SystemExit('no earlier form to reuse; run without --again')
TOKEN = args[args.index('--token') + 1] if '--token' in args else _session.get('token') or secrets.token_urlsafe(16)

result = {}
done = threading.Event()


def valid(d):
    if not isinstance(d, dict):
        return 'bad request'
    for key, rx in (('staging', HTTP), ('figma_desktop', FIGMA), ('figma_mobile', FIGMA), ('notion', NOTION)):
        v = d.get(key)
        if not isinstance(v, str) or len(v) > 2000 or not rx.match(v.strip()):
            return f'invalid {key}'
    return None


def read_status():
    try:
        with open(STATUS) as f:
            return json.load(f)
    except Exception:
        return {'state': 'idle'}


def write_status(s):
    os.makedirs(os.path.dirname(STATUS), exist_ok=True)
    s['updated'] = time.time()
    with open(STATUS + '.tmp', 'w') as f:
        json.dump(s, f)
    os.replace(STATUS + '.tmp', STATUS)


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
        p = self.path.split('?')[0]
        if p in (f'/{TOKEN}/', f'/{TOKEN}'):
            with open(FORM, 'rb') as f:
                return self._send(200, f.read(), 'text/html; charset=utf-8')
        if p == f'/{TOKEN}/status':
            s = read_status() if (PROGRESS_MODE or AGAIN or done.is_set()) else {'state': 'idle'}
            return self._send(200, json.dumps(s), 'application/json')
        self._send(404, 'not found')

    def do_POST(self):
        if self.path != f'/{TOKEN}/submit':
            return self._send(404, 'not found')
        if PROGRESS_MODE or done.is_set():
            return self._send(409, 'already running')
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
        result.update({k: data[k].strip() for k in KEYS})
        write_status({'state': 'running', 'step': 0, 'message': 'Starting', 'started': time.time(), 'log': []})
        self._send(200, 'ok')
        done.set()


def bind(port, tries=1):
    for i in range(tries):
        try:
            return HTTPServer(('127.0.0.1', port), Handler)
        except OSError:
            time.sleep(0.1)
    return None


def progress_main():
    """Detached: keep serving the page + status until the QA ends (or 4 hours)."""
    port = int(args[args.index('--port') + 1])
    srv = bind(port, tries=50)
    if not srv:
        return
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    start, end_seen = time.time(), None
    while time.time() - start < 4 * 3600:
        time.sleep(0.5)
        if os.path.exists(HANDOVER):  # a --again server wants this port
            try:
                os.remove(HANDOVER)
            except OSError:
                pass
            break
        st = read_status().get('state')
        if st in ('done', 'error'):
            end_seen = end_seen or time.time()
            if time.time() - end_seen > 600:  # keep the result visible for 10 minutes
                break
    srv.shutdown()


def main():
    if PROGRESS_MODE:
        return progress_main()
    timeout = int(args[args.index('--timeout') + 1]) if '--timeout' in args else 1800
    if AGAIN:
        os.makedirs(os.path.dirname(HANDOVER), exist_ok=True)
        open(HANDOVER, 'w').close()
        srv = bind(int(_session['port']), tries=100)
        if os.path.exists(HANDOVER):
            os.remove(HANDOVER)
    else:
        srv = bind(PREFERRED_PORT) or bind(0)
    if not srv:
        raise SystemExit('could not start local server')
    port = srv.server_port
    url = f'http://127.0.0.1:{port}/{TOKEN}/'
    os.makedirs(os.path.dirname(SESSION), exist_ok=True)
    with open(SESSION, 'w') as f:
        json.dump({'port': port, 'token': TOKEN}, f)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    print(f'FORM_URL {url}', file=sys.stderr, flush=True)
    if '--no-open' not in args and not AGAIN:
        webbrowser.open(url)
    if not done.wait(timeout):
        print('TIMEOUT no submission', file=sys.stderr)
        srv.shutdown()
        sys.exit(2)
    time.sleep(0.2)  # let the response reach the browser
    srv.shutdown()
    srv.server_close()
    subprocess.Popen([sys.executable, os.path.abspath(__file__), '--progress', '--port', str(port), '--token', TOKEN],
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True, close_fds=True)
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
