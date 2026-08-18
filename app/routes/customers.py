from datetime import date, datetime
from decimal import Decimal
from fastapi import APIRouter, Depends, Request, Form, HTTPException, status, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import User, Customer, Item, Sale, SaleItem, PaymentReceived, CustomerLedger
from app.auth import get_current_user, log_audit
from app.services import (
    next_code, money, apply_stock_change, add_customer_ledger,
    ensure_walk_in_customer, PAYMENT_METHODS
)

router = APIRouter(prefix="/customers", tags=["customers"])
templates = Jinja2Templates(directory="app/templates")


def parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


@router.get("", response_class=HTMLResponse)
def list_customers(
    request: Request,
    q: str = Query(""),
    status: str = Query(""),
    balance_status: str = Query(""),
    customer_type: str = Query(""),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_walk_in_customer(db)
    db.commit()
    query = db.query(Customer)
    if q:
        like = f"%{q}%"
        query = query.filter((Customer.name.ilike(like)) | (Customer.customer_code.ilike(like)) | (Customer.phone.ilike(like)))
    if status:
        query = query.filter(Customer.status == status)
    if balance_status == "with_balance":
        query = query.filter(Customer.current_balance > 0)
    elif balance_status == "credit":
        query = query.filter(Customer.current_balance < 0)
    elif balance_status == "zero":
        query = query.filter(Customer.current_balance == 0)
    if customer_type == "walk_in":
        query = query.filter(Customer.is_walk_in == True)
    elif customer_type == "regular":
        query = query.filter(Customer.is_walk_in == False)

    customers = query.order_by(Customer.name).all()
    return templates.TemplateResponse("customers/list.html", {
        "request": request, "current_user": current_user, "customers": customers,
        "filters": {
            "q": q,
            "status": status,
            "balance_status": balance_status,
            "customer_type": customer_type,
        },
        "active_tab": "customers", "error": None, "success": None,
    })


@router.get("/new", response_class=HTMLResponse)
def new_customer_form(request: Request, current_user: User = Depends(get_current_user)):
    return templates.TemplateResponse("customers/form.html", {
        "request": request, "current_user": current_user, "customer": None,
        "active_tab": "customers", "error": None, "success": None,
    })


@router.post("/new")
def create_customer(
    request: Request,
    name: str = Form(...),
    phone: str = Form(""),
    address: str = Form(""),
    vehicle_info: str = Form(""),
    opening_balance: str = Form("0"),
    status: str = Form("Active"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    code = next_code(db, Customer, "customer_code", "CUST")
    if code == "CUST-0000":
        code = "CUST-0001"
    bal = money(opening_balance)
    customer = Customer(
        customer_code=code, name=name.strip(), phone=phone.strip() or None,
        address=address.strip() or None, vehicle_info=vehicle_info.strip() or None,
        opening_balance=bal, current_balance=bal, status=status, is_walk_in=False,
    )
    db.add(customer)
    db.flush()
    if bal != 0:
        db.add(CustomerLedger(
            customer_id=customer.id, date=date.today(), description="Opening Balance",
            debit=bal if bal > 0 else Decimal("0"),
            credit=(-bal if bal < 0 else Decimal("0")),
            balance=bal, reference_type="opening",
        ))
    db.commit()
    log_audit(db, current_user.id, "Create Customer", f"Created {code} — {name}")
    return RedirectResponse(url="/customers", status_code=303)


@router.get("/sales", response_class=HTMLResponse)
def list_sales(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    sales = db.query(Sale).options(joinedload(Sale.customer)).order_by(Sale.date.desc(), Sale.id.desc()).all()
    return templates.TemplateResponse("customers/sales.html", {
        "request": request, "current_user": current_user, "sales": sales,
        "active_tab": "customers", "error": None, "success": None,
    })


@router.get("/sales/new", response_class=HTMLResponse)
def new_sale_form(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ensure_walk_in_customer(db)
    db.commit()
    customers = db.query(Customer).filter(Customer.status == "Active").order_by(Customer.name).all()
    items = db.query(Item).filter(Item.status == "Active").order_by(Item.item_code).all()
    return templates.TemplateResponse("customers/sale_form.html", {
        "request": request, "current_user": current_user, "customers": customers, "items": items,
        "payment_methods": PAYMENT_METHODS, "today": date.today().isoformat(),
        "active_tab": "customers", "error": None, "success": None,
    })


@router.post("/sales/new")
async def create_sale(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    form = await request.form()
    customer_id = int(form.get("customer_id"))
    sale_date = parse_date(form.get("date"))
    amount_received = money(form.get("amount_received") or 0)
    payment_method = form.get("payment_method") or None
    note = form.get("note") or None

    item_ids = form.getlist("item_id")
    quantities = form.getlist("quantity")
    prices = form.getlist("unit_price")

    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(404, "Customer not found")

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

    customers = db.query(Customer).filter(Customer.status == "Active").order_by(Customer.name).all()
    items = db.query(Item).filter(Item.status == "Active").order_by(Item.item_code).all()
    ctx = {
        "request": request, "current_user": current_user, "customers": customers, "items": items,
        "payment_methods": PAYMENT_METHODS, "today": date.today().isoformat(),
        "active_tab": "customers", "success": None,
    }
    if not lines:
        ctx["error"] = "Add at least one item line"
        return templates.TemplateResponse("customers/sale_form.html", ctx)

    for iid, q, p, sub in lines:
        item = db.query(Item).filter(Item.id == iid).first()
        if item.current_stock < q:
            ctx["error"] = f"Insufficient stock for {item.item_code} (available {item.current_stock})"
            return templates.TemplateResponse("customers/sale_form.html", ctx)

    invoice_no = next_code(db, Sale, "invoice_no", "SINV")
    
    advance_available = Decimal("0")
    if customer.current_balance < 0:
        advance_available = abs(money(customer.current_balance))
    
    advance_to_adjust = min(total - amount_received, advance_available)
    if advance_to_adjust < 0:
        advance_to_adjust = Decimal("0")
        
    balance = total - amount_received - advance_to_adjust
    
    if advance_to_adjust > 0:
        adjustment_msg = f"Rs. {advance_to_adjust} adjusted from account credit."
        note = f"{note} | {adjustment_msg}" if note else adjustment_msg

    sale = Sale(
        invoice_no=invoice_no, date=sale_date, customer_id=customer.id,
        total_amount=total, amount_received=amount_received, balance=balance,
        payment_method=payment_method, note=note, created_by=current_user.id,
    )
    db.add(sale)
    db.flush()

    for iid, q, p, sub in lines:
        item = db.query(Item).filter(Item.id == iid).first()
        db.add(SaleItem(sale_id=sale.id, item_id=iid, quantity=q, unit_price=p, subtotal=sub))
        apply_stock_change(db, item, -q, "sale", user_id=current_user.id, reference_type="sale", reference_id=sale.id, note=invoice_no)

    if not customer.is_walk_in:
        add_customer_ledger(db, customer, sale_date, f"Sale {invoice_no}", debit=total, reference_type="sale", reference_id=sale.id)
        if amount_received > 0:
            add_customer_ledger(db, customer, sale_date, f"Payment on {invoice_no}", credit=amount_received, reference_type="sale_payment", reference_id=sale.id)

    db.commit()
    log_audit(db, current_user.id, "Create Sale", f"{invoice_no} total {total}")
    return RedirectResponse(url=f"/customers/sales/{sale.id}", status_code=303)


@router.get("/sales/{sale_id}", response_class=HTMLResponse)
def sale_detail(sale_id: int, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    sale = db.query(Sale).options(joinedload(Sale.customer), joinedload(Sale.items).joinedload(SaleItem.item)).filter(Sale.id == sale_id).first()
    if not sale:
        raise HTTPException(404, "Sale not found")
    return templates.TemplateResponse("customers/sale_detail.html", {
        "request": request, "current_user": current_user, "sale": sale,
        "active_tab": "customers", "error": None, "success": None,
    })


@router.get("/payments/new", response_class=HTMLResponse)
def new_payment_form(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    customers = db.query(Customer).filter(Customer.status == "Active", Customer.is_walk_in == False).order_by(Customer.name).all()
    return templates.TemplateResponse("customers/payment_form.html", {
        "request": request, "current_user": current_user, "customers": customers,
        "payment_methods": PAYMENT_METHODS, "today": date.today().isoformat(),
        "active_tab": "customers", "error": None, "success": None,
    })


@router.post("/payments/new")
async def create_payment(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    form = await request.form()
    customer = db.query(Customer).filter(Customer.id == int(form.get("customer_id"))).first()
    if not customer:
        raise HTTPException(404, "Customer not found")
    amt = money(form.get("amount"))
    pay_date = parse_date(form.get("date"))
    receipt_no = next_code(db, PaymentReceived, "receipt_no", "CREC")
    payment = PaymentReceived(
        receipt_no=receipt_no, customer_id=customer.id, date=pay_date,
        amount=amt, payment_method=form.get("payment_method"),
        note=form.get("note") or None, created_by=current_user.id,
    )
    db.add(payment)
    db.flush()
    add_customer_ledger(db, customer, pay_date, f"Payment {receipt_no}", credit=amt, reference_type="payment", reference_id=payment.id)
    db.commit()
    log_audit(db, current_user.id, "Customer Payment", f"{receipt_no} amount {amt}")
    return RedirectResponse(url=f"/customers/{customer.id}", status_code=303)


@router.get("/{customer_id}", response_class=HTMLResponse)
def customer_detail(customer_id: int, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(404, "Customer not found")
    ledger = db.query(CustomerLedger).filter(CustomerLedger.customer_id == customer_id).order_by(CustomerLedger.date, CustomerLedger.id).all()
    return templates.TemplateResponse("customers/detail.html", {
        "request": request, "current_user": current_user, "customer": customer, "ledger": ledger,
        "active_tab": "customers", "error": None, "success": None,
    })


@router.get("/{customer_id}/edit", response_class=HTMLResponse)
def edit_customer_form(customer_id: int, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(404, "Customer not found")
    return templates.TemplateResponse("customers/form.html", {
        "request": request, "current_user": current_user, "customer": customer,
        "active_tab": "customers", "error": None, "success": None,
    })


@router.post("/{customer_id}/edit")
def update_customer(
    customer_id: int,
    request: Request,
    name: str = Form(...),
    phone: str = Form(""),
    address: str = Form(""),
    vehicle_info: str = Form(""),
    status: str = Form("Active"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(404, "Customer not found")
    if not customer.is_walk_in:
        customer.name = name.strip()
    customer.phone = phone.strip() or None
    customer.address = address.strip() or None
    customer.vehicle_info = vehicle_info.strip() or None
    customer.status = status
    db.commit()
    log_audit(db, current_user.id, "Update Customer", f"Updated {customer.customer_code}")
    return RedirectResponse(url=f"/customers/{customer_id}", status_code=303)


@router.post("/{customer_id}/delete")
def delete_customer(
    customer_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(404, "Customer not found")
    if customer.is_walk_in:
        raise HTTPException(400, "Cannot delete Walk-in Customer")
    
    customer_code = customer.customer_code
    db.delete(customer)
    db.commit()
    log_audit(db, current_user.id, "Delete Customer", f"Deleted customer {customer_code}")
    return RedirectResponse(url="/customers", status_code=303)
