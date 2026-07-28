from __future__ import annotations

import unittest

from astrbot_plugin_zssm_core.file_preview_utils import build_text_exts_from_config
from astrbot_plugin_zssm_core.main import ZssmExplain
from astrbot_plugin_zssm_core.message_utils import extract_from_onebot_message_payload


class TestPureUtils(unittest.TestCase):
    def test_strip_trigger_content(self):
        self.assertEqual(ZssmExplain._strip_trigger_and_get_content("zssm hello"), "hello")
        self.assertEqual(ZssmExplain._strip_trigger_and_get_content("  /zssm  hello  "), "hello")
        self.assertEqual(ZssmExplain._strip_trigger_and_get_content("zssm? hello"), "hello")
        self.assertEqual(ZssmExplain._strip_trigger_and_get_content("zssm"), "")

    def test_build_text_exts(self):
        exts = build_text_exts_from_config("md, json, .py", ["txt"])
        self.assertIn(".txt", exts)
        self.assertIn(".md", exts)
        self.assertIn(".json", exts)
        self.assertIn(".py", exts)

    def test_extract_onebot_payload(self):
        payload = {
            "data": {
                "message": [
                    {"type": "text", "data": {"text": "hello"}},
                    {"type": "image", "data": {"url": "http://a/b.png"}},
                ]
            }
        }
        t, imgs = extract_from_onebot_message_payload(payload)
        self.assertIn("hello", t)
        self.assertEqual(imgs, ["http://a/b.png"])


if __name__ == "__main__":
    unittest.main()
