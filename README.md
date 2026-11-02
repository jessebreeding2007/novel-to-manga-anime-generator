# Novel to Manga & Anime Generator

**English** | [繁體中文](README.zh-TW.md) | [日本語](README.ja.md)

An AI agent plugin that turns novel text into a **manga / comic / webtoon** or an **anime-style video**. Paste a chapter, choose comic or video, and the agent walks you through a full production pipeline and writes ready-to-use prompts for **Seedream** (images) and **Seedance** (video).

Works with **ChatGPT**, **Codex** and **Claude Code**. Replies in your language: English, 中文, 日本語.

## What it does

1. **REF sheets** — characters, locations and props, so every panel and shot stays consistent
2. **Adaptation outline** — what to keep, merge or cut; opening hook, climax, ending hook
3. **Comic**: page breakdown (regular / highlight / climax pages) → per-panel context → Seedream prompts → lettering
   **Anime**: per-minute outline → per-shot context (start state, event, end state) → keyframes → Seedance prompts → sound & editing
4. **QA** — a pre-generation checklist and a fix-in-order rule (Context → REF → Prompt → result)
5. **Optional automation** — Python scripts let an agent generate every image and video through the BytePlus ModelArk API

Full worked examples use public-domain classics: *Hamlet* (English), 西遊記 (Chinese), 竹取物語 (Japanese).

## Install

### ChatGPT
**Option A — add this repo as a marketplace**
1. ChatGPT → **Plugins** → **Add** → **Add marketplace**
2. Paste `https://github.com/BBQ2077/novel-to-manga-anime-generator`
3. Install **Novel to Manga & Anime Generator**

**Option B — upload the archive**
1. Download [`dist/novel-to-manga-anime-generator-plugin.zip`](dist/novel-to-manga-anime-generator-plugin.zip)
2. ChatGPT → **Plugins** → **Add** → **Upload plugin archive**

### Codex
Add this repository as a plugin marketplace, then install `novel-to-manga-anime-generator`.

### Claude Code
```
/plugin marketplace add BBQ2077/novel-to-manga-anime-generator
/plugin install novel-to-manga-anime-generator@manga-anime-tools
```

## Fully automatic webtoon (one command)

Paste a chapter into a text file and get a finished vertical webtoon back, with no prompts to copy and no approvals in between:

```bash
pip install -r requirements-webtoon.txt
export ANTHROPIC_API_KEY=...   # Claude writes the adaptation plan
export ARK_API_KEY=...         # Seedream draws the images (see api-setup.md)
python plugins/novel-to-manga-anime-generator/skills/novel-to-manga-anime-generator/scripts/webtoon.py chapter.txt
```

| Step | What happens | Output |
|---|---|---|
| 1. Plan | Claude adapts the chapter using this skill's rules: REF sheets, fixed character descriptions, hook / climax / cliffhanger, webtoon pacing. The plan is validated and fixed automatically if needed. | `webtoon_chapter/comic_plan.json` |
| 2. REFs | Seedream draws character, location and prop sheets | `output/refs/` |
| 3. Panels | Seedream draws every panel using the matching REFs; failed panels are retried | `output/panels/` |
| 4. Stitch | Panels are joined top to bottom; dialogue is lettered in the white space above each panel | `output/webtoon.png`, `output/webtoon_slices/*.jpg` (800 × 1280 slices for upload) |

Useful options: `--lang en|zh|ja`, `--max-panels 60`, `--style "<style string from vocab.md>"`, `--no-letter` (clean art for your own lettering), `--plan-only` (review the plan first), `--replan`, `--font <file>`.
Re-running the same command resumes: finished images are never regenerated. To redo one panel: `run_comic.py <out>/comic_plan.json --only p012 --force`, then `stitch.py <out>/comic_plan.json`.

### From GitHub, with no local setup

1. In your fork: **Settings → Secrets and variables → Actions**, add `ANTHROPIC_API_KEY` and `ARK_API_KEY`.
2. Add a chapter as `chapters/<name>.txt` and push (or run the **Webtoon** workflow manually with the file path).
3. Download the `webtoons-<run>` artifact from the workflow run.

See [`chapters/README.md`](chapters/README.md) for per-chapter options. Both APIs bill per use; a 60-panel chapter is about 60–120 Seedream images plus one long Claude request.

## Try it

- `Turn this chapter into a manga: [paste text]`
- `Make a 3-minute anime from this scene: [paste text]`

## Generating the images and videos

| | Subscription — **BytePlus Lumina** (recommended) | API — **BytePlus ModelArk** |
|---|---|---|
| Best for | Most people: a few chapters or episodes, tweaking as you go | Letting an agent generate everything automatically in bulk |
| Cost | Fixed monthly fee | Pay per use |
| How | Paste the prompts into the web app | Set an API key; the plugin's scripts do the rest |
| Link | https://byteplus.pxf.io/vDqjnd | https://byteplus.pxf.io/c/7876220/3836120/48404 |

API setup: [`references/api-setup.md`](plugins/novel-to-manga-anime-generator/skills/novel-to-manga-anime-generator/references/api-setup.md)

> The links above are affiliate links. Using them supports this project at no extra cost to you.

## Copyright

⚠️ If you don't hold the rights to the original work, do not use the result commercially.

## License

[MIT](LICENSE)
