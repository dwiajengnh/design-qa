#!/usr/bin/env python3
"""Turn on Claude Code auto-update for the kesato-plugins marketplace.

Sets extraKnownMarketplaces["kesato-plugins"].autoUpdate = true in
~/.claude/settings.json, so new versions of this plugin install by themselves
when Claude starts. Does nothing if it's already on, or if the plugin was
installed by copying the folder (no kesato-plugins entry).

For plugin installs it also adds a small shortcut skill at
~/.claude/skills/design-qa so the skill can be run as /design-qa instead of
/design-qa:design-qa. It never overwrites an existing design-qa folder.
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

STUB_DIR = os.path.expanduser('~/.claude/skills/design-qa')
STUB = """---
name: design-qa
description: Visual design QA — compare a staging page against its Figma frames (desktop + mobile) and log each design bug to Notion with screenshots. Shortcut so the skill runs as /design-qa.
---
<!-- design-qa shortcut: created by the design-qa plugin. Safe to delete. -->

Shortcut for the design-qa plugin. Right away, use the Skill tool to run `design-qa:design-qa` (pass on these arguments: $ARGUMENTS) and follow its instructions exactly. Don't do anything else first.

If `design-qa:design-qa` isn't available, tell the user the design-qa plugin isn't installed and to install it from GitHub dwiajengnh/design-qa (marketplace kesato-plugins).
"""
if isinstance(m, dict) and not os.path.exists(STUB_DIR):
    os.makedirs(STUB_DIR)
    with open(os.path.join(STUB_DIR, 'SKILL.md'), 'w') as f:
        f.write(STUB)
    print('shortcut: /design-qa added')
