"""Product catalog: structured lookup + compare for CS agents."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from app.config import get_settings

ROOT = Path(__file__).resolve().parent.parent
CATALOG_PATH = ROOT / "data" / "catalog" / "products.json"


@lru_cache(maxsize=1)
def load_products() -> list[dict]:
    if not CATALOG_PATH.exists():
        return []
    try:
        data = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def catalog_status() -> dict:
    products = load_products()
    return {
        "path": str(CATALOG_PATH),
        "exists": CATALOG_PATH.exists(),
        "count": len(products),
    }


def reload_products() -> list[dict]:
    load_products.cache_clear()
    return load_products()


def get_product(sku_or_name: str) -> dict | None:
    q = (sku_or_name or "").strip().lower()
    if not q:
        return None
    products = load_products()
    for p in products:
        if p["sku"].lower() == q or p["name"].lower() == q:
            return p
    # fuzzy contains
    for p in products:
        if q in p["name"].lower() or q in p["sku"].lower():
            return p
    return None


def search_products(query: str, limit: int = 8) -> list[dict]:
    q = (query or "").strip().lower()
    products = load_products()
    if not q:
        return products[:limit]
    scored: list[tuple[int, dict]] = []
    for p in products:
        blob = " ".join(
            [
                p.get("sku", ""),
                p.get("name", ""),
                p.get("category", ""),
                p.get("summary", ""),
                p.get("best_for", ""),
                p.get("compare_group", ""),
                " ".join(p.get("highlights") or []),
            ]
        ).lower()
        score = 0
        for token in re.findall(r"[a-z0-9\u4e00-\u9fff]+", q):
            if token in blob:
                score += 2
            if token in p.get("name", "").lower():
                score += 3
            if token == p.get("compare_group"):
                score += 4
            if token == p.get("category"):
                score += 3
        if score:
            scored.append((score, p))
    scored.sort(key=lambda x: (-x[0], x[1].get("price", 0)))
    return [p for _, p in scored[:limit]]


def products_in_group(group: str) -> list[dict]:
    g = (group or "").strip().lower()
    return [p for p in load_products() if (p.get("compare_group") or "").lower() == g]


def compare_products(a: str, b: str | None = None) -> dict:
    """Compare two products, or all items in a compare_group if only one hint given."""
    if not load_products():
        return {
            "ok": False,
            "error": "Product catalog is empty on this server. Ops → Re-ingest after deploy includes data/catalog.",
        }
    left = get_product(a)
    right = get_product(b) if b else None
    if left and right:
        return _pair_compare(left, right)
    if left and not b:
        peers = [p for p in products_in_group(left.get("compare_group", "")) if p["sku"] != left["sku"]]
        if peers:
            return _pair_compare(left, peers[0], note=f"Closest peer in {left.get('compare_group')} group")
        return {"ok": False, "error": f"No comparison peer found for {left['name']}"}
    # try treat `a` as category/group keyword
    group_hits = products_in_group(a) or search_products(a, limit=4)
    if len(group_hits) >= 2:
        return _pair_compare(group_hits[0], group_hits[1], note=f"Top matches for “{a}”")
    if left:
        return {"ok": True, "products": [left], "message": "Only one product matched; share another name to compare."}
    return {"ok": False, "error": f"Could not find products to compare for “{a}”" + (f" vs “{b}”" if b else "")}


def _pair_compare(left: dict, right: dict, note: str | None = None) -> dict:
    keys = sorted(set(left.get("specs", {})) | set(right.get("specs", {})))
    spec_rows = []
    for k in keys:
        spec_rows.append(
            {
                "field": k,
                left["sku"]: left.get("specs", {}).get(k, "—"),
                right["sku"]: right.get("specs", {}).get(k, "—"),
            }
        )
    return {
        "ok": True,
        "note": note,
        "left": left,
        "right": right,
        "price_diff": round(float(right["price"]) - float(left["price"]), 2),
        "spec_rows": spec_rows,
        "verdict": _verdict(left, right),
    }


def _verdict(left: dict, right: dict) -> str:
    if left["price"] < right["price"]:
        cheaper, pricier = left, right
    else:
        cheaper, pricier = right, left
    return (
        f"{cheaper['name']} is cheaper (¥{cheaper['price']}). "
        f"{pricier['name']} costs ¥{pricier['price']} and is aimed at: {pricier.get('best_for')}."
    )


def extract_product_query(text: str) -> str | None:
    """Pull product name / sku from user text when possible."""
    t = text or ""
    m = re.search(r"SKU-[A-Z0-9-]+", t.upper())
    if m:
        return m.group(0)
    known = sorted((p["name"] for p in load_products()), key=len, reverse=True)
    low = t.lower()
    for name in known:
        if name.lower() in low:
            return name
    return None


def catalog_to_markdown() -> str:
    """Render catalog as markdown for RAG ingest."""
    lines = ["# SteelShop Product Catalog", ""]
    for p in load_products():
        lines.append(f"## {p['name']} ({p['sku']})")
        lines.append(f"Category: {p['category']} · Compare group: {p['compare_group']}")
        lines.append(f"Price: ¥{p['price']} {p.get('currency', 'CNY')}")
        lines.append(p.get("summary", ""))
        lines.append("Highlights: " + "; ".join(p.get("highlights") or []))
        specs = p.get("specs") or {}
        if specs:
            lines.append("Specs: " + ", ".join(f"{k}={v}" for k, v in specs.items()))
        lines.append(f"Best for: {p.get('best_for', '')}")
        lines.append(f"Compatibility: {p.get('compatibility', '')}")
        lines.append(f"In the box: {', '.join(p.get('in_box') or [])}")
        lines.append("")
    return "\n".join(lines)


def ensure_catalog_markdown() -> Path:
    """Write/refresh markdown sheet used by policy ingest."""
    settings = get_settings()
    out = settings.policies_dir / "product_catalog.md"
    settings.policies_dir.mkdir(parents=True, exist_ok=True)
    out.write_text(catalog_to_markdown(), encoding="utf-8")
    return out
