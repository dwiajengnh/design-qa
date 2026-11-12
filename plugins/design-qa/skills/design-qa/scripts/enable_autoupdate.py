#!/usr/bin/env python3
"""Turn on Claude Code auto-update for the kesato-plugins marketplace.

Sets extraKnownMarketplaces["kesato-plugins"].autoUpdate = true in
~/.claude/settings.json, so new versions of this plugin install by themselves
when Claude starts. Does nothing if it's already on, or if the plugin was
installed by copying the folder (no kesato-plugins entry). Changes nothing else.
"""
import json, os

PATH = os.path.expanduser('~/.claude/settings.json')
NAME = 'kesato-plugins'

try:
    with open(PATH) as f:
        s = json.load(f)
except Exception:
    raise SystemExit(0)

m = (s.get('extraKnownMarketplaces') or {}).get(NAME)
if not isinstance(m, dict):
    print('auto-update: not a plugin install, skipped')
elif m.get('autoUpdate') is True:
    print('auto-update: already on')
else:
    m['autoUpdate'] = True
    tmp = PATH + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(s, f, indent=2)
        f.write('\n')
    os.replace(tmp, PATH)
    print('auto-update: turned on')
