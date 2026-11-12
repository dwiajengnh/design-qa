#!/usr/bin/env python3
"""Report Design QA progress to the browser form.

  qa_status.py step <1-5> "<what you're doing now>"
  qa_status.py done "<summary>" [--link <notion database url>]
  qa_status.py error "<what went wrong>"

Steps: 1 Reading Figma, 2 Checking the staging page, 3 Capturing screenshots,
4 Writing bugs to Notion, 5 Done. Writes ~/.design-qa/status.json, which the
form server shows on the page. Safe to call when no form is open (it just writes the file).
"""
import json, os, sys, time

STEPS = ['Reading Figma', 'Checking the staging page', 'Capturing screenshots', 'Writing bugs to Notion', 'Done']
PATH = os.path.expanduser('~/.design-qa/status.json')


def load():
    try:
        with open(PATH) as f:
            return json.load(f)
    except Exception:
        return {'state': 'running', 'step': 0, 'started': time.time(), 'log': []}


def save(s):
    os.makedirs(os.path.dirname(PATH), exist_ok=True)
    s['updated'] = time.time()
    s['steps'] = STEPS
    s['log'] = s.get('log', [])[-30:]
    tmp = PATH + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(s, f)
    os.replace(tmp, PATH)


def main():
    a = sys.argv[1:]
    if not a:
        raise SystemExit(__doc__)
    s = load()
    cmd = a[0]
    if cmd == 'step' and len(a) >= 2:
        n = max(1, min(int(a[1]), len(STEPS)))
        msg = a[2] if len(a) > 2 else STEPS[n - 1]
        s.update(state='running', step=n, message=msg)
        s.setdefault('log', []).append(msg)
    elif cmd == 'done':
        s.update(state='done', step=len(STEPS), message=a[1] if len(a) > 1 else 'QA finished')
        if '--link' in a:
            s['link'] = a[a.index('--link') + 1]
    elif cmd == 'error':
        s.update(state='error', message=a[1] if len(a) > 1 else 'Something went wrong')
    else:
        raise SystemExit(__doc__)
    save(s)
    print('status:', s['state'], s.get('step'), s.get('message'))


if __name__ == '__main__':
    main()
