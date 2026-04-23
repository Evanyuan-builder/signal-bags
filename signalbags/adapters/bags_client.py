"""
Bags.fm public API client.

Base URL:  https://public-api-v2.bags.fm/api/v1/
Auth:      x-api-key header
Rate:      1000 req / hour / IP (free tier may be lower — monitor on 429)

Endpoint paths verified against docs.bags.fm on 2026-04-23.
Response envelope is consistently {"success": bool, "response": <payload>}.
We unwrap `response` here so callers get the payload directly.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import httpx

BAGS_BASE_URL = "https://public-api-v2.bags.fm/api/v1"


@dataclass
class BagsLaunchTx:
    unsigned_tx_base64: str
    mint: str | None
    raw: dict


@dataclass
class BagsFeedItem:
    name: str
    symbol: str
    description: str
    image: str
    token_mint: str
    status: str
    twitter: str
    website: str
    account_keys: list[str]
    raw: dict


class BagsAPIError(RuntimeError):
    pass


class BagsClient:
    def __init__(self, api_key: str | None = None, base_url: str = BAGS_BASE_URL) -> None:
        self._api_key = api_key or os.environ.get("BAGS_API_KEY")
        if not self._api_key:
            raise RuntimeError("BAGS_API_KEY missing — set env or pass explicitly")
        self._base = base_url.rstrip("/")
        self._client = httpx.Client(
            base_url=self._base,
            headers={"x-api-key": self._api_key},
            timeout=httpx.Timeout(30.0, connect=10.0),
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "BagsClient":
        return self

    def __exit__(self, *_exc: Any) -> None:
        self.close()

    def _unwrap(self, r: httpx.Response) -> Any:
        r.raise_for_status()
        data = r.json()
        if not data.get("success", False):
            raise BagsAPIError(f"Bags API returned success=false: {data}")
        return data.get("response")

    def _get(self, path: str, params: dict | None = None) -> Any:
        return self._unwrap(self._client.get(path, params=params))

    def _post(self, path: str, json: dict) -> Any:
        return self._unwrap(self._client.post(path, json=json))

    def auth_me(self) -> dict:
        return self._get("/auth/me")

    def get_feed(self) -> list[BagsFeedItem]:
        items = self._get("/token-launch/feed") or []
        return [
            BagsFeedItem(
                name=i.get("name", ""),
                symbol=i.get("symbol", ""),
                description=i.get("description", ""),
                image=i.get("image", ""),
                token_mint=i.get("tokenMint", ""),
                status=i.get("status", ""),
                twitter=i.get("twitter", ""),
                website=i.get("website", ""),
                account_keys=i.get("accountKeys", []) or [],
                raw=i,
            )
            for i in items
        ]

    def get_pools(self) -> list[dict]:
        return self._get("/solana/bags/pools") or []

    def get_pool_by_mint(self, token_mint: str) -> dict:
        return self._get("/solana/bags/pools/token-mint", params={"tokenMint": token_mint})

    def get_creators(self, token_mint: str) -> dict:
        return self._get("/token-launch/creator/v3", params={"tokenMint": token_mint})

    def get_lifetime_fees(self, token_mint: str) -> dict:
        return self._get("/token-launch/lifetime-fees", params={"tokenMint": token_mint})

    def get_claim_stats(self, token_mint: str) -> dict:
        return self._get("/token-launch/claim-stats", params={"tokenMint": token_mint})

    def create_token_info(self, name: str, symbol: str, description: str, image_url: str, **extra: Any) -> dict:
        payload = {"name": name, "symbol": symbol, "description": description, "image": image_url, **extra}
        return self._post("/token-launch/create-token-info", payload)

    def build_launch_tx(self, **payload: Any) -> BagsLaunchTx:
        """
        Request-body schema is documented at
        https://docs.bags.fm/api-reference/create-token-launch-transaction.
        We pass through kwargs and return the raw response alongside the
        unsigned tx + mint so callers can inspect on failure.
        """
        data = self._post("/token-launch/create-launch-transaction", payload)
        tx = data.get("transaction") or data.get("unsignedTransaction")
        return BagsLaunchTx(unsigned_tx_base64=tx, mint=data.get("mint"), raw=data)
