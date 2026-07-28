from __future__ import annotations

from typing import List, Optional


# === 默认提示词常量（集中管理，可供用户修改） ===

DEFAULT_SYSTEM_PROMPT = (
    "你是一个中文助理，负责解释用户提供或引用的内容。\n"
    "请严格按以下 Markdown 结构输出：\n\n"
    "**关键词**\n"
    "关键词1 | 关键词2 | 关键词3\n\n"
    "**详细阐述**\n"
    "要求：\n"
    "1. 不要输出思考过程。\n"
    "2. 不要输出多余小标题。\n"
    "3. 关键词放在“**关键词**”下一行，使用“ | ”分隔。\n"
)

# 短回复（100字内）- 用于“仅 zssm + 回复文件/消息”
DEFAULT_TEXT_USER_PROMPT_SHORT = (
    "请解释这条被回复的消息含义，回答简洁，不超过100字。\n"
    "原始文本：\n{text}"
)

DEFAULT_IMAGE_USER_PROMPT_SHORT = (
    "请解释这条被回复的消息/图片含义，回答简洁，不超过100字。\n"
    "{text_block}\n包含图片：若无法直接读取图片，请结合上下文或文件名描述。"
)

# 长回复（不限字数）- 用于“zssm 问题”/“zssm 问题+文件”
DEFAULT_TEXT_USER_PROMPT_DETAIL = (
    "请详细解释下面内容，结合上下文给出完整说明，字数不限。\n"
    "原始文本：\n{text}"
)

DEFAULT_IMAGE_USER_PROMPT_DETAIL = (
    "请详细解释下面消息/图片内容，结合上下文给出完整说明，字数不限。\n"
    "{text_block}\n包含图片：若无法直接读取图片，请结合上下文或文件名描述。"
)


def build_user_prompt(text: Optional[str], images: List[str], concise: bool = True) -> str:
    """根据是否包含图片、是否简短模式选择提示词模板。"""
    text_block = ("原始文本:\n" + text) if text else ""

    if concise:
        tmpl = DEFAULT_IMAGE_USER_PROMPT_SHORT if images else DEFAULT_TEXT_USER_PROMPT_SHORT
    else:
        tmpl = DEFAULT_IMAGE_USER_PROMPT_DETAIL if images else DEFAULT_TEXT_USER_PROMPT_DETAIL

    return tmpl.format(text=text or "", text_block=text_block)


def build_system_prompt() -> str:
    """返回系统提示词（供 LLM 调用使用）。"""
    return DEFAULT_SYSTEM_PROMPT
