# Kesato Claude Code plugins

## Install
In Claude Code:

```
/plugin marketplace add dwiajengnh/design-qa
/plugin install design-qa@kesato-plugins
```

Update later with `/plugin marketplace update kesato-plugins`.

## design-qa
Compares a staging page with its Figma frames (desktop and mobile) and logs each visual bug to a Notion database, with an Actual (Staging) and an Expected (Figma) screenshot.

**Start a QA:** type `/design-qa` and fill in the form, or open `plugins/design-qa/skills/design-qa/form.html` in your browser.

**You need:**
- Figma and Notion connected in your Claude account
- Google Chrome and Node 22 or newer (for screenshots)
- python3 and curl
- Access to your team's Notion QA database

The rules (ignore dummy content, entry format, and so on) are in `plugins/design-qa/skills/design-qa/SKILL.md`.
