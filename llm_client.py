from __future__ import annotations

import asyncio
import os
from typing import Any, Callable, List, Optional


LLM_TIMEOUT_SEC_KEY = "llm_timeout_sec"
DEFAULT_LLM_TIMEOUT_SEC = 90
PROVIDER_ID_TEXT_KEY = "provider_id_text"
PROVIDER_ID_IMAGE_KEY = "provider_id_image"

# 新增：重试次数
LLM_RETRY_TIMES_KEY = "llm_retry_times"
DEFAULT_LLM_RETRY_TIMES = 2  # 1=不重试；2=重试1次


class LLMClient:
    """封装 LLM 调用与回退逻辑。"""

    def __init__(
        self,
        *,
        context: Any,
        get_conf_int: Callable[[str, int, int, int], int],
        get_config_provider: Optional[Callable[[str], Optional[Any]]] = None,
        logger: Optional[Any] = None,
    ):
        self._context = context
        self._get_conf_int = get_conf_int
        self._get_config_provider = get_config_provider
        self._logger = logger

    def filter_supported_images(self, images: List[str]) -> List[str]:
        ok: List[str] = []
        for x in images:
            try:
                if not isinstance(x, str) or not x:
                    continue
                lx = x.lower()
                if lx.startswith(("http://", "https://")):
                    ok.append(x)
                elif lx.startswith("base64://") or lx.startswith("data:image/"):
                    ok.append(x)
                elif lx.startswith("file://"):
                    fp = x[7:]
                    if fp.startswith("/") and len(fp) > 3 and fp[2] == ":":
                        fp = fp[1:]
                    if fp and os.path.exists(fp):
                        ok.append(os.path.abspath(fp))
                elif os.path.exists(x):
                    ok.append(os.path.abspath(x))
            except OSError:
                pass
        return ok

    @staticmethod
    def provider_supports_image(provider: Any) -> bool:
        try:
            mods = getattr(provider, "modalities", None)
            if isinstance(mods, (list, tuple)):
                ml = [str(m).lower() for m in mods]
                if any(k in ml for k in ["image", "vision", "multimodal", "vl", "picture"]):
                    return True
        except Exception:
            pass

        for attr in ("config", "model_config", "model"):
            try:
                lt = str(getattr(provider, attr, None)).lower()
                if any(
                    k in lt
                    for k in ["image", "vision", "multimodal", "vl", "gpt-4o", "gemini", "minicpm-v"]
                ):
                    return True
            except Exception:
                pass
        return False

    @staticmethod
    def _get_provider_label(provider: Any) -> str:
        if provider is None:
            return "None"
        for key in ("provider_id", "id", "name"):
            try:
                v = getattr(provider, key, None)
                if isinstance(v, str) and v.strip():
                    return v.strip()
            except Exception:
                continue
        return provider.__class__.__name__

    def _get_provider_from_config(self, key: str = PROVIDER_ID_TEXT_KEY) -> Optional[Any]:
        if not self._get_config_provider:
            return None
        try:
            return self._get_config_provider(key)
        except Exception:
            return None

    def select_text_provider(self, *, session_provider: Any) -> Any:
        cfg = self._get_provider_from_config(PROVIDER_ID_TEXT_KEY)
        return cfg if cfg is not None else session_provider

    def select_image_provider(self, *, session_provider: Any) -> Any:
        cfg = self._get_provider_from_config(PROVIDER_ID_IMAGE_KEY)

        if cfg is not None and self.provider_supports_image(cfg):
            return cfg

        if session_provider is not None and self.provider_supports_image(session_provider):
            return session_provider

        try:
            providers = self._context.get_all_providers()
        except Exception:
            providers = []
        for p in providers:
            if self.provider_supports_image(p):
                return p

        return cfg if cfg is not None else session_provider

    async def call_with_fallback(
        self,
        *,
        primary: Any,
        session_provider: Any,
        user_prompt: str,
        system_prompt: str,
        image_urls: List[str],
    ) -> Any:
        tried: set = set()
        images_present = bool(image_urls)
        timeout_sec = self._get_conf_int(LLM_TIMEOUT_SEC_KEY, DEFAULT_LLM_TIMEOUT_SEC, 5, 600)
        errors: List[str] = []

        def _record(p: Any, e: Exception) -> None:
            if len(errors) >= 8:
                return
            label = self._get_provider_label(p)
            msg = str(e).replace("\n", " ").strip()
            if len(msg) > 220:
                msg = msg[:217] + "..."
            errors.append(f"{label}: {e.__class__.__name__}: {msg}")

        async def _try_call(p: Any) -> Any:
            retry_times = self._get_conf_int(
                LLM_RETRY_TIMES_KEY, DEFAULT_LLM_RETRY_TIMES, 1, 5
            )

            last_exc: Optional[Exception] = None
            for i in range(max(1, retry_times)):
                try:
                    return await asyncio.wait_for(
                        p.text_chat(
                            prompt=user_prompt,
                            context=[],
                            system_prompt=system_prompt,
                            image_urls=image_urls,
                        ),
                        timeout=max(5, int(timeout_sec)),
                    )
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    last_exc = e
                    if i >= retry_times - 1:
                        raise
                    # 简单退避
                    await asyncio.sleep(min(0.5 * (2 ** i), 3.0))

            if last_exc:
                raise last_exc

        if primary is not None:
            tried.add(id(primary))
            try:
                return await _try_call(primary)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                _record(primary, e)

        if session_provider is not None and id(session_provider) not in tried:
            tried.add(id(session_provider))
            try:
                if not images_present or self.provider_supports_image(session_provider):
                    return await _try_call(session_provider)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                _record(session_provider, e)

        try:
            providers = self._context.get_all_providers()
        except Exception:
            providers = []

        for p in providers:
            if id(p) in tried:
                continue
            if images_present and not self.provider_supports_image(p):
                continue
            tried.add(id(p))
            try:
                return await _try_call(p)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                _record(p, e)

        if self._logger is not None:
            self._logger.error(
                "zssm_core: all providers failed (images_present=%s, tried=%d) errors=%s",
                images_present,
                len(tried),
                errors,
            )
        raise RuntimeError("all providers failed for current request")

    @staticmethod
    def pick_llm_text(llm_resp: object) -> str:
        try:
            rc = getattr(llm_resp, "result_chain", None)
            chain = getattr(rc, "chain", None)
            if isinstance(chain, list) and chain:
                parts: List[str] = []
                for seg in chain:
                    txt = getattr(seg, "text", None)
                    if isinstance(txt, str) and txt.strip():
                        parts.append(txt.strip())
                if parts:
                    return "\n".join(parts).strip()
        except Exception:
            pass

        for attr in ("completion_text", "text", "content", "message"):
            try:
                val = getattr(llm_resp, attr, None)
                if isinstance(val, str) and val.strip():
                    return val.strip()
            except Exception:
                pass

        return "（未解析到可读内容）"
