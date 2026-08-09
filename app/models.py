from sqlalchemy import (
    Column, Integer, String, DateTime, ForeignKey, Text, Numeric, Date, Boolean
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), default="Admin", nullable=False)
    status = Column(String(20), default="Active", nullable=False)
    failed_attempts = Column(Integer, default=0, nullable=False)
    locked_until = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    audit_logs = relationship("AuditLog", back_populates="user")


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action = Column(String(100), nullable=False)
    details = Column(Text, nullable=True)
    timestamp = Column(DateTime, server_default=func.now())

    user = relationship("User", back_populates="audit_logs")


class Item(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True, index=True)
    item_code = Column(String(20), unique=True, index=True, nullable=False)
    brand = Column(String(100), nullable=False)
    size = Column(String(50), nullable=True)
    pattern = Column(String(100), nullable=True)
    type = Column(String(50), nullable=True)  # Tubeless / Tube-type
    category = Column(String(50), nullable=False)
    purchase_price = Column(Numeric(12, 2), default=0, nullable=False)
    sale_price = Column(Numeric(12, 2), default=0, nullable=False)
    current_stock = Column(Integer, default=0, nullable=False)
    reorder_level = Column(Integer, default=5, nullable=False)
    unit = Column(String(20), default="Piece", nullable=False)
    status = Column(String(20), default="Active", nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    stock_movements = relationship("StockMovement", back_populates="item")


class StockMovement(Base):
    __tablename__ = "stock_movements"

    id = Column(Integer, primary_key=True, index=True)
    item_id = Column(Integer, ForeignKey("items.id"), nullable=False)
    movement_type = Column(String(50), nullable=False)  # purchase, sale, customer_return, supplier_return, adjustment
    quantity_change = Column(Integer, nullable=False)  # + or -
    quantity_after = Column(Integer, nullable=False)
    reference_type = Column(String(50), nullable=True)
    reference_id = Column(Integer, nullable=True)
    note = Column(Text, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    item = relationship("Item", back_populates="stock_movements")
    user = relationship("User")


class Supplier(Base):
    __tablename__ = "suppliers"

    id = Column(Integer, primary_key=True, index=True)
    supplier_code = Column(String(20), unique=True, index=True, nullable=False)
    name = Column(String(150), nullable=False)
    contact_person = Column(String(100), nullable=True)
    phone = Column(String(30), nullable=True)
    address = Column(Text, nullable=True)
    opening_balance = Column(Numeric(12, 2), default=0, nullable=False)
    current_balance = Column(Numeric(12, 2), default=0, nullable=False)
    status = Column(String(20), default="Active", nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    purchases = relationship("Purchase", back_populates="supplier")
    ledger_entries = relationship("SupplierLedger", back_populates="supplier")


class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)
    customer_code = Column(String(20), unique=True, index=True, nullable=False)
    name = Column(String(150), nullable=False)
    phone = Column(String(30), nullable=True)
    address = Column(Text, nullable=True)
    vehicle_info = Column(String(150), nullable=True)
    opening_balance = Column(Numeric(12, 2), default=0, nullable=False)
    current_balance = Column(Numeric(12, 2), default=0, nullable=False)
    status = Column(String(20), default="Active", nullable=False)
    is_walk_in = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    sales = relationship("Sale", back_populates="customer")
    ledger_entries = relationship("CustomerLedger", back_populates="customer")


class Purchase(Base):
    __tablename__ = "purchases"

    id = Column(Integer, primary_key=True, index=True)
    invoice_no = Column(String(30), unique=True, index=True, nullable=False)
    date = Column(Date, nullable=False)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=False)
    total_amount = Column(Numeric(12, 2), default=0, nullable=False)
    amount_paid = Column(Numeric(12, 2), default=0, nullable=False)
    balance = Column(Numeric(12, 2), default=0, nullable=False)
    payment_method = Column(String(30), nullable=True)
    note = Column(Text, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    supplier = relationship("Supplier", back_populates="purchases")
    items = relationship("PurchaseItem", back_populates="purchase", cascade="all, delete-orphan")
    user = relationship("User")


class PurchaseItem(Base):
    __tablename__ = "purchase_items"

    id = Column(Integer, primary_key=True, index=True)
    purchase_id = Column(Integer, ForeignKey("purchases.id", ondelete="CASCADE"), nullable=False)
    item_id = Column(Integer, ForeignKey("items.id"), nullable=False)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Numeric(12, 2), nullable=False)
    subtotal = Column(Numeric(12, 2), nullable=False)

    purchase = relationship("Purchase", back_populates="items")
    item = relationship("Item")


class Sale(Base):
    __tablename__ = "sales"

    id = Column(Integer, primary_key=True, index=True)
    invoice_no = Column(String(30), unique=True, index=True, nullable=False)
    date = Column(Date, nullable=False)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    total_amount = Column(Numeric(12, 2), default=0, nullable=False)
    amount_received = Column(Numeric(12, 2), default=0, nullable=False)
    balance = Column(Numeric(12, 2), default=0, nullable=False)
    payment_method = Column(String(30), nullable=True)
    note = Column(Text, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    customer = relationship("Customer", back_populates="sales")
    items = relationship("SaleItem", back_populates="sale", cascade="all, delete-orphan")
    user = relationship("User")


class SaleItem(Base):
    __tablename__ = "sale_items"

    id = Column(Integer, primary_key=True, index=True)
    sale_id = Column(Integer, ForeignKey("sales.id", ondelete="CASCADE"), nullable=False)
    item_id = Column(Integer, ForeignKey("items.id"), nullable=False)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Numeric(12, 2), nullable=False)
    subtotal = Column(Numeric(12, 2), nullable=False)

    sale = relationship("Sale", back_populates="items")
    item = relationship("Item")


class SupplierReturn(Base):
    __tablename__ = "supplier_returns"

    id = Column(Integer, primary_key=True, index=True)
    return_no = Column(String(30), unique=True, index=True, nullable=False)
    date = Column(Date, nullable=False)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=False)
    purchase_id = Column(Integer, ForeignKey("purchases.id"), nullable=True)
    total_amount = Column(Numeric(12, 2), default=0, nullable=False)
    refund_method = Column(String(50), nullable=True)  # Cash / Adjusted against balance
    note = Column(Text, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    supplier = relationship("Supplier")
    purchase = relationship("Purchase")
    items = relationship("SupplierReturnItem", back_populates="supplier_return", cascade="all, delete-orphan")
    user = relationship("User")


class SupplierReturnItem(Base):
    __tablename__ = "supplier_return_items"

    id = Column(Integer, primary_key=True, index=True)
    supplier_return_id = Column(Integer, ForeignKey("supplier_returns.id", ondelete="CASCADE"), nullable=False)
    item_id = Column(Integer, ForeignKey("items.id"), nullable=False)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Numeric(12, 2), nullable=False)
    subtotal = Column(Numeric(12, 2), nullable=False)
    reason = Column(String(100), nullable=True)

    supplier_return = relationship("SupplierReturn", back_populates="items")
    item = relationship("Item")


