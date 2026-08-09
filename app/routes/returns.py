from datetime import date, datetime
from decimal import Decimal
from fastapi import APIRouter, Depends, Request, HTTPException, status, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import (
    User, Supplier, Customer, Item, Purchase, Sale,
    SupplierReturn, SupplierReturnItem, CustomerReturn, CustomerReturnItem
)
from app.auth import get_current_user, log_audit
from app.services import (
    next_code, money, apply_stock_change, add_supplier_ledger, add_customer_ledger,
    REFUND_METHODS, RETURN_REASONS
)

router = APIRouter(prefix="/returns", tags=["returns"])
templates = Jinja2Templates(directory="app/templates")


def parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


@router.get("", response_class=HTMLResponse)
def returns_dashboard(
    request: Request,
    day: str = Query(""),
    q: str = Query(""),
    brand: str = Query(""),
    reason: str = Query(""),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    selected = parse_date(day) if day else date.today()
    supplier_returns = db.query(SupplierReturn).options(
        joinedload(SupplierReturn.supplier),
        joinedload(SupplierReturn.items).joinedload(SupplierReturnItem.item)
    ).filter(SupplierReturn.date == selected).order_by(SupplierReturn.id.desc()).all()
    customer_returns = db.query(CustomerReturn).options(
        joinedload(CustomerReturn.customer),
        joinedload(CustomerReturn.items).joinedload(CustomerReturnItem.item)
    ).filter(CustomerReturn.date == selected).order_by(CustomerReturn.id.desc()).all()

    def matches(ret):
        if not q and not brand and not reason:
            return True
        for line in ret.items:
            item = line.item
            blob = f"{item.item_code} {item.brand}".lower()
            if q and q.lower() not in blob:
                continue
            if brand and brand.lower() not in (item.brand or "").lower():
                continue
            if reason and reason.lower() not in (line.reason or "").lower():
                continue
            return True
        return False

    if q or brand or reason:
        supplier_returns = [r for r in supplier_returns if matches(r)]
        customer_returns = [r for r in customer_returns if matches(r)]

    supplier_total = sum((r.total_amount or 0) for r in supplier_returns)
    customer_total = sum((r.total_amount or 0) for r in customer_returns)

    return templates.TemplateResponse("returns/dashboard.html", {
        "request": request, "current_user": current_user,
        "selected": selected.isoformat(),
        "supplier_returns": supplier_returns, "customer_returns": customer_returns,
        "supplier_total": supplier_total, "customer_total": customer_total,
        "q": q, "brand": brand, "reason": reason, "reasons": RETURN_REASONS,
        "active_tab": "returns", "error": None, "success": None,
    })


@router.get("/supplier/new", response_class=HTMLResponse)
def supplier_return_form(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    suppliers = db.query(Supplier).filter(Supplier.status == "Active").order_by(Supplier.name).all()
    purchases = db.query(Purchase).order_by(Purchase.date.desc()).limit(100).all()
    items = db.query(Item).filter(Item.status == "Active").order_by(Item.item_code).all()
    return templates.TemplateResponse("returns/supplier_form.html", {
        "request": request, "current_user": current_user, "suppliers": suppliers,
        "purchases": purchases, "items": items, "refund_methods": REFUND_METHODS,
        "reasons": RETURN_REASONS, "today": date.today().isoformat(),
        "active_tab": "returns", "error": None, "success": None,
    })


@router.post("/supplier/new")
async def create_supplier_return(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    form = await request.form()
    supplier = db.query(Supplier).filter(Supplier.id == int(form.get("supplier_id"))).first()
    if not supplier:
        raise HTTPException(404, "Supplier not found")
    ret_date = parse_date(form.get("date"))
    purchase_id = form.get("purchase_id") or None
    if purchase_id:
        purchase_id = int(purchase_id)
    refund_method = form.get("refund_method")
    note = form.get("note") or None

    item_ids = form.getlist("item_id")
    quantities = form.getlist("quantity")
    prices = form.getlist("unit_price")
    reasons = form.getlist("reason")

    lines = []
    total = Decimal("0")
    for iid, qty, price, reason in zip(item_ids, quantities, prices, reasons):
        if not iid or not qty:
            continue
        q = int(qty)
        p = money(price)
        if q <= 0:
            continue
        sub = money(q * p)
        lines.append((int(iid), q, p, sub, reason or None))
        total += sub

    if not lines:
        raise HTTPException(400, "Add at least one item")

    for iid, q, p, sub, reason in lines:
        item = db.query(Item).filter(Item.id == iid).first()
        if item.current_stock < q:
            raise HTTPException(400, f"Insufficient stock for {item.item_code}")

    return_no = next_code(db, SupplierReturn, "return_no", "SRET")
    ret = SupplierReturn(
        return_no=return_no, date=ret_date, supplier_id=supplier.id,
        purchase_id=purchase_id, total_amount=total, refund_method=refund_method,
        note=note, created_by=current_user.id,
    )
    db.add(ret)
    db.flush()
    for iid, q, p, sub, reason in lines:
        item = db.query(Item).filter(Item.id == iid).first()
        db.add(SupplierReturnItem(supplier_return_id=ret.id, item_id=iid, quantity=q, unit_price=p, subtotal=sub, reason=reason))
        apply_stock_change(db, item, -q, "supplier_return", user_id=current_user.id, reference_type="supplier_return", reference_id=ret.id, note=return_no)

    add_supplier_ledger(db, supplier, ret_date, f"Return {return_no}", credit=total, reference_type="supplier_return", reference_id=ret.id)
    db.commit()
    log_audit(db, current_user.id, "Supplier Return", f"{return_no} total {total}")
    return RedirectResponse(url=f"/returns?day={ret_date.isoformat()}", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/customer/new", response_class=HTMLResponse)
def customer_return_form(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    customers = db.query(Customer).filter(Customer.status == "Active").order_by(Customer.name).all()
    sales = db.query(Sale).order_by(Sale.date.desc()).limit(100).all()
    items = db.query(Item).filter(Item.status == "Active").order_by(Item.item_code).all()
    return templates.TemplateResponse("returns/customer_form.html", {
        "request": request, "current_user": current_user, "customers": customers,
        "sales": sales, "items": items, "refund_methods": REFUND_METHODS,
        "reasons": RETURN_REASONS, "today": date.today().isoformat(),
        "active_tab": "returns", "error": None, "success": None,
    })


@router.post("/customer/new")
async def create_customer_return(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    form = await request.form()
    customer = db.query(Customer).filter(Customer.id == int(form.get("customer_id"))).first()
    if not customer:
        raise HTTPException(404, "Customer not found")
    ret_date = parse_date(form.get("date"))
    sale_id = form.get("sale_id") or None
    if sale_id:
        sale_id = int(sale_id)
    refund_method = form.get("refund_method")
    note = form.get("note") or None

    item_ids = form.getlist("item_id")
    quantities = form.getlist("quantity")
    prices = form.getlist("unit_price")
    reasons = form.getlist("reason")

    lines = []
    total = Decimal("0")
    for iid, qty, price, reason in zip(item_ids, quantities, prices, reasons):
        if not iid or not qty:
            continue
        q = int(qty)
        p = money(price)
        if q <= 0:
            continue
        sub = money(q * p)
        lines.append((int(iid), q, p, sub, reason or None))
        total += sub

    if not lines:
        raise HTTPException(400, "Add at least one item")

    return_no = next_code(db, CustomerReturn, "return_no", "CRET")
    ret = CustomerReturn(
        return_no=return_no, date=ret_date, customer_id=customer.id,
        sale_id=sale_id, total_amount=total, refund_method=refund_method,
        note=note, created_by=current_user.id,
    )
    db.add(ret)
    db.flush()
    for iid, q, p, sub, reason in lines:
        item = db.query(Item).filter(Item.id == iid).first()
        db.add(CustomerReturnItem(customer_return_id=ret.id, item_id=iid, quantity=q, unit_price=p, subtotal=sub, reason=reason))
        apply_stock_change(db, item, q, "customer_return", user_id=current_user.id, reference_type="customer_return", reference_id=ret.id, note=return_no)

    if not customer.is_walk_in:
        add_customer_ledger(db, customer, ret_date, f"Return {return_no}", credit=total, reference_type="customer_return", reference_id=ret.id)
    db.commit()
    log_audit(db, current_user.id, "Customer Return", f"{return_no} total {total}")
    return RedirectResponse(url=f"/returns?day={ret_date.isoformat()}", status_code=status.HTTP_303_SEE_OTHER)
