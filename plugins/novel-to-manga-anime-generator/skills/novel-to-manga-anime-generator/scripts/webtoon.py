#!/usr/bin/env python3
"""One command: chapter text in, finished webtoon out.

  python webtoon.py chapter.txt
  python webtoon.py chapter.txt --lang ja --max-panels 40 --out work/ch01

Steps (each is resumable; finished images are never regenerated):
  1. plan    Claude adapts the chapter into <out>/comic_plan.json   (ANTHROPIC_API_KEY)
  2. refs    Seedream draws character / location / prop sheets      (ARK_API_KEY)
  3. panels  Seedream draws every panel, using the REF sheets
  4. stitch  panels + lettering -> <out>/output/webtoon.png and upload-sized slices

Re-running with the same --out skips the plan (unless --replan) and any image that
already finished, so a failed run can simply be started again.
"""

import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import plan_writer  # noqa: E402
import stitch  # noqa: E402


def run_comic(plan_path, *extra):
    cmd = [sys.executable, os.path.join(HERE, "run_comic.py"), plan_path, *extra]
    print("[run]", " ".join(cmd[1:]), flush=True)
    return subprocess.call(cmd)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("chapter", help="text file with the chapter (UTF-8), or - for stdin")
    ap.add_argument("--out", default=None, help="work folder (default: webtoon_<chapter name>/)")
    ap.add_argument("--lang", default="en", choices=["en", "zh", "ja"],
                    help="language of dialogue and lettering")
    ap.add_argument("--style", default=plan_writer.DEFAULT_STYLE, help="style lock string")
    ap.add_argument("--max-panels", type=int, default=60)
    ap.add_argument("--delay", type=float, default=0, help="seconds between panels (raise on HTTP 429)")
    ap.add_argument("--retries", type=int, default=1, help="extra passes for failed images")
    ap.add_argument("--replan", action="store_true", help="write a new plan even if one exists")
    ap.add_argument("--plan-only", action="store_true", help="stop after writing the plan")
    ap.add_argument("--no-letter", action="store_true", help="don't draw dialogue on the strip")
    ap.add_argument("--font", default=None, help="font file for lettering (needed for zh/ja "
                    "if no Noto CJK / system CJK font is installed)")
    ap.add_argument("--width", type=int, default=800)
    ap.add_argument("--slice-height", type=int, default=1280)
    args = ap.parse_args()

    if args.chapter == "-":
        chapter, name = sys.stdin.read(), "stdin"
    else:
        with open(args.chapter, encoding="utf-8") as f:
            chapter = f.read()
        name = os.path.splitext(os.path.basename(args.chapter))[0]
    if not chapter.strip():
        print("The chapter file is empty.")
        return 1

    out = os.path.abspath(args.out or f"webtoon_{name}")
    os.makedirs(out, exist_ok=True)
    plan_path = os.path.join(out, "comic_plan.json")

    # 1. plan
    if args.replan or not os.path.exists(plan_path):
        try:
            plan = plan_writer.write_plan(chapter, lang=args.lang, style=args.style,
                                          max_panels=args.max_panels, delay_seconds=args.delay)
        except plan_writer.PlanError as e:
            print(f"[plan] {e}")
            return 1
        with open(plan_path, "w", encoding="utf-8") as f:
            json.dump(plan, f, ensure_ascii=False, indent=2)
        print(f"[plan] wrote {plan_path}")
    else:
        print(f"[plan] reusing {plan_path} (pass --replan to write a new one)")

    if run_comic(plan_path, "--check") != 0:
        return 1
    if args.plan_only:
        return 0
    if not os.environ.get("ARK_API_KEY"):
        print("ARK_API_KEY is not set; see references/api-setup.md. The plan is ready.")
        return 1

    # 2-3. refs then panels, with retry passes (finished items are skipped)
    for stage in ("refs", "panels"):
        code = run_comic(plan_path, "--stage", stage)
        for _ in range(args.retries):
            if code != 2:
                break
            print(f"[run] retrying failed {stage}")
            code = run_comic(plan_path, "--stage", stage)
        if code == 1:
            return 1
        if code == 2 and stage == "refs":
            print("[run] some REF sheets failed; panels that need them will be skipped")

    # 4. stitch
    _, missing = stitch.stitch(plan_path, os.path.join(out, "output"), args.width,
                               args.slice_height, not args.no_letter, args.font)
    if missing:
        print("Some panels are missing. Re-run the same command to retry them.")
        return 2
    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