class CustomerReturn(Base):
    __tablename__ = "customer_returns"

    id = Column(Integer, primary_key=True, index=True)
    return_no = Column(String(30), unique=True, index=True, nullable=False)
    date = Column(Date, nullable=False)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    sale_id = Column(Integer, ForeignKey("sales.id"), nullable=True)
    total_amount = Column(Numeric(12, 2), default=0, nullable=False)
    refund_method = Column(String(50), nullable=True)
    note = Column(Text, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    customer = relationship("Customer")
    sale = relationship("Sale")
    items = relationship("CustomerReturnItem", back_populates="customer_return", cascade="all, delete-orphan")
    user = relationship("User")


class CustomerReturnItem(Base):
    __tablename__ = "customer_return_items"

    id = Column(Integer, primary_key=True, index=True)
    customer_return_id = Column(Integer, ForeignKey("customer_returns.id", ondelete="CASCADE"), nullable=False)
    item_id = Column(Integer, ForeignKey("items.id"), nullable=False)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Numeric(12, 2), nullable=False)
    subtotal = Column(Numeric(12, 2), nullable=False)
    reason = Column(String(100), nullable=True)

    customer_return = relationship("CustomerReturn", back_populates="items")
    item = relationship("Item")


class SupplierLedger(Base):
    __tablename__ = "supplier_ledger"

    id = Column(Integer, primary_key=True, index=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=False)
    date = Column(Date, nullable=False)
    description = Column(String(255), nullable=False)
    debit = Column(Numeric(12, 2), default=0, nullable=False)
    credit = Column(Numeric(12, 2), default=0, nullable=False)
    balance = Column(Numeric(12, 2), default=0, nullable=False)
    reference_type = Column(String(50), nullable=True)
    reference_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    supplier = relationship("Supplier", back_populates="ledger_entries")


class CustomerLedger(Base):
    __tablename__ = "customer_ledger"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    date = Column(Date, nullable=False)
    description = Column(String(255), nullable=False)
    debit = Column(Numeric(12, 2), default=0, nullable=False)
    credit = Column(Numeric(12, 2), default=0, nullable=False)
    balance = Column(Numeric(12, 2), default=0, nullable=False)
    reference_type = Column(String(50), nullable=True)
    reference_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    customer = relationship("Customer", back_populates="ledger_entries")


class PaymentMade(Base):
    __tablename__ = "payments_made"

    id = Column(Integer, primary_key=True, index=True)
    payment_no = Column(String(30), unique=True, index=True, nullable=False)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=False)
    date = Column(Date, nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    payment_method = Column(String(30), nullable=False)
    note = Column(Text, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    supplier = relationship("Supplier")
    user = relationship("User")


class PaymentReceived(Base):
    __tablename__ = "payments_received"

    id = Column(Integer, primary_key=True, index=True)
    receipt_no = Column(String(30), unique=True, index=True, nullable=False)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    date = Column(Date, nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    payment_method = Column(String(30), nullable=False)
    note = Column(Text, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    customer = relationship("Customer")
    user = relationship("User")
