# design-qa skill

Claude Code skill that compares a staging page with its Figma frames and logs visual bugs to Notion. Each bug gets an Expected (Figma) screenshot and an Actual (Staging) screenshot.

## Install
Unzip or copy this folder to one of these locations:
- `~/.claude/skills/design-qa/`: available in all your projects
- `<project>/.claude/skills/design-qa/`: only that project (you can commit it to the repo for the team)

## Needs
- Figma connector (official Figma MCP), signed in
- Notion connector, with access to your QA page or database
- Google Chrome and Node 22 or newer (for `scripts/capture.mjs`)
- python3, curl

## Use
In Claude Code, type:

```
/design-qa
```

A form opens. In the Claude desktop app it appears in the chat; in a terminal, it opens in your browser. Fill in:
- Notion database (only the first time; after that it's remembered)
- Staging page URL
- Figma frame link, desktop
- Figma frame link, mobile

Click Start QA. Claude compares each section, shows you the bug list for approval, then creates one Notion entry per bug.

The rules it follows (ignore dummy content, entry format and so on) are in `SKILL.md`. Edit that file to change them for your team.
