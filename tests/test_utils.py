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
        self.assertEqual(ZssmExplain._strip_trigger_and_get_content("zssm?hello"), "hello")
        self.assertEqual(ZssmExplain._strip_trigger_and_get_content("zssm：hello"), "hello")
        self.assertEqual(ZssmExplain._strip_trigger_and_get_content("zssm: hello"), "hello")
        self.assertEqual(ZssmExplain._strip_trigger_and_get_content("zssm，hello world"), "hello world")
        self.assertEqual(ZssmExplain._strip_trigger_and_get_content("zssm"), "")

    def test_is_zssm_trigger(self):
        self.assertTrue(ZssmExplain._is_zssm_trigger("zssm hello"))
        self.assertTrue(ZssmExplain._is_zssm_trigger("zssm? what is this"))
        self.assertTrue(ZssmExplain._is_zssm_trigger("zssm：什么是量子计算"))
        self.assertFalse(ZssmExplain._is_zssm_trigger("hello world"))
        self.assertFalse(ZssmExplain._is_zssm_trigger("zssmhello"))

    def test_extract_search_query(self):
        self.assertEqual(ZssmExplain._extract_search_query("搜索一下今天的天气"), "今天的天气")
        self.assertEqual(ZssmExplain._extract_search_query("搜索：量子计算"), "量子计算")
        self.assertEqual(ZssmExplain._extract_search_query("search today's weather"), "today's weather")
        self.assertEqual(ZssmExplain._extract_search_query("联网搜索 北京天气"), "北京天气")
        self.assertEqual(ZssmExplain._extract_search_query("什么是量子计算"), "")

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

    def test_extract_reply_with_chain(self):
        import astrbot.api.message_components as Comp
        from astrbot_plugin_zssm_core.message_utils import try_extract_from_reply_component

        reply = Comp.Reply(id="123", chain=[Comp.Plain(text="Hello english text")])
        text, images, from_forward = try_extract_from_reply_component(reply)
        self.assertIn("Hello english text", text)
        self.assertEqual(from_forward, False)

        reply2 = Comp.Reply(message_str="Hello from message_str")
        text2, images2, from_forward2 = try_extract_from_reply_component(reply2)
        self.assertIsNone(text2)

    def test_web_search_empty_query(self):
        import asyncio
        from astrbot_plugin_zssm_core.web_search import perform_web_search

        self.assertIsNone(asyncio.run(perform_web_search("", provider_settings={})))
        self.assertIsNone(asyncio.run(perform_web_search("   ", provider_settings={})))


if __name__ == "__main__":
    unittest.main()
