"""
Helius Solana RPC + DAS API client.

We use Helius for two things:
  1. DAS getAssetBatch — enrich Bags mints with Metaplex metadata
  2. Standard Solana RPC — timestamp/slot anchoring when needed

Endpoint:  https://mainnet.helius-rpc.com/?api-key=<key>
Auth:      API key in query string (JSON-RPC body has no auth)
"""
from __future__ import annotations

import os
from typing import Any

import httpx

HELIUS_RPC = "https://mainnet.helius-rpc.com/"
BATCH_LIMIT = 100  # DAS getAssetBatch supports up to 1000; 100 is a safe default


class HeliusError(RuntimeError):
    pass


class HeliusClient:
    def __init__(self, api_key: str | None = None, base_url: str = HELIUS_RPC) -> None:
        self._api_key = api_key or os.environ.get("HELIUS_API_KEY")
        if not self._api_key:
            raise RuntimeError("HELIUS_API_KEY missing — set env or pass explicitly")
        self._url = f"{base_url.rstrip('/')}/?api-key={self._api_key}"
        self._client = httpx.Client(timeout=httpx.Timeout(60.0, connect=10.0))

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "HeliusClient":
        return self

    def __exit__(self, *_exc: Any) -> None:
        self.close()

    def rpc(self, method: str, params: Any) -> Any:
        payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
        r = self._client.post(self._url, json=payload, headers={"content-type": "application/json"})
        r.raise_for_status()
        data = r.json()
        if "error" in data:
            raise HeliusError(f"{method} failed: {data['error']}")
        return data.get("result")

    def get_asset_batch(self, ids: list[str]) -> list[dict | None]:
        out: list[dict | None] = []
        for i in range(0, len(ids), BATCH_LIMIT):
            chunk = ids[i : i + BATCH_LIMIT]
            res = self.rpc("getAssetBatch", {"ids": chunk})
            out.extend(res or [])
        return out

    @staticmethod
    def extract_metadata(asset: dict | None) -> dict:
        """Flatten the nested DAS response into the fields Signal actually needs."""
        if not asset:
            return {}
        content = asset.get("content") or {}
        md = content.get("metadata") or {}
        links = content.get("links") or {}
        token_info = asset.get("token_info") or {}
        supply = asset.get("supply") or {}
        return {
            "name": md.get("name"),
            "symbol": md.get("symbol"),
            "description": md.get("description"),
            "image": links.get("image") or md.get("image"),
            "interface": asset.get("interface"),
            "decimals": token_info.get("decimals"),
            "token_supply": supply.get("print_max_supply") or token_info.get("supply"),
            "last_indexed_slot": asset.get("last_indexed_slot"),
            "mutable": asset.get("mutable"),
            "burnt": asset.get("burnt"),
        }
