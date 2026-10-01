"""Seed Singapore logistics demo: shippers, SHP shipments, inventory, tracking."""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import delete, select

from app.db.models import (
    ChatLog,
    Coupon,
    Customer,
    ExchangeRequest,
    InventoryLot,
    Invoice,
    Order,
    Payment,
    PendingAction,
    SatisfactionRating,
    SessionHandoff,
    SessionIdentity,
    Ticket,
    ToolIdempotency,
    TrackingEvent,
    UploadedDocument,
)
from app.db.session import SyncSessionLocal, init_db


def seed_all(force: bool = False) -> None:
    init_db(reset=force)
    with SyncSessionLocal() as db:
        existing = db.scalar(select(Order).limit(1))
        if existing and not force:
            _patch_live_demo_fields(db)
            return
        if force:
            for model in (
                ToolIdempotency,
                PendingAction,
                SessionIdentity,
                SatisfactionRating,
                SessionHandoff,
                ExchangeRequest,
                Invoice,
                TrackingEvent,
                Coupon,
                ChatLog,
                Ticket,
                Payment,
                Order,
                InventoryLot,
                UploadedDocument,
                Customer,
            ):
                db.execute(delete(model))

        now = datetime.utcnow()
        customers = [
            Customer(
                customer_id="CUS-001",
                name="Harbour Brands Pte Ltd",
                email="ops@harbourbrands.sg",
                phone="+65 9123 4001",
                loyalty_points=1280,
                tier="gold",
                created_at=now - timedelta(days=120),
            ),
            Customer(
                customer_id="CUS-002",
                name="Little Red Dot Retail",
                email="cs@lrd.sg",
                phone="+65 9123 4002",
                loyalty_points=420,
                tier="standard",
                created_at=now - timedelta(days=80),
            ),
            Customer(
                customer_id="CUS-003",
                name="Tuas Components SG",
                email="warehouse@tuascomp.sg",
                phone="+65 9123 4003",
                loyalty_points=90,
                tier="standard",
                created_at=now - timedelta(days=40),
            ),
            Customer(
                customer_id="CUS-004",
                name="Orchard Premium Co",
                email="vip@orchardpremium.sg",
                phone="+65 9123 4004",
                loyalty_points=2100,
                tier="vip",
                created_at=now - timedelta(days=15),
            ),
        ]
        db.add_all(customers)

        orders = [
            Order(
                order_id="SHP-2001",
                customer_id="CUS-001",
                product="Carton mix — skincare B2C",
                quantity=24,
                amount=86.40,
                currency="SGD",
                status="shipped",
                shipping_address="Blk 123 Jurong East St 13, Singapore 600123",
                tracking_no="NVSG88990011",
                carrier="Ninja Van",
                created_at=now - timedelta(days=2),
                notes="Handed to Ninja Van at Jurong West DC",
            ),
            Order(
                order_id="SHP-2002",
                customer_id="CUS-002",
                product="Document pack — contracts",
                quantity=1,
                amount=12.50,
                currency="SGD",
                status="delivered",
                shipping_address="1 Raffles Place, Singapore 048616",
                tracking_no="SPSG44556677",
                carrier="SingPost",
                created_at=now - timedelta(days=10),
                notes="Delivered to lobby",
            ),
            Order(
                order_id="SHP-2003",
                customer_id="CUS-003",
                product="Pallet — industrial fasteners",
                quantity=1,
                amount=180.0,
                currency="SGD",
                status="processing",
                shipping_address="Tuas Link 1, Singapore 638588",
                tracking_no=None,
                carrier=None,
                created_at=now - timedelta(hours=6),
                notes="Picking in zone B",
            ),
            Order(
                order_id="SHP-2004",
                customer_id="CUS-001",
                product="Express pouch — samples",
                quantity=3,
                amount=45.0,
                currency="SGD",
                status="paid",
                shipping_address="78 Shenton Way, Singapore 079120",
                tracking_no=None,
                carrier="GrabExpress",
                created_at=now - timedelta(hours=18),
                notes="Awaiting same-day GrabExpress booking",
            ),
            Order(
                order_id="SHP-2005",
                customer_id="CUS-004",
                product="High-value hampers",
                quantity=8,
                amount=420.0,
                currency="SGD",
                status="delivered",
                shipping_address="391 Orchard Rd, Singapore 238872",
                tracking_no="NVSG11223344",
                carrier="Ninja Van",
                created_at=now - timedelta(days=20),
                notes="VIP shipper — white-glove note",
            ),
            # Legacy alias ids for older demos / tests
            Order(
                order_id="ORD-1001",
                customer_id="CUS-001",
                product="Alias of SHP-2001",
                quantity=24,
                amount=86.40,
                currency="SGD",
                status="shipped",
                shipping_address="Blk 123 Jurong East St 13, Singapore 600123",
                tracking_no="NVSG88990011",
                carrier="Ninja Van",
                created_at=now - timedelta(days=2),
                notes="Legacy ORD alias",
            ),
        ]
        db.add_all(orders)

        payments = [
            Payment(
                payment_id="PAY-9001",
                order_id="SHP-2001",
                amount=86.40,
                currency="SGD",
                method="paynow",
                status="succeeded",
                transaction_ref="PN20240901001",
                paid_at=now - timedelta(days=2, hours=1),
                created_at=now - timedelta(days=2, hours=1),
            ),
            Payment(
                payment_id="PAY-9002",
                order_id="SHP-2002",
                amount=12.50,
                currency="SGD",
                method="card",
                status="succeeded",
                transaction_ref="CARD20240820002",
                paid_at=now - timedelta(days=10, hours=2),
                created_at=now - timedelta(days=10, hours=2),
            ),
            Payment(
                payment_id="PAY-9003",
                order_id="SHP-2003",
                amount=180.0,
                currency="SGD",
                method="bank_transfer",
                status="pending",
                transaction_ref=None,
                paid_at=None,
                created_at=now - timedelta(hours=6),
                notes="Awaiting GIRO",
            ),
            Payment(
                payment_id="PAY-9004",
                order_id="SHP-2004",
                amount=45.0,
                currency="SGD",
                method="paynow",
                status="succeeded",
                transaction_ref="PN20240914004",
                paid_at=now - timedelta(hours=18),
                created_at=now - timedelta(hours=18),
            ),
            Payment(
                payment_id="PAY-9005",
                order_id="SHP-2005",
                amount=420.0,
                currency="SGD",
                method="card",
                status="succeeded",
                transaction_ref="CARD20240801005",
                paid_at=now - timedelta(days=20, hours=3),
                created_at=now - timedelta(days=20, hours=3),
            ),
        ]
        db.add_all(payments)

        tracking = [
            TrackingEvent(
                order_id="SHP-2001",
                tracking_no="NVSG88990011",
                status_code="picked_up",
                description="Parcel collected at Jurong West DC",
                location="Jurong West, Singapore",
                event_time=now - timedelta(days=2, hours=2),
            ),
            TrackingEvent(
                order_id="SHP-2001",
                tracking_no="NVSG88990011",
                status_code="in_transit",
                description="At Ninja Van sorting hub",
                location="Tampines hub",
                event_time=now - timedelta(days=1, hours=18),
            ),
            TrackingEvent(
                order_id="SHP-2001",
                tracking_no="NVSG88990011",
                status_code="out_for_delivery",
                description="Out for delivery",
                location="Jurong East",
                event_time=now - timedelta(hours=5),
            ),
            TrackingEvent(
                order_id="SHP-2002",
                tracking_no="SPSG44556677",
                status_code="delivered",
                description="Delivered and signed",
                location="Raffles Place",
                event_time=now - timedelta(days=8),
            ),
            TrackingEvent(
                order_id="SHP-2005",
                tracking_no="NVSG11223344",
                status_code="delivered",
                description="Delivered to concierge",
                location="Orchard",
                event_time=now - timedelta(days=18),
            ),
            TrackingEvent(
                order_id="ORD-1001",
                tracking_no="NVSG88990011",
                status_code="out_for_delivery",
                description="Out for delivery (legacy alias)",
                location="Jurong East",
                event_time=now - timedelta(hours=5),
            ),
        ]
        db.add_all(tracking)

        inventory = [
            InventoryLot(
                sku="SKU-PALLET-WRAP",
                name="Stretch wrap roll 500mm",
                qty_on_hand=420,
                zone="A",
                bin_code="A-12",
                uom="ROLL",
            ),
            InventoryLot(
                sku="SKU-CARTON-M",
                name="Medium shipper carton",
                qty_on_hand=1800,
                zone="A",
                bin_code="A-04",
                uom="EA",
            ),
            InventoryLot(
                sku="SKU-LABEL-A6",
                name="Thermal label A6",
                qty_on_hand=9500,
                zone="C",
                bin_code="C-02",
                uom="EA",
            ),
            InventoryLot(
                sku="WH-BIN-A12",
                name="Demo bin alias for clarify prompts",
                qty_on_hand=12,
                zone="A",
                bin_code="A-12",
                uom="EA",
            ),
        ]
        db.add_all(inventory)

        coupons = [
            Coupon(
                coupon_code="FREESHIP",
                customer_id="CUS-001",
                title="Waive handling once",
                discount_label="1 free pick",
                status="active",
                expires_at=now + timedelta(days=14),
            ),
            Coupon(
                coupon_code="VIP100",
                customer_id="CUS-004",
                title="VIP SGD 100 credit",
                discount_label="SGD 100",
                status="active",
                expires_at=now + timedelta(days=60),
            ),
        ]
        db.add_all(coupons)

        db.add(
            Ticket(
                ticket_id="T-SEED01",
                session_id="care-demo-1",
                order_id="SHP-2005",
                category="complaint",
                status="open",
                summary="VIP hamper delivery follow-up (seeded SLA demo)",
                priority="urgent",
                sla_minutes=5,
                sla_due_at=now - timedelta(minutes=20),
                assigned_to="human_queue",
                created_at=now - timedelta(hours=1),
            )
        )
        db.commit()


