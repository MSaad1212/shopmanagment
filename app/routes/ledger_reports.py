from datetime import date, datetime, timedelta
from decimal import Decimal
from fastapi import APIRouter, Depends, Request, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models import (
    User, Supplier, Customer, Item, Sale, SaleItem, Purchase, PurchaseItem,
    SupplierReturn, CustomerReturn, PaymentMade, PaymentReceived
)
from app.auth import get_current_user, require_admin
from app.services import money

router = APIRouter(tags=["ledger-reports"])
templates = Jinja2Templates(directory="app/templates")


def parse_date(value: str, default: date = None) -> date:
    if not value:
        return default or date.today()
    return datetime.strptime(value, "%Y-%m-%d").date()


@router.get("/ledger", response_class=HTMLResponse)
def general_ledger(
    request: Request,
    period_from: str = Query(""),
    period_to: str = Query(""),
    day: str = Query(""),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    today = date.today()
    cash_day = parse_date(day, today)
    start = parse_date(period_from, today.replace(day=1))
    end = parse_date(period_to, today)

    receivables = db.query(func.coalesce(func.sum(Customer.current_balance), 0)).filter(Customer.is_walk_in == False).scalar() or 0
    payables = db.query(func.coalesce(func.sum(Supplier.current_balance), 0)).scalar() or 0

    cash_in = Decimal("0")
    cash_out = Decimal("0")

    sales_cash = db.query(Sale).filter(Sale.date >= start, Sale.date <= end, Sale.payment_method == "Cash").all()
    for s in sales_cash:
        cash_in += money(s.amount_received)
    recv = db.query(PaymentReceived).filter(PaymentReceived.date >= start, PaymentReceived.date <= end, PaymentReceived.payment_method == "Cash").all()
    for p in recv:
        cash_in += money(p.amount)

    purchases_cash = db.query(Purchase).filter(Purchase.date >= start, Purchase.date <= end, Purchase.payment_method == "Cash").all()
    for p in purchases_cash:
        cash_out += money(p.amount_paid)
    paid = db.query(PaymentMade).filter(PaymentMade.date >= start, PaymentMade.date <= end, PaymentMade.payment_method == "Cash").all()
    for p in paid:
        cash_out += money(p.amount)

    # Daily cash book
    cash_book = []
    for s in db.query(Sale).filter(Sale.date == cash_day, Sale.payment_method == "Cash").all():
        if s.amount_received and money(s.amount_received) > 0:
            cash_book.append({"date": s.date, "desc": f"Sale {s.invoice_no}", "in": money(s.amount_received), "out": Decimal("0")})
    for p in db.query(PaymentReceived).filter(PaymentReceived.date == cash_day, PaymentReceived.payment_method == "Cash").all():
        cash_book.append({"date": p.date, "desc": f"Receipt {p.receipt_no}", "in": money(p.amount), "out": Decimal("0")})
    for p in db.query(Purchase).filter(Purchase.date == cash_day, Purchase.payment_method == "Cash").all():
        if p.amount_paid and money(p.amount_paid) > 0:
            cash_book.append({"date": p.date, "desc": f"Purchase {p.invoice_no}", "in": Decimal("0"), "out": money(p.amount_paid)})
    for p in db.query(PaymentMade).filter(PaymentMade.date == cash_day, PaymentMade.payment_method == "Cash").all():
        cash_book.append({"date": p.date, "desc": f"Payment {p.payment_no}", "in": Decimal("0"), "out": money(p.amount)})

    day_in = sum((r["in"] for r in cash_book), Decimal("0"))
    day_out = sum((r["out"] for r in cash_book), Decimal("0"))

    return templates.TemplateResponse("ledger/overview.html", {
        "request": request, "current_user": current_user,
        "receivables": receivables, "payables": payables,
        "cash_in": cash_in, "cash_out": cash_out, "cash_net": cash_in - cash_out,
        "start": start.isoformat(), "end": end.isoformat(),
        "cash_day": cash_day.isoformat(), "cash_book": cash_book,
        "day_in": day_in, "day_out": day_out,
        "active_tab": "ledger", "error": None, "success": None,
    })


@router.get("/reports", response_class=HTMLResponse)
def reports_home(request: Request, current_user: User = Depends(get_current_user)):
    return templates.TemplateResponse("reports/index.html", {
        "request": request, "current_user": current_user, "active_tab": "reports",
        "error": None, "success": None, "today": date.today().isoformat(),
        "month_start": date.today().replace(day=1).isoformat(),
    })


@router.get("/reports/sales", response_class=HTMLResponse)
def sales_report(
    request: Request,
    date_from: str = Query(""),
    date_to: str = Query(""),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    start = parse_date(date_from, date.today().replace(day=1))
    end = parse_date(date_to, date.today())
    sales = db.query(Sale).filter(Sale.date >= start, Sale.date <= end).order_by(Sale.date.desc()).all()
    total = sum((money(s.total_amount) for s in sales), Decimal("0"))
    return templates.TemplateResponse("reports/sales.html", {
        "request": request, "current_user": current_user, "sales": sales, "total": total,
        "date_from": start.isoformat(), "date_to": end.isoformat(),
        "active_tab": "reports", "error": None, "success": None,
    })


@router.get("/reports/purchases", response_class=HTMLResponse)
def purchases_report(
    request: Request,
    date_from: str = Query(""),
    date_to: str = Query(""),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    start = parse_date(date_from, date.today().replace(day=1))
    end = parse_date(date_to, date.today())
    purchases = db.query(Purchase).filter(Purchase.date >= start, Purchase.date <= end).order_by(Purchase.date.desc()).all()
    total = sum((money(p.total_amount) for p in purchases), Decimal("0"))
    return templates.TemplateResponse("reports/purchases.html", {
        "request": request, "current_user": current_user, "purchases": purchases, "total": total,
        "date_from": start.isoformat(), "date_to": end.isoformat(),
        "active_tab": "reports", "error": None, "success": None,
    })


@router.get("/reports/returns", response_class=HTMLResponse)
def returns_report(
    request: Request,
    date_from: str = Query(""),
    date_to: str = Query(""),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    start = parse_date(date_from, date.today().replace(day=1))
    end = parse_date(date_to, date.today())
    s_rets = db.query(SupplierReturn).filter(SupplierReturn.date >= start, SupplierReturn.date <= end).all()
    c_rets = db.query(CustomerReturn).filter(CustomerReturn.date >= start, CustomerReturn.date <= end).all()
    return templates.TemplateResponse("reports/returns.html", {
        "request": request, "current_user": current_user,
        "supplier_returns": s_rets, "customer_returns": c_rets,
        "date_from": start.isoformat(), "date_to": end.isoformat(),
        "active_tab": "reports", "error": None, "success": None,
    })


@router.get("/reports/stock-valuation", response_class=HTMLResponse)
def stock_valuation(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    items = db.query(Item).filter(Item.status == "Active").order_by(Item.item_code).all()
    rows = []
    grand = Decimal("0")
    for item in items:
        val = money(item.current_stock) * money(item.purchase_price)
        grand += val
        rows.append({"item": item, "value": val})
    return templates.TemplateResponse("reports/stock_valuation.html", {
        "request": request, "current_user": current_user, "rows": rows, "grand": grand,
        "active_tab": "reports", "error": None, "success": None,
    })


@router.get("/reports/profit", response_class=HTMLResponse)
def profit_report(
    request: Request,
    date_from: str = Query(""),
    date_to: str = Query(""),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    start = parse_date(date_from, date.today().replace(day=1))
    end = parse_date(date_to, date.today())
    lines = db.query(SaleItem).join(Sale).filter(Sale.date >= start, Sale.date <= end).all()
    rows = []
    total_profit = Decimal("0")
    for line in lines:
        cost = money(line.item.purchase_price) * line.quantity
        revenue = money(line.subtotal)
        profit = revenue - cost
        total_profit += profit
        rows.append({"line": line, "sale": line.sale, "cost": cost, "revenue": revenue, "profit": profit})
    return templates.TemplateResponse("reports/profit.html", {
        "request": request, "current_user": current_user, "rows": rows, "total_profit": total_profit,
        "date_from": start.isoformat(), "date_to": end.isoformat(),
        "active_tab": "reports", "error": None, "success": None,
    })


@router.get("/reports/outstanding", response_class=HTMLResponse)
def outstanding_report(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    customers = db.query(Customer).filter(Customer.is_walk_in == False, Customer.current_balance != 0).order_by(Customer.current_balance.desc()).all()
    suppliers = db.query(Supplier).filter(Supplier.current_balance != 0).order_by(Supplier.current_balance.desc()).all()
    return templates.TemplateResponse("reports/outstanding.html", {
        "request": request, "current_user": current_user, "customers": customers, "suppliers": suppliers,
        "active_tab": "reports", "error": None, "success": None,
    })
