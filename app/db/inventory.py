"""Inventory lots for warehouse demo."""

from __future__ import annotations

from sqlalchemy import select

from app.db.models import InventoryLot
from app.db.session import SyncSessionLocal


def lookup_sku(sku: str) -> dict:
    code = (sku or "").strip().upper()
    if not code:
        return {"ok": False, "error": "SKU is required"}
    with SyncSessionLocal() as db:
        lot = db.scalar(select(InventoryLot).where(InventoryLot.sku == code))
        if not lot:
            # try partial
            lot = db.scalar(select(InventoryLot).where(InventoryLot.sku.contains(code)))
        if not lot:
            return {"ok": False, "error": f"SKU {code} not found", "sku": code}
        return {
            "ok": True,
            "sku": lot.sku,
            "name": lot.name,
            "qty_on_hand": lot.qty_on_hand,
            "zone": lot.zone,
            "bin": lot.bin_code,
            "uom": lot.uom,
        }


def list_inventory(limit: int = 50) -> list[dict]:
    with SyncSessionLocal() as db:
        rows = db.scalars(select(InventoryLot).limit(limit)).all()
        return [
            {
                "sku": r.sku,
                "name": r.name,
                "qty_on_hand": r.qty_on_hand,
                "zone": r.zone,
                "bin": r.bin_code,
                "uom": r.uom,
            }
            for r in rows
        ]