def _patch_live_demo_fields(db) -> None:
    """Fill new columns / inventory on an already-seeded SQLite file."""
    tiers = {
        "CUS-001": "gold",
        "CUS-002": "standard",
        "CUS-003": "standard",
        "CUS-004": "vip",
    }
    for c in db.scalars(select(Customer)).all():
        if c.customer_id in tiers:
            c.tier = tiers[c.customer_id]

    if not db.scalar(select(InventoryLot).limit(1)):
        db.add_all(
            [
                InventoryLot(
                    sku="SKU-PALLET-WRAP",
                    name="Stretch wrap roll 500mm",
                    qty_on_hand=420,
                    zone="A",
                    bin_code="A-12",
                    uom="ROLL",
                ),
                InventoryLot(
                    sku="SKU-CARTON-M",
                    name="Medium shipper carton",
                    qty_on_hand=1800,
                    zone="A",
                    bin_code="A-04",
                    uom="EA",
                ),
            ]
        )

    seed_ticket = db.scalar(select(Ticket).where(Ticket.ticket_id == "T-SEED01"))
    if not seed_ticket:
        db.add(
            Ticket(
                ticket_id="T-SEED01",
                session_id="care-demo-1",
                order_id="SHP-2005",
                category="complaint",
                status="open",
                summary="VIP hamper delivery follow-up (seeded SLA demo)",
                priority="urgent",
                sla_minutes=5,
                sla_due_at=datetime.utcnow() - timedelta(minutes=20),
                assigned_to="human_queue",
            )
        )
    else:
        seed_ticket.session_id = "care-demo-1"
    db.commit()


def seed_orders(force: bool = False) -> None:
    seed_all(force=force)
