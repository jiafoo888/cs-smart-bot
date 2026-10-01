"""Clarification slot-filling (MVP C4)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_SESSION: dict[str, "ClarifyState"] = {}


@dataclass
class ClarifyState:
    intent: str | None = None
    missing: list[str] = field(default_factory=list)
    slots: dict[str, str] = field(default_factory=dict)
    turns: int = 0


def get_clarify(session_id: str) -> ClarifyState | None:
    return _SESSION.get(session_id)


def clear_clarify(session_id: str) -> None:
    _SESSION.pop(session_id, None)


def set_clarify(session_id: str, state: ClarifyState) -> ClarifyState:
    _SESSION[session_id] = state
    return state


def extract_shipment_id(text: str) -> str | None:
    m = re.search(r"(?:SHP|ORD)-\d{4}", text.upper())
    return m.group(0) if m else None


def extract_sku(text: str) -> str | None:
    m = re.search(r"\bSKU-[\w-]+\b", text.upper())
    if m:
        return m.group(0)
    m = re.search(r"\b([A-Z]{2,6}-\d{3,5})\b", text.upper())
    return m.group(1) if m else None


def needs_clarification(text: str) -> ClarifyState | None:
    """Return a ClarifyState when the user ask is ambiguous and needs slots."""
    t = text.lower().strip()
    shp = extract_shipment_id(text)
    sku = extract_sku(text)

    trackish = any(
        k in t
        for k in (
            "where is my parcel",
            "where is my shipment",
            "where is my package",
            "track my",
            "track parcel",
            "track shipment",
            "status of my shipment",
            "where's my",
        )
    ) or (t in ("track", "tracking", "where is it"))

    if trackish and not shp:
        return ClarifyState(
            intent="track_shipment",
            missing=["shipment_id"],
            slots={},
            turns=0,
        )

    invish = any(
        k in t
        for k in ("inventory", "stock level", "on hand", "on-hand", "bin location", "where is sku")
    ) and not sku
    if invish:
        return ClarifyState(
            intent="inventory_lookup",
            missing=["sku"],
            slots={},
            turns=0,
        )

    claimish = any(k in t for k in ("claim", "damaged", "damage", "lost freight", "short shipment"))
    claim_policy = any(
        k in t for k in ("policy", "window", "how long", "what is", "what's", "sla", "days")
    )
    if claimish and claim_policy and not any(
        k in t for k in ("open a claim", "file a claim", "start a claim", "i want to claim")
    ):
        return None  # let FAQ / policy RAG handle
    if claimish and not shp:
        return ClarifyState(
            intent="freight_claim",
            missing=["shipment_id", "description"],
            slots={},
            turns=0,
        )
    if claimish and shp and len(t.split()) < 6:
        return ClarifyState(
            intent="freight_claim",
            missing=["description"],
            slots={"shipment_id": shp},
            turns=0,
        )

    return None


def apply_user_fill(session_id: str, text: str, existing: ClarifyState) -> ClarifyState | str:
    """
    Merge user reply into slots.
    Returns updated ClarifyState if still missing, or a synthetic resolved query string.
    """
    existing.turns += 1
    shp = extract_shipment_id(text)
    sku = extract_sku(text)

    if "shipment_id" in existing.missing and shp:
        existing.slots["shipment_id"] = shp
        existing.missing = [m for m in existing.missing if m != "shipment_id"]

    if "sku" in existing.missing and sku:
        existing.slots["sku"] = sku
        existing.missing = [m for m in existing.missing if m != "sku"]

    if "description" in existing.missing:
        # any free text longer than a bare id counts as description
        if not shp or len(text.strip()) > len(shp) + 3:
            desc = text.strip()
            if shp:
                desc = re.sub(re.escape(shp), "", desc, flags=re.I).strip(" ,.-")
            if desc:
                existing.slots["description"] = desc
                existing.missing = [m for m in existing.missing if m != "description"]

    if existing.missing and existing.turns >= 2:
        # best-effort: stop clarifying
        clear_clarify(session_id)
        if existing.intent == "track_shipment":
            return (
                "I still need a shipment id like SHP-2001 to track. "
                "You can also escalate to a human if you don't have it."
            )
        return (
            "I'm missing a few details to finish that. "
            "Share the SHP id / SKU, or say escalate for a human."
        )

    if existing.missing:
        set_clarify(session_id, existing)
        return existing

    clear_clarify(session_id)
    if existing.intent == "track_shipment":
        return f"Track shipment {existing.slots['shipment_id']}"
    if existing.intent == "inventory_lookup":
        return f"Inventory lookup for {existing.slots['sku']}"
    if existing.intent == "freight_claim":
        return (
            f"Open freight claim for {existing.slots.get('shipment_id', '')}: "
            f"{existing.slots.get('description', '')}"
        )
    return text


def clarify_prompt(state: ClarifyState) -> str:
    if state.intent == "track_shipment":
        return (
            "I can track that — what's the shipment id? "
            "It looks like SHP-2001 (demo: SHP-2001, SHP-2002)."
        )
    if state.intent == "inventory_lookup":
        return "Which SKU should I check? Example: SKU-PALLET-WRAP or WH-BIN-A12."
    if state.intent == "freight_claim":
        if "shipment_id" in state.missing:
            return "To open a claim I need the shipment id (e.g. SHP-2001) and a short damage description."
        return "Please describe the damage or loss in one short sentence."
    return "Could you share a bit more detail so I can look that up?"
