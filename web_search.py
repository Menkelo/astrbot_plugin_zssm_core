from __future__ import annotations

import html as html_mod
import re
import urllib.parse
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

try:
    import aiohttp  # type: ignore[import-not-found]
except Exception:  # pragma: no cover
    aiohttp = None  # type: ignore[assignment]

_SEARCH_TIMEOUT_SEC = 10
_MAX_RESULTS = 6
_MAX_SNIPPET_CHARS = 300


@dataclass
class SearchResultItem:
    title: str
    url: str
    snippet: str


@dataclass
class _SearchContext:
    session: Any
    timeout: aiohttp.ClientTimeout = field(default_factory=lambda: aiohttp.ClientTimeout(total=_SEARCH_TIMEOUT_SEC))


def _norm_key(value: Any) -> str:
    if not value:
        return ""
    if isinstance(value, list):
        for v in value:
            if isinstance(v, str) and v.strip():
                return v.strip()
        return ""
    return str(value).strip()


def _fmt_results(results: List[SearchResultItem]) -> str:
    lines: List[str] = []
    for idx, item in enumerate(results[:_MAX_RESULTS], 1):
        snippet = (item.snippet or "").strip()
        if len(snippet) > _MAX_SNIPPET_CHARS:
            snippet = snippet[:_MAX_SNIPPET_CHARS] + " ..."
        title = (item.title or "").strip() or "无标题"
        lines.append(f"{idx}. {title}")
        lines.append(f"   链接: {item.url}")
        if snippet:
            lines.append(f"   摘要: {snippet}")
    return "\n".join(lines)


async def _tavily_search(ctx: _SearchContext, key: str, query: str) -> List[SearchResultItem]:
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    payload = {"query": query, "max_results": _MAX_RESULTS, "include_answer": False}
    async with ctx.session.post(
        "https://api.tavily.com/search",
        json=payload,
        headers=headers,
        timeout=ctx.timeout,
    ) as resp:
        if resp.status != 200:
            return []
        data = await resp.json()
        results: List[SearchResultItem] = []
        for item in data.get("results", []) or []:
            if not isinstance(item, dict):
                continue
            url = item.get("url") or ""
            if not url:
                continue
            results.append(
                SearchResultItem(
                    title=str(item.get("title") or ""),
                    url=str(url),
                    snippet=str(item.get("content") or ""),
                )
            )
        return results


async def _bocha_search(ctx: _SearchContext, key: str, query: str) -> List[SearchResultItem]:
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Accept-Encoding": "gzip, deflate",
    }
    payload = {"query": query, "count": _MAX_RESULTS, "summary": True}
    async with ctx.session.post(
        "https://api.bochaai.com/v1/web-search",
        json=payload,
        headers=headers,
        timeout=ctx.timeout,
    ) as resp:
        if resp.status != 200:
            return []
        data = await resp.json()
        web_pages = ((data.get("data") or {}).get("webPages") or {}).get("value") or []
        results: List[SearchResultItem] = []
        for item in web_pages:
            if not isinstance(item, dict):
                continue
            url = item.get("url") or ""
            if not url:
                continue
            results.append(
                SearchResultItem(
                    title=str(item.get("name") or ""),
                    url=str(url),
                    snippet=str(item.get("snippet") or ""),
                )
            )
        return results


async def _brave_search(ctx: _SearchContext, key: str, query: str) -> List[SearchResultItem]:
    headers = {"Accept": "application/json", "X-Subscription-Token": key}
    params = {"q": query, "count": _MAX_RESULTS}
    async with ctx.session.get(
        "https://api.search.brave.com/res/v1/web/search",
        params=params,
        headers=headers,
        timeout=ctx.timeout,
    ) as resp:
        if resp.status != 200:
            return []
        data = await resp.json()
        web = (data.get("web") or {}).get("results") or []
        results: List[SearchResultItem] = []
        for item in web:
            if not isinstance(item, dict):
                continue
            url = item.get("url") or ""
            if not url:
                continue
            results.append(
                SearchResultItem(
                    title=str(item.get("title") or ""),
                    url=str(url),
                    snippet=str(item.get("description") or ""),
                )
            )
        return results


def _clean_html_fragment(frag: str) -> str:
    text = re.sub(r"<[^>]+>", "", frag)
    text = html_mod.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


