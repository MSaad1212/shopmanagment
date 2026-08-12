from datetime import date, datetime
from decimal import Decimal
from fastapi import APIRouter, Depends, Request, Form, HTTPException, status, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import User, Supplier, Item, Purchase, PurchaseItem, PaymentMade, SupplierLedger
from app.auth import get_current_user, log_audit
from app.services import (
    next_code, money, apply_stock_change, add_supplier_ledger, PAYMENT_METHODS
)

router = APIRouter(prefix="/suppliers", tags=["suppliers"])
templates = Jinja2Templates(directory="app/templates")


def parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


@router.get("", response_class=HTMLResponse)
def list_suppliers(
    request: Request,
    q: str = Query(""),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Supplier)
    if q:
        like = f"%{q}%"
        query = query.filter((Supplier.name.ilike(like)) | (Supplier.supplier_code.ilike(like)) | (Supplier.phone.ilike(like)))
    suppliers = query.order_by(Supplier.name).all()
    return templates.TemplateResponse("suppliers/list.html", {
        "request": request, "current_user": current_user, "suppliers": suppliers,
        "q": q, "active_tab": "suppliers", "error": None, "success": None,
    })


@router.get("/new", response_class=HTMLResponse)
def new_supplier_form(request: Request, current_user: User = Depends(get_current_user)):
    return templates.TemplateResponse("suppliers/form.html", {
        "request": request, "current_user": current_user, "supplier": None,
        "active_tab": "suppliers", "error": None, "success": None,
    })


