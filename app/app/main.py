from __future__ import annotations

import os
import uuid
from datetime import datetime
from typing import Literal, Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import (
    Column,
    DateTime,
    Index,
    Integer,
    String,
    create_engine,
    select,
)
from sqlalchemy.orm import Session, declarative_base, sessionmaker

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@localhost:5432/ledgerha",
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


class OrderRow(Base):
    __tablename__ = "orders"

    id = Column(String(36), primary_key=True)
    customer_id = Column(String(64), nullable=False)
    sku = Column(String(64), nullable=False)
    amount_cents = Column(Integer, nullable=False)
    status = Column(String(24), nullable=False, default="OPEN")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_orders_status_updated", "status", "updated_at"),
        Index("ix_orders_customer_created", "customer_id", "created_at"),
    )


class OrderCreate(BaseModel):
    customer_id: str = Field(min_length=1, max_length=64)
    sku: str = Field(min_length=1, max_length=64)
    amount_cents: int = Field(gt=0)


class OrderOut(BaseModel):
    id: str
    customer_id: str
    sku: str
    amount_cents: int
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


StatusFilter = Literal["OPEN", "PAID", "CANCELLED", "SHIPPED"]

app = FastAPI(title="LedgerHA", version="1.0.0")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/orders", response_model=OrderOut, status_code=201)
def create_order(body: OrderCreate):
    now = datetime.utcnow()
    row = OrderRow(
        id=str(uuid.uuid4()),
        customer_id=body.customer_id,
        sku=body.sku,
        amount_cents=body.amount_cents,
        status="OPEN",
        created_at=now,
        updated_at=now,
    )
    with SessionLocal() as session:
        session.add(row)
        session.commit()
        session.refresh(row)
        return row


@app.get("/orders/{order_id}", response_model=OrderOut)
def get_order(order_id: str):
    with SessionLocal() as session:
        row = session.get(OrderRow, order_id)
        if not row:
            raise HTTPException(status_code=404, detail="order not found")
        return row


@app.get("/orders", response_model=list[OrderOut])
def list_orders(
    status: Optional[StatusFilter] = Query(default=None),
    customer_id: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
):
    with SessionLocal() as session:
        stmt = select(OrderRow)
        if status:
            stmt = stmt.where(OrderRow.status == status).order_by(
                OrderRow.updated_at.desc()
            )
        elif customer_id:
            stmt = stmt.where(OrderRow.customer_id == customer_id).order_by(
                OrderRow.created_at.desc()
            )
        else:
            stmt = stmt.order_by(OrderRow.created_at.desc())
        stmt = stmt.limit(limit)
        return list(session.scalars(stmt))


@app.post("/orders/{order_id}/status", response_model=OrderOut)
def update_status(order_id: str, status: StatusFilter = Query(...)):
    with SessionLocal() as session:
        row = session.get(OrderRow, order_id)
        if not row:
            raise HTTPException(status_code=404, detail="order not found")
        row.status = status
        row.updated_at = datetime.utcnow()
        session.commit()
        session.refresh(row)
        return row
