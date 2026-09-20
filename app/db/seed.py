"""Seed demo customers, orders, payments, tracking, loyalty."""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import delete, select

from app.db.models import (
    ChatLog,
    Coupon,
    Customer,
    ExchangeRequest,
    Invoice,
    Order,
    Payment,
    SatisfactionRating,
    SessionHandoff,
    Ticket,
    TrackingEvent,
)
from app.db.session import SyncSessionLocal, init_db


def seed_all(force: bool = False) -> None:
    init_db(reset=force)
    with SyncSessionLocal() as db:
        existing = db.scalar(select(Order).limit(1))
        if existing and not force:
            return
        if force:
            for model in (
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
                Customer,
            ):
                db.execute(delete(model))

        now = datetime.utcnow()
        customers = [
            Customer(
                customer_id="CUS-001",
                name="Alice Chen",
                email="alice@example.com",
                phone="13800001001",
                loyalty_points=1280,
                created_at=now - timedelta(days=120),
            ),
            Customer(
                customer_id="CUS-002",
                name="Bob Wang",
                email="bob@example.com",
                phone="13800001002",
                loyalty_points=420,
                created_at=now - timedelta(days=80),
            ),
            Customer(
                customer_id="CUS-003",
                name="Carol Li",
                email="carol@example.com",
                phone="13800001003",
                loyalty_points=90,
                created_at=now - timedelta(days=40),
            ),
            Customer(
                customer_id="CUS-004",
                name="David Zhang",
                email="david@example.com",
                phone="13800001004",
                loyalty_points=2100,
                created_at=now - timedelta(days=15),
            ),
        ]
        db.add_all(customers)

        orders = [
            Order(
                order_id="ORD-1001",
                customer_id="CUS-001",
                product="Wireless Earbuds Pro",
                quantity=1,
                amount=299.0,
                status="shipped",
                shipping_address="1 Century Ave, Pudong, Shanghai",
                tracking_no="SF1234567890",
                carrier="SF",
                created_at=now - timedelta(days=2),
                notes="Shipped to Shanghai",
            ),
            Order(
                order_id="ORD-1002",
                customer_id="CUS-002",
                product="Mechanical Keyboard",
                quantity=1,
                amount=459.0,
                status="delivered",
                shipping_address="88 Wensan Rd, Xihu, Hangzhou",
                tracking_no="YT9876543210",
                carrier="YT",
                created_at=now - timedelta(days=10),
                notes="Delivered in Hangzhou",
            ),
            Order(
                order_id="ORD-1003",
                customer_id="CUS-003",
                product="Monitor Arm",
                quantity=2,
                amount=258.0,
                status="processing",
                shipping_address="Science Park, Nanshan, Shenzhen",
                tracking_no=None,
                carrier=None,
                created_at=now - timedelta(hours=6),
                notes="Picking in warehouse",
            ),
            Order(
                order_id="ORD-1004",
                customer_id="CUS-001",
                product="USB-C Hub",
                quantity=1,
                amount=189.0,
                status="paid",
                shipping_address="1 Century Ave, Pudong, Shanghai",
                tracking_no=None,
                carrier=None,
                created_at=now - timedelta(hours=18),
                notes="Awaiting dispatch",
            ),
            Order(
                order_id="ORD-1005",
                customer_id="CUS-004",
                product="Ergonomic Chair",
                quantity=1,
                amount=1299.0,
                status="delivered",
                shipping_address="Wangjing SOHO, Chaoyang, Beijing",
                tracking_no="ZT5566778899",
                carrier="ZT",
                created_at=now - timedelta(days=20),
                notes="White-glove delivery completed",
            ),
        ]
        db.add_all(orders)

        payments = [
            Payment(
                payment_id="PAY-9001",
                order_id="ORD-1001",
                amount=299.0,
                method="wechat",
                status="succeeded",
                transaction_ref="WX20240901001",
                paid_at=now - timedelta(days=2, hours=1),
                created_at=now - timedelta(days=2, hours=1),
            ),
            Payment(
                payment_id="PAY-9002",
                order_id="ORD-1002",
                amount=459.0,
                method="alipay",
                status="succeeded",
                transaction_ref="ALI20240820002",
                paid_at=now - timedelta(days=10, hours=2),
                created_at=now - timedelta(days=10, hours=2),
            ),
            Payment(
                payment_id="PAY-9003",
                order_id="ORD-1003",
                amount=258.0,
                method="card",
                status="pending",
                transaction_ref=None,
                paid_at=None,
                created_at=now - timedelta(hours=6),
                notes="Card authorization pending",
            ),
            Payment(
                payment_id="PAY-9004",
                order_id="ORD-1004",
                amount=189.0,
                method="wechat",
                status="succeeded",
                transaction_ref="WX20240914004",
                paid_at=now - timedelta(hours=18),
                created_at=now - timedelta(hours=18),
            ),
            Payment(
                payment_id="PAY-9005",
                order_id="ORD-1005",
                amount=1299.0,
                method="alipay",
                status="succeeded",
                transaction_ref="ALI20240801005",
                paid_at=now - timedelta(days=20, hours=3),
                created_at=now - timedelta(days=20, hours=3),
            ),
            Payment(
                payment_id="PAY-9006",
                order_id="ORD-1005",
                amount=50.0,
                method="balance",
                status="failed",
                transaction_ref="BAL-FAIL-006",
                paid_at=None,
                created_at=now - timedelta(days=20, hours=4),
                notes="Insufficient balance; switched to full Alipay payment",
            ),
        ]
        db.add_all(payments)

        tracking = [
            TrackingEvent(
                order_id="ORD-1001",
                tracking_no="SF1234567890",
                status_code="picked_up",
                description="Parcel collected by SF courier",
                location="Shanghai hub",
                event_time=now - timedelta(days=2, hours=2),
            ),
            TrackingEvent(
                order_id="ORD-1001",
                tracking_no="SF1234567890",
                status_code="in_transit",
                description="Departed origin sorting center",
                location="Shanghai",
                event_time=now - timedelta(days=1, hours=18),
            ),
            TrackingEvent(
                order_id="ORD-1001",
                tracking_no="SF1234567890",
                status_code="out_for_delivery",
                description="Out for delivery",
                location="Pudong, Shanghai",
                event_time=now - timedelta(hours=5),
            ),
            TrackingEvent(
                order_id="ORD-1002",
                tracking_no="YT9876543210",
                status_code="delivered",
                description="Delivered and signed",
                location="Hangzhou",
                event_time=now - timedelta(days=8),
            ),
            TrackingEvent(
                order_id="ORD-1005",
                tracking_no="ZT5566778899",
                status_code="delivered",
                description="Furniture delivery completed",
                location="Beijing",
                event_time=now - timedelta(days=18),
            ),
        ]
        db.add_all(tracking)

        coupons = [
            Coupon(
                coupon_code="SAVE20",
                customer_id="CUS-001",
                title="¥20 off electronics",
                discount_label="¥20",
                status="active",
                expires_at=now + timedelta(days=30),
            ),
            Coupon(
                coupon_code="FREESHIP",
                customer_id="CUS-001",
                title="Free shipping voucher",
                discount_label="Free ship",
                status="active",
                expires_at=now + timedelta(days=14),
            ),
            Coupon(
                coupon_code="VIP100",
                customer_id="CUS-004",
                title="VIP ¥100 off",
                discount_label="¥100",
                status="active",
                expires_at=now + timedelta(days=60),
            ),
            Coupon(
                coupon_code="USED10",
                customer_id="CUS-002",
                title="¥10 welcome coupon",
                discount_label="¥10",
                status="used",
                expires_at=now - timedelta(days=5),
            ),
        ]
        db.add_all(coupons)
        db.commit()


def seed_orders(force: bool = False) -> None:
    seed_all(force=force)