async def _bing_search(ctx: _SearchContext, query: str) -> List[SearchResultItem]:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
        )
    }
    params = {"q": query}
    async with ctx.session.get(
        "https://cn.bing.com/search",
        params=params,
        headers=headers,
        timeout=ctx.timeout,
    ) as resp:
        if resp.status != 200:
            return []
        text = await resp.text()

    blocks = re.split(r'<li class="b_algo', text)[1:]
    results: List[SearchResultItem] = []
    for block in blocks:
        m = re.search(
            r'<h2[^>]*>\s*<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
            block,
            re.S,
        )
        if not m:
            continue
        url = m.group(1).strip()
        if not url or not url.startswith("http"):
            continue
        title = _clean_html_fragment(m.group(2))
        if not title:
            continue
        snippet = ""
        sm = re.search(r"<p[^>]*>(.*?)</p>", block, re.S)
        if sm:
            snippet = _clean_html_fragment(sm.group(1))
        results.append(SearchResultItem(title=title, url=url, snippet=snippet))
    return results


def _decode_ddg_href(href: str) -> str:
    href = html_mod.unescape(href).strip()
    if "uddg=" in href:
        try:
            parsed = urllib.parse.urlparse(href)
            params = urllib.parse.parse_qs(parsed.query)
            if params.get("uddg"):
                return params["uddg"][0]
        except Exception:
            pass
    return href


async def _ddg_search(ctx: _SearchContext, query: str) -> List[SearchResultItem]:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
        )
    }
    params = {"q": query}
    async with ctx.session.get(
        "https://html.duckduckgo.com/html/",
        params=params,
        headers=headers,
        timeout=ctx.timeout,
    ) as resp:
        if resp.status != 200:
            return []
        text = await resp.text()

    title_matches = re.findall(
        r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
        text,
        re.S,
    )
    snippet_matches = re.findall(
        r'class="result__snippet"[^>]*>(.*?)</a>',
        text,
        re.S,
    )

    results: List[SearchResultItem] = []
    for idx, (href, title_frag) in enumerate(title_matches):
        title = _clean_html_fragment(title_frag)
        if not title:
            continue
        url = _decode_ddg_href(href)
        snippet = ""
        if idx < len(snippet_matches):
            snippet = _clean_html_fragment(snippet_matches[idx])
        results.append(SearchResultItem(title=title, url=url, snippet=snippet))
    return results


def _collect_provider_keys(provider_settings: Optional[Dict[str, Any]]) -> Dict[str, str]:
    ps = provider_settings if isinstance(provider_settings, dict) else {}
    keys: Dict[str, str] = {}
    for name, key in (
        ("tavily", ps.get("websearch_tavily_key")),
        ("bocha", ps.get("websearch_bocha_key")),
        ("brave", ps.get("websearch_brave_key")),
    ):
        k = _norm_key(key)
        if k:
            keys[name] = k
    return keys


async def perform_web_search(
    query: str,
    provider_settings: Optional[Dict[str, Any]] = None,
    timeout_sec: Optional[int] = None,
) -> Optional[str]:
    """执行联网搜索，返回格式化的搜索结果文本。

    搜索后端优先级：Tavily / BoCha / Brave（读取 AstrBot 配置的搜索 Key），
    均不可用时回退到无需 Key 的 Bing，最后尝试 DuckDuckGo。
    全部失败或无结果时返回 None。
    """
    query = (query or "").strip()
    if not query:
        return None
    if aiohttp is None:
        return None

    timeout_total = timeout_sec if isinstance(timeout_sec, int) and timeout_sec > 0 else _SEARCH_TIMEOUT_SEC
    keys = _collect_provider_keys(provider_settings)

    try:
        timeout = aiohttp.ClientTimeout(total=timeout_total)
        async with aiohttp.ClientSession(trust_env=True) as session:
            ctx = _SearchContext(session=session, timeout=timeout)

            if keys.get("tavily"):
                try:
                    results = await _tavily_search(ctx, keys["tavily"], query)
                    if results:
                        return _fmt_results(results)
                except Exception:
                    pass

            if keys.get("bocha"):
                try:
                    results = await _bocha_search(ctx, keys["bocha"], query)
                    if results:
                        return _fmt_results(results)
                except Exception:
                    pass

            if keys.get("brave"):
                try:
                    results = await _brave_search(ctx, keys["brave"], query)
                    if results:
                        return _fmt_results(results)
                except Exception:
                    pass

            try:
                results = await _bing_search(ctx, query)
                if results:
                    return _fmt_results(results)
            except Exception:
                pass

            try:
                results = await _ddg_search(ctx, query)
                if results:
                    return _fmt_results(results)
            except Exception:
                pass
    except Exception:
        return None

    return None