@router.post("/new")
def create_supplier(
    request: Request,
    name: str = Form(...),
    contact_person: str = Form(""),
    phone: str = Form(""),
    address: str = Form(""),
    opening_balance: str = Form("0"),
    status: str = Form("Active"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    code = next_code(db, Supplier, "supplier_code", "SUP")
    bal = money(opening_balance)
    supplier = Supplier(
        supplier_code=code, name=name.strip(), contact_person=contact_person.strip() or None,
        phone=phone.strip() or None, address=address.strip() or None,
        opening_balance=bal, current_balance=bal, status=status,
    )
    db.add(supplier)
    db.flush()
    if bal != 0:
        db.add(SupplierLedger(
            supplier_id=supplier.id, date=date.today(), description="Opening Balance",
            debit=bal if bal > 0 else Decimal("0"),
            credit=(-bal if bal < 0 else Decimal("0")),
            balance=bal, reference_type="opening",
        ))
    db.commit()
    log_audit(db, current_user.id, "Create Supplier", f"Created {code} — {name}")
    return RedirectResponse(url="/suppliers", status_code=303)


@router.get("/purchases", response_class=HTMLResponse)
def list_purchases(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    purchases = db.query(Purchase).options(joinedload(Purchase.supplier)).order_by(Purchase.date.desc(), Purchase.id.desc()).all()
    return templates.TemplateResponse("suppliers/purchases.html", {
        "request": request, "current_user": current_user, "purchases": purchases,
        "active_tab": "suppliers", "error": None, "success": None,
    })


@router.get("/purchases/new", response_class=HTMLResponse)
def new_purchase_form(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    suppliers = db.query(Supplier).filter(Supplier.status == "Active").order_by(Supplier.name).all()
    items = db.query(Item).filter(Item.status == "Active").order_by(Item.item_code).all()
    return templates.TemplateResponse("suppliers/purchase_form.html", {
        "request": request, "current_user": current_user, "suppliers": suppliers, "items": items,
        "payment_methods": PAYMENT_METHODS, "today": date.today().isoformat(),
        "active_tab": "suppliers", "error": None, "success": None,
    })


@router.post("/purchases/new")
async def create_purchase(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    form = await request.form()
    supplier_id = int(form.get("supplier_id"))
    purchase_date = parse_date(form.get("date"))
    amount_paid = money(form.get("amount_paid") or 0)
    payment_method = form.get("payment_method") or None
    note = form.get("note") or None

    item_ids = form.getlist("item_id")
    quantities = form.getlist("quantity")
    prices = form.getlist("unit_price")

    supplier = db.query(Supplier).filter(Supplier.id == supplier_id).first()
    if not supplier:
        raise HTTPException(404, "Supplier not found")

    lines = []
    total = Decimal("0")
    for iid, qty, price in zip(item_ids, quantities, prices):
        if not iid or not qty:
            continue
        q = int(qty)
        p = money(price)
        if q <= 0:
            continue
        lines.append((int(iid), q, p, money(q * p)))
        total += money(q * p)

    if not lines:
        suppliers = db.query(Supplier).filter(Supplier.status == "Active").order_by(Supplier.name).all()
        items = db.query(Item).filter(Item.status == "Active").order_by(Item.item_code).all()
        return templates.TemplateResponse("suppliers/purchase_form.html", {
            "request": request, "current_user": current_user, "suppliers": suppliers, "items": items,
            "payment_methods": PAYMENT_METHODS, "today": date.today().isoformat(),
            "active_tab": "suppliers", "error": "Add at least one item line", "success": None,
        })

    invoice_no = next_code(db, Purchase, "invoice_no", "PINV")
    balance = total - amount_paid
    purchase = Purchase(
        invoice_no=invoice_no, date=purchase_date, supplier_id=supplier.id,
        total_amount=total, amount_paid=amount_paid, balance=balance,
        payment_method=payment_method, note=note, created_by=current_user.id,
    )
    db.add(purchase)
    db.flush()

    for iid, q, p, sub in lines:
        item = db.query(Item).filter(Item.id == iid).first()
        db.add(PurchaseItem(purchase_id=purchase.id, item_id=iid, quantity=q, unit_price=p, subtotal=sub))
        apply_stock_change(db, item, q, "purchase", user_id=current_user.id, reference_type="purchase", reference_id=purchase.id, note=invoice_no)
        item.purchase_price = p

    add_supplier_ledger(db, supplier, purchase_date, f"Purchase {invoice_no}", debit=total, reference_type="purchase", reference_id=purchase.id)
    if amount_paid > 0:
        add_supplier_ledger(db, supplier, purchase_date, f"Payment on {invoice_no}", credit=amount_paid, reference_type="purchase_payment", reference_id=purchase.id)

    db.commit()
    log_audit(db, current_user.id, "Create Purchase", f"{invoice_no} total {total}")
    return RedirectResponse(url=f"/suppliers/purchases/{purchase.id}", status_code=303)


@router.get("/purchases/{purchase_id}", response_class=HTMLResponse)
def purchase_detail(purchase_id: int, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    purchase = db.query(Purchase).options(joinedload(Purchase.supplier), joinedload(Purchase.items).joinedload(PurchaseItem.item)).filter(Purchase.id == purchase_id).first()
    if not purchase:
        raise HTTPException(404, "Purchase not found")
    return templates.TemplateResponse("suppliers/purchase_detail.html", {
        "request": request, "current_user": current_user, "purchase": purchase,
        "active_tab": "suppliers", "error": None, "success": None,
    })


@router.get("/payments/new", response_class=HTMLResponse)
def new_payment_form(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    suppliers = db.query(Supplier).filter(Supplier.status == "Active").order_by(Supplier.name).all()
    return templates.TemplateResponse("suppliers/payment_form.html", {
        "request": request, "current_user": current_user, "suppliers": suppliers,
        "payment_methods": PAYMENT_METHODS, "today": date.today().isoformat(),
        "active_tab": "suppliers", "error": None, "success": None,
    })


@router.post("/payments/new")
async def create_payment(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    form = await request.form()
    supplier = db.query(Supplier).filter(Supplier.id == int(form.get("supplier_id"))).first()
    if not supplier:
        raise HTTPException(404, "Supplier not found")
    amt = money(form.get("amount"))
    pay_date = parse_date(form.get("date"))
    payment_method = form.get("payment_method")
    note = form.get("note") or None
    payment_no = next_code(db, PaymentMade, "payment_no", "SPAY")
    payment = PaymentMade(
        payment_no=payment_no, supplier_id=supplier.id, date=pay_date,
        amount=amt, payment_method=payment_method, note=note, created_by=current_user.id,
    )
    db.add(payment)
    db.flush()
    add_supplier_ledger(db, supplier, pay_date, f"Payment {payment_no}", credit=amt, reference_type="payment", reference_id=payment.id)
    db.commit()
    log_audit(db, current_user.id, "Supplier Payment", f"{payment_no} amount {amt}")
    return RedirectResponse(url=f"/suppliers/{supplier.id}", status_code=303)


@router.get("/{supplier_id}", response_class=HTMLResponse)
def supplier_detail(supplier_id: int, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    supplier = db.query(Supplier).filter(Supplier.id == supplier_id).first()
    if not supplier:
        raise HTTPException(404, "Supplier not found")
    ledger = db.query(SupplierLedger).filter(SupplierLedger.supplier_id == supplier_id).order_by(SupplierLedger.date, SupplierLedger.id).all()
    return templates.TemplateResponse("suppliers/detail.html", {
        "request": request, "current_user": current_user, "supplier": supplier, "ledger": ledger,
        "active_tab": "suppliers", "error": None, "success": None,
    })


@router.get("/{supplier_id}/edit", response_class=HTMLResponse)
def edit_supplier_form(supplier_id: int, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    supplier = db.query(Supplier).filter(Supplier.id == supplier_id).first()
    if not supplier:
        raise HTTPException(404, "Supplier not found")
    return templates.TemplateResponse("suppliers/form.html", {
        "request": request, "current_user": current_user, "supplier": supplier,
        "active_tab": "suppliers", "error": None, "success": None,
    })


@router.post("/{supplier_id}/edit")
def update_supplier(
    supplier_id: int,
    request: Request,
    name: str = Form(...),
    contact_person: str = Form(""),
    phone: str = Form(""),
    address: str = Form(""),
    status: str = Form("Active"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    supplier = db.query(Supplier).filter(Supplier.id == supplier_id).first()
    if not supplier:
        raise HTTPException(404, "Supplier not found")
    supplier.name = name.strip()
    supplier.contact_person = contact_person.strip() or None
    supplier.phone = phone.strip() or None
    supplier.address = address.strip() or None
    supplier.status = status
    db.commit()
    log_audit(db, current_user.id, "Update Supplier", f"Updated {supplier.supplier_code}")
    return RedirectResponse(url=f"/suppliers/{supplier_id}", status_code=303)


@router.post("/{supplier_id}/delete")
def delete_supplier(
    supplier_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    supplier = db.query(Supplier).filter(Supplier.id == supplier_id).first()
    if not supplier:
        raise HTTPException(404, "Supplier not found")
    
    supplier_code = supplier.supplier_code
    db.delete(supplier)
    db.commit()
    log_audit(db, current_user.id, "Delete Supplier", f"Deleted supplier {supplier_code}")
    return RedirectResponse(url="/suppliers", status_code=303)
