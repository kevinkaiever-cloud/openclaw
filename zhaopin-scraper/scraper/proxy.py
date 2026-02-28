"""代理池管理 — 轮换 IP 以规避反爬封禁"""

from __future__ import annotations

import itertools
import logging
import random
from typing import Optional

import requests

logger = logging.getLogger(__name__)


class ProxyPool:
    """简单的轮换代理池。

    支持三种模式:
    - 无代理（直连）
    - 静态代理列表（配置文件/环境变量提供）
    - 远程代理 API（可选扩展）
    """

    def __init__(self, proxies: Optional[list[str]] = None) -> None:
        self._proxies: list[str] = list(proxies or [])
        self._cycle = itertools.cycle(self._proxies) if self._proxies else None

    @property
    def available(self) -> bool:
        return bool(self._proxies)

    def get(self) -> Optional[dict[str, str]]:
        """返回下一个代理，格式为 requests 可用的 dict，无代理时返回 None。"""
        if not self._cycle:
            return None
        proxy = next(self._cycle)
        return {"http": proxy, "https": proxy}

    def get_random(self) -> Optional[dict[str, str]]:
        """随机返回一个代理。"""
        if not self._proxies:
            return None
        proxy = random.choice(self._proxies)
        return {"http": proxy, "https": proxy}

    def add(self, proxy: str) -> None:
        self._proxies.append(proxy)
        self._cycle = itertools.cycle(self._proxies)

    def remove(self, proxy: str) -> None:
        self._proxies = [p for p in self._proxies if p != proxy]
        self._cycle = itertools.cycle(self._proxies) if self._proxies else None

    def refresh_from_api(self, api_url: str) -> int:
        """从远程代理 API 拉取代理列表（JSON 数组格式），返回新增数量。"""
        try:
            resp = requests.get(api_url, timeout=10)
            resp.raise_for_status()
            new_proxies: list[str] = resp.json()
            added = 0
            for p in new_proxies:
                if p not in self._proxies:
                    self._proxies.append(p)
                    added += 1
            self._cycle = itertools.cycle(self._proxies) if self._proxies else None
            logger.info("代理池刷新: 新增 %d 个代理，当前共 %d 个", added, len(self._proxies))
            return added
        except Exception:
            logger.exception("从代理 API 拉取失败: %s", api_url)
            return 0

    def __len__(self) -> int:
        return len(self._proxies)

    def __repr__(self) -> str:
        return f"ProxyPool(count={len(self._proxies)})"
