"""Offline tests for the webtoon pipeline (no API calls).

Run: python -m unittest discover -s tests
"""

import json
import os
import sys
import tempfile
import unittest
from types import SimpleNamespace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "plugins", "novel-to-manga-anime-generator", "skills",
                       "novel-to-manga-anime-generator", "scripts")
sys.path.insert(0, SCRIPTS)

from PIL import Image  # noqa: E402

import plan_writer  # noqa: E402
import stitch  # noqa: E402


def raw_plan(n=3, bad_index=False):
    return {
        "title": "Test",
        "adaptation_notes": "Kept everything.",
        "refs": [
            {"id": "char_mira", "kind": "character", "prompt": "Character reference sheet of Mira."},
            {"id": "loc_dock", "kind": "location", "prompt": "Environment concept art of a dock."},
        ],
        "panels": [
            {"id": f"p{i:03d}", "scene": "Mira on the dock", "refs": ["char_mira", "loc_dock"],
             "aspect": "3:4" if i % 2 else "9:16",
             "prompt": ("Use image 3 for x." if bad_index and i == 1 else
                        "Use image 1 for the character and image 2 for the location. "
                        "No text, no speech bubbles, no captions."),
             "lines": [{"kind": "speech", "speaker": "Mira", "side": "left",
                        "text": "The tide is turning faster than anyone expected tonight."},
                       {"kind": "narration", "speaker": "", "side": "center", "text": "Later."}],
             "gap_after": "medium"}
            for i in range(1, n + 1)
        ],
    }


class FakeStream:
    def __init__(self, message):
        self.message = message

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def get_final_message(self):
        return self.message


class FakeClient:
    """Returns the queued raw plans one per call and records the requests."""

    def __init__(self, *plans):
        self.plans = list(plans)
        self.calls = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(stream=self._stream))

    def _stream(self, **kwargs):
        self.calls.append(kwargs)
        block = SimpleNamespace(type="text", text=json.dumps(self.plans.pop(0)))
        return FakeStream(SimpleNamespace(stop_reason="end_turn", content=[block]))


class PlanWriterTests(unittest.TestCase):
    def test_converts_to_comic_plan(self):
        plan = plan_writer.to_comic_plan(raw_plan(), "en", "style")
        self.assertEqual(plan["reading_direction"], "ltr")
        self.assertEqual(plan["pages"][0]["rows"], [["p001"], ["p002"], ["p003"]])
        self.assertEqual(plan_writer.validate(plan, 60), [])

    def test_retries_once_on_validation_error(self):
        client = FakeClient(raw_plan(bad_index=True), raw_plan())
        plan = plan_writer.write_plan("Once upon a time.", client=client, log=lambda *_: None)
        self.assertEqual(len(client.calls), 2)
        self.assertEqual(len(plan["panels"]), 3)
        self.assertIn("failed validation", client.calls[1]["messages"][-1]["content"])

    def test_gives_up_after_second_failure(self):
        client = FakeClient(raw_plan(bad_index=True), raw_plan(bad_index=True))
        with self.assertRaises(plan_writer.PlanError):
            plan_writer.write_plan("x", client=client, log=lambda *_: None)

    def test_panel_limit_enforced(self):
        plan = plan_writer.to_comic_plan(raw_plan(5), "en", "style")
        self.assertTrue(plan_writer.validate(plan, 4))

    def test_request_shape(self):
        client = FakeClient(raw_plan())
        plan_writer.write_plan("text", client=client, log=lambda *_: None)
        call = client.calls[0]
        self.assertEqual(call["output_config"]["format"]["type"], "json_schema")
        self.assertIn("<chapter>\ntext\n</chapter>", call["messages"][0]["content"])

    def test_refusal_raises(self):
        client = FakeClient()
        msg = SimpleNamespace(stop_reason="refusal", content=[],
                              stop_details=SimpleNamespace(explanation="nope"))
        client.beta.messages.stream = lambda **kw: FakeStream(msg)
        with self.assertRaises(plan_writer.PlanError):
            plan_writer.write_plan("x", client=client, log=lambda *_: None)


class StitchTests(unittest.TestCase):
    def test_strip_and_slices(self):
        with tempfile.TemporaryDirectory() as d:
            plan = plan_writer.to_comic_plan(raw_plan(3), "en", "style")
            plan_path = os.path.join(d, "comic_plan.json")
            with open(plan_path, "w", encoding="utf-8") as f:
                json.dump(plan, f)
            panels = os.path.join(d, "output", "panels")
            os.makedirs(panels)
            Image.new("RGB", (1728, 2304), (200, 30, 30)).save(os.path.join(panels, "p001.png"))
            Image.new("RGB", (1440, 2560), (30, 200, 30)).save(os.path.join(panels, "p002.png"))
            # p003 missing on purpose
            full, missing = stitch.stitch(plan_path, log=lambda *_: None)
            self.assertEqual(missing, ["p003"])
            with Image.open(full) as im:
                self.assertEqual(im.width, 800)
                self.assertGreater(im.height, 1067 + 1422)
                height = im.height
            slices = sorted(os.listdir(os.path.join(d, "output", "webtoon_slices")))
            self.assertEqual(len(slices), -(-height // 1280))

    def test_wrap_cjk_and_words(self):
        from PIL import ImageDraw, ImageFont
        draw = ImageDraw.Draw(Image.new("RGB", (1, 1)))
        font = ImageFont.load_default(size=20)
        self.assertGreater(len(stitch.wrap(draw, "word " * 40, font, 200)), 1)
        self.assertGreater(len(stitch.wrap(draw, "漢" * 60, font, 200)), 1)


if __name__ == "__main__":
    unittest.main()
