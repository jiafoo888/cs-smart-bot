"""Business tables for enterprise CS demo."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    customer_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(64))
    email: Mapped[str] = mapped_column(String(128))
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    loyalty_points: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    orders: Mapped[list[Order]] = relationship(back_populates="customer")
    coupons: Mapped[list[Coupon]] = relationship(back_populates="customer")


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.customer_id"), index=True)
    product: Mapped[str] = mapped_column(String(128))
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    amount: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(8), default="CNY")
    status: Mapped[str] = mapped_column(String(32), index=True)
    shipping_address: Mapped[str | None] = mapped_column(String(256), nullable=True)
    tracking_no: Mapped[str | None] = mapped_column(String(64), nullable=True)
    carrier: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    customer: Mapped[Customer] = relationship(back_populates="orders")
    payments: Mapped[list[Payment]] = relationship(back_populates="order")
    tickets: Mapped[list[Ticket]] = relationship(back_populates="order")
    tracking_events: Mapped[list[TrackingEvent]] = relationship(back_populates="order")
    invoices: Mapped[list[Invoice]] = relationship(back_populates="order")
    exchanges: Mapped[list[ExchangeRequest]] = relationship(back_populates="order")


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    payment_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.order_id"), index=True)
    amount: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(8), default="CNY")
    method: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), index=True)
    transaction_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    order: Mapped[Order] = relationship(back_populates="payments")


class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ticket_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    order_id: Mapped[str | None] = mapped_column(
        ForeignKey("orders.order_id"), nullable=True, index=True
    )
    category: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), default="open")
    summary: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    order: Mapped[Order | None] = relationship(back_populates="tickets")


class ChatLog(Base):
    __tablename__ = "chat_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    role: Mapped[str] = mapped_column(String(16))  # user | assistant | system | human
    agent: Mapped[str | None] = mapped_column(String(32), nullable=True)
    content: Mapped[str] = mapped_column(Text)
    meta_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class TrackingEvent(Base):
    """Mock carrier tracking timeline."""

    __tablename__ = "tracking_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.order_id"), index=True)
    tracking_no: Mapped[str] = mapped_column(String(64), index=True)
    status_code: Mapped[str] = mapped_column(String(32))
    description: Mapped[str] = mapped_column(String(256))
    location: Mapped[str | None] = mapped_column(String(128), nullable=True)
    event_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    order: Mapped[Order] = relationship(back_populates="tracking_events")


class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    invoice_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.order_id"), index=True)
    title: Mapped[str] = mapped_column(String(128), default="Personal")
    tax_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    amount: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(32), default="issued")  # pending | issued | void
    pdf_url: Mapped[str | None] = mapped_column(String(256), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    order: Mapped[Order] = relationship(back_populates="invoices")


class ExchangeRequest(Base):
    __tablename__ = "exchange_requests"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    exchange_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.order_id"), index=True)
    reason: Mapped[str] = mapped_column(String(256))
    status: Mapped[str] = mapped_column(String(32), default="submitted")
    # submitted | approved | rejected | completed
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    order: Mapped[Order] = relationship(back_populates="exchanges")


class Coupon(Base):
    __tablename__ = "coupons"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    coupon_code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.customer_id"), index=True)
    title: Mapped[str] = mapped_column(String(128))
    discount_label: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default="active")  # active | used | expired
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    customer: Mapped[Customer] = relationship(back_populates="coupons")


class SatisfactionRating(Base):
    __tablename__ = "satisfaction_ratings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    score: Mapped[int] = mapped_column(Integer)  # 1-5
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SessionHandoff(Base):
    """Human takeover: when bot_paused, graph stops and waits for agent reply."""

    __tablename__ = "session_handoffs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    ticket_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    bot_paused: Mapped[bool] = mapped_column(Boolean, default=True)
    paused_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    resumed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_human_reply: Mapped[str | None] = mapped_column(Text, nullable=True)
