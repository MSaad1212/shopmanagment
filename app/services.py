"""Shared business helpers: codes, stock movements, ledgers."""
from decimal import Decimal
from datetime import date
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models import (
    Item, StockMovement, Supplier, Customer,
    SupplierLedger, CustomerLedger
)


def money(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal("0.01"))


def next_code(db: Session, model, field_name: str, prefix: str, width: int = 4) -> str:
    col = getattr(model, field_name)
    last = db.query(model).order_by(model.id.desc()).first()
    if not last:
        return f"{prefix}-{str(1).zfill(width)}"
    raw = getattr(last, field_name) or ""
    try:
        num = int(raw.split("-")[-1]) + 1
    except (ValueError, IndexError):
        num = (last.id or 0) + 1
    return f"{prefix}-{str(num).zfill(width)}"


def apply_stock_change(
    db: Session,
    item: Item,
    quantity_change: int,
    movement_type: str,
    user_id: int = None,
    reference_type: str = None,
    reference_id: int = None,
    note: str = None,
) -> StockMovement:
    available = item.current_stock or 0
    new_qty = available + quantity_change
    if new_qty < 0:
        raise ValueError(f"Insufficient stock for {item.item_code}. Available: {available}")
    item.current_stock = new_qty
    movement = StockMovement(
        item_id=item.id,
        movement_type=movement_type,
        quantity_change=quantity_change,
        quantity_after=item.current_stock,
        reference_type=reference_type,
        reference_id=reference_id,
        note=note,
        created_by=user_id,
    )
    db.add(movement)
    return movement


def add_supplier_ledger(
    db: Session,
    supplier: Supplier,
    entry_date: date,
    description: str,
    debit: Decimal = Decimal("0"),
    credit: Decimal = Decimal("0"),
    reference_type: str = None,
    reference_id: int = None,
) -> SupplierLedger:
    debit = money(debit)
    credit = money(credit)
    new_balance = money(supplier.current_balance) + debit - credit
    supplier.current_balance = new_balance
    entry = SupplierLedger(
        supplier_id=supplier.id,
        date=entry_date,
        description=description,
        debit=debit,
        credit=credit,
        balance=new_balance,
        reference_type=reference_type,
        reference_id=reference_id,
    )
    db.add(entry)
    return entry


def add_customer_ledger(
    db: Session,
    customer: Customer,
    entry_date: date,
    description: str,
    debit: Decimal = Decimal("0"),
    credit: Decimal = Decimal("0"),
    reference_type: str = None,
    reference_id: int = None,
) -> CustomerLedger:
    debit = money(debit)
    credit = money(credit)
    new_balance = money(customer.current_balance) + debit - credit
    customer.current_balance = new_balance
    entry = CustomerLedger(
        customer_id=customer.id,
        date=entry_date,
        description=description,
        debit=debit,
        credit=credit,
        balance=new_balance,
        reference_type=reference_type,
        reference_id=reference_id,
    )
    db.add(entry)
    return entry


def ensure_walk_in_customer(db: Session) -> Customer:
    walk_in = db.query(Customer).filter(Customer.is_walk_in == True).first()
    if walk_in:
        return walk_in
    walk_in = Customer(
        customer_code="CUST-0000",
        name="Walk-in / Cash Customer",
        status="Active",
        is_walk_in=True,
        opening_balance=0,
        current_balance=0,
    )
    db.add(walk_in)
    db.flush()
    return walk_in


CATEGORIES = [
    "Gas Kit", "Cylinder", "Valve", "Pipes", "Fittings", "Accessory", "Other"
]
ITEM_TYPES = ["New", "Used", "Refurbished"]
PAYMENT_METHODS = ["Cash", "Bank Transfer", "Cheque"]
REFUND_METHODS = ["Cash", "Adjusted against balance"]
RETURN_REASONS = ["Defective", "Wrong size", "Changed mind", "Other"]
