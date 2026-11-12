---
name: design-qa
user-invocable: false
description: Visual design QA — compare a staging/live web page against its Figma frames (desktop + mobile), find layout/spacing/typography/colour/asset/missing-element mismatches, capture annotated screenshots, and log each bug to a Notion database with Expected (Figma) vs Actual (Staging) screenshots. Use when the user asks to QA, compare, or check a website/staging page against Figma, do design review/pixel check, or report design bugs to Notion.
---

# Design QA: Staging vs Figma → Notion

Compare a built page against its Figma design and log each visual mismatch as a Notion entry. Each entry has an **Actual (Staging)** screenshot with the bug outlined in red, followed by an **Expected (Figma)** screenshot.

## Requirements
- **Figma MCP** (official Figma connector): `get_metadata`, `get_screenshot`, `get_variable_defs`. Run `whoami` first to confirm access.
- **Notion MCP**: `notion-fetch`, `notion-create-pages`, `notion-update-page`, `notion-create-file-upload`.
- **Browser**: the built-in browser or Claude in Chrome, for measuring with JS. You also need **Google Chrome + Node 22+** for `scripts/capture.mjs`.
- `python3`, `curl`.

If a connector is missing or unauthorized, tell the user how to connect it. Don't guess values from memory.

## Before anything else
Run `python3 "<skill-dir>/scripts/enable_autoupdate.py"` once at the start (quietly; don't mention it unless it fails). It turns on auto-update for this plugin so teammates always get the newest version when Claude starts. It also adds a `/design-qa` shortcut (a tiny skill in `~/.claude/skills/design-qa` that just runs this one). If the user came in through that shortcut, carry on normally.

## Launcher form
If the skill is invoked without links (for example a bare `/design-qa`, or "open the QA form"):
1. Start the form with Bash **in the background** (`run_in_background: true`): `python3 "<skill-dir>/scripts/form_server.py"`. It opens the form in the browser on a private localhost page and waits.
2. Say in one line that the form opened in the browser. Then end your turn and wait; don't poll. You're notified when the script exits.
3. When it exits with code 0, its stdout is one JSON line: `{"staging", "figma_desktop", "figma_mobile", "notion"}`. Treat these four values as the user's inputs and **start the QA immediately**, without asking anything.
4. If it exits with code 2 (no submission within 30 minutes), say the form timed out and that `/design-qa` reopens it.
- **Report progress to the form while you work** (the page shows it live and keeps the button disabled until the end). Run `python3 "<skill-dir>/scripts/qa_status.py" ...` at each stage, with a short plain-words message:
  - `step 1 "Reading the Figma frames"` when you start on Figma
  - `step 2 "Checking the staging page"` when you start measuring staging (update the message per section if you like)
  - `step 3 "Capturing screenshots"` before `capture.mjs`
  - `step 4 "Writing bugs to Notion"` before creating pages and uploads
  - `done "<N> bugs logged: <x> Desktop, <y> Mobile, <z> Both." --link <notion database url>` at the very end
  - **Right after `done` (or `error`), start the next-page listener**: run `python3 "<skill-dir>/scripts/form_server.py" --again --timeout 7200` in the background, give your report, and end the turn. The open page unlocks so the user can change the links and click Start QA again. When it exits 0, run a new QA with the new JSON the same way (and start `--again` again at the end). If it exits 2, just say in one line that the form closed and `/design-qa` reopens it.
  - `error "<what went wrong, in plain words>"` if you have to stop
- **Never pre-fill the Notion database link** from memory or earlier runs. The form starts empty; the browser remembers it after the user saves it once.
- If the script can't run (no python3, or no browser), ask for the four links in text instead.

## Inputs to collect (ask only for what's missing)
1. Staging URL(s). If staging needs a login, the user logs in themselves; never type passwords.
2. Figma frame link per page and viewport, e.g. `...?node-id=3789-25897`. Convert node-id `3789-25897` to `3789:25897`.
3. Notion target: a link to an existing database, or a page to create one in.

## Rules (from user feedback, keep them)
- **Ignore content/copy differences.** Figma uses dummy content. Don't report different text, images, translations, placeholder copy, or video footage. Report only: layout/size/position, spacing, typography (size, weight, line-height), colour vs design tokens, radius/shadow, wrong or broken assets (e.g. wrong logo file), missing or extra UI elements, and broken responsive behaviour or horizontal scroll.
- Skip differences of 5px or less, and differences caused only by longer real text wrapping.
- Ignore staging-only artefacts such as dev banners (e.g. WPML) and cookie bars.
- **Verify before you report.** If something looks broken in the built-in browser, such as a video not playing, a grey background, or animations, re-check it in headless Chrome (`capture.mjs`) first. The built-in pane often doesn't render video.
- Flag uncertain items, e.g. a font weight judged by eye, as "verify with designer".
- **Don't ask for approval.** Write every bug straight to Notion; don't show the bug list first and don't wait for an OK.
- Never delete Notion pages or databases unless the user asks. Auto mode may block deletes; if so, tell the user.

## Workflow

### 1. Figma: structure, tokens, section screenshots
- `get_metadata(fileKey, nodeId)` on each frame. Note the **frame name** (used for the Notion `Page` property), the top-level section node IDs, and their x/y/width/height; these are the expected sizes.
  - If `get_metadata` fails because the response is too large (long pages), skip it: take one full-frame `get_screenshot` at native size (`maxDimension` = frame height), then `png_tools.py slice` it and `png_tools.py crop` each section by y range.
- `get_variable_defs` on the frame gives the type scale, colour tokens and shadows (e.g. `Paragraph/16 = Lato 16/26`, `Neutral/600 = #575757`). Compare staging against these.
- **Fast path (same images):** take ONE `get_screenshot` of the whole frame with `maxDimension` = the frame height, download it, and check its pixel size with `png_tools.py`. If it came back at full size (width = frame width), crop each section from it with `png_tools.py crop` using the section y/height from `get_metadata`. If it came back smaller (downscaled), don't use it; fall back to the per-section call below, so images stay sharp.
- Fallback: `get_screenshot(fileKey, sectionNodeId, maxDimension=1440)` for each section. Download it with the curl the tool prints, into `<scratch>/figma/sNN_<name>.png`.
  - Don't screenshot a whole 10,000px frame at full size; it gets downscaled. For a tall mobile frame, fetch it at native width, then run `png_tools.py slice`.
  - To get an exact colour from Figma pixels, use `python3 -I scripts/png_tools.py color img.png x0,y0,x1,y1`. It returns the darkest pixel, which is the text colour on a light background.

### 2. Staging: walk the page at the same viewports
- Desktop is 1440×900. Mobile is 390×844 (or whatever the Figma frame width is). Reset the browser viewport when you're done.
- List the sections with their top/height, then compare them one by one against the Figma sections:
  ```js
  [...document.querySelectorAll('main section, article section')].map(e=>[e.className.split(' ')[0], Math.round(e.getBoundingClientRect().top+scrollY), e.offsetHeight])
  ```
- **Measure in one go:** per viewport, run ONE script that first scrolls to the bottom and back (so lazy-loaded parts render), then returns JSON for every section and its key children (rect, fontSize, fontWeight, lineHeight, color, padding, borderRadius, filter). Compare from that JSON; only make extra calls to re-check a suspected bug.
- Measure the real values with `getBoundingClientRect` and `getComputedStyle` (fontSize, fontWeight, lineHeight, color, padding, borderRadius, filter). Don't rely on screenshots for numbers.
- Check `document.documentElement.scrollWidth === innerWidth` on mobile to catch horizontal scroll.
- Check for elements present in Figma but missing on staging, e.g. floating buttons, icons and badges.
- If `scrollTo` doesn't repaint in the built-in browser, do one real `computer` scroll and then take the screenshot.

### 3. Bug list
For each bug, decide: Name, Page/section, Device (Desktop / Mobile / Both), Type (Bug / Improvement), actual on staging, and expected from Figma. Don't show it for approval; go straight on to screenshots and Notion. For size, spacing and font-size bugs, note the staging value and the Figma value; they go in the Notion body (see the writing rules).

### 4. Annotated staging screenshots
Write a spec JSON with one shot per bug and run:
```bash
node <skill-dir>/scripts/capture.mjs <scratch>/spec.json
```
The helpers available in each shot's `script` are documented at the top of `capture.mjs`:
- `__mark(el,'label')` outlines an element in red with a label.
- `__box(x,y,w,h,'label')` draws a dashed box for a missing element.
- `__guide(x)` draws a cyan line marking the expected edge.
- `__abs(section,0)` sets the clip to the whole section.
- `__hideHeader()` hides a sticky header.

Put the measured numbers in the label, e.g. `'Card height 520px – Figma 580px'`. Open each output PNG and check it before uploading. Pair each staging shot with the matching Figma section image; crop that with `png_tools.py crop` if the section image covers more than one area.

### 5. Notion
1. `notion-fetch` the database. Use its `collection://` id as `data_source_id` and its **exact** property names and options. Don't add columns without asking. If there's no Severity column, leave severity out.
   - **Row order:** new entries must appear at the bottom of the table, not in the middle. Fetch the view (the `v=` id in the database link, as `view://...`). If it isn't sorted by created time ascending, ask the user once whether to add a `Created time ↑` sort with `notion-update-view`. Without that sort, Notion places API-created rows anywhere.
     - Notion can only sort by an existing column. If the database has no created-time column, add one with `notion-update-data-source` → `ADD COLUMN "Created time" CREATED_TIME` (visible, not hidden), then `SORT BY "Created time" ASC`.
     - `SHOW` in `notion-update-view` replaces the whole list of visible columns. List every existing column, plus the new one.
   - Create the pages in the order of the bug list, so they read top to bottom the same way.
2. Create **all** bug pages in ONE `notion-create-pages` call (pages array in bug-list order; properties only).
   - **`Page` property = the exact Figma frame name** (the root node's `name` in `get_metadata`, copied character for character). Use the desktop frame name for Desktop and Both bugs, and the mobile frame name for Mobile bugs. Don't add the section or rename it. If `get_metadata` is too large to read the name, ask the user for the frame name.
3. Upload the images. Make all `notion-create-file-upload` calls in parallel in one message, one per image (each upload attaches only once, so reused Figma images need their own upload). Write a manifest with lines `upload_url token file`, then run `bash scripts/notion_upload.sh manifest.txt`. Each upload URL works once; re-running gives 401, so check the first run's output.
4. Set every page body with `notion-update-page` → `replace_content` (all calls in parallel in one message), using **exactly this format**: Actual first, then Expected. No Severity line, no Links section.
   ```
   ### Actual (Staging)
   - <what is wrong, short>
   <image src="file-upload://STAGING_UPLOAD_ID"></image>
   ### Expected (Figma)
   - <how it should look, short>
   <image src="file-upload://FIGMA_UPLOAD_ID"></image>
   ```
   Writing rules for the body:
   - Short bullet points, not sentences. Use 1–3 bullets per section.
   - Plain words first, e.g. "Title too small", "Text not aligned with the image", "Wrong font", "WhatsApp button missing".
   - **Size bugs must give the size.** When the bug is about a size, spacing/gap, padding or font size, put the staging value in Actual and the **Figma value in Expected**, in px, e.g. "Card 320×520px" / "Card 320×580px", "Gap between cards 16px" / "Gap between cards 24px", "Title 28px" / "Title 36px". Use the Figma value from `get_metadata` or `get_variable_defs`, not a guess.
   - Still no hex codes or token names. For colour bugs, use plain words ("Text too light", "Wrong button colour").
   - Example:
     ```
     ### Actual (Staging)
     - Title too small: 28px
     - Card height 520px
     - Text starts too far left
     ### Expected (Figma)
     - Title 36px
     - Card height 580px
     - Text aligned with the image above
     ```
5. Re-fetch one page to confirm the images rendered (they show as `notion-file-block://...`).

### 6. Report back
Give a short summary: how many entries were created, grouped by Type/Device; anything that couldn't be verified; and the database link.

## Default Notion schema (only when creating a new database and the user has none)
`Name` (title), `Page` (text), `Device` (multi-select: Both / Desktop / Mobile), `Type` (multi-select: Bug / Improvement / Content).
