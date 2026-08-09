from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import (
    User, Sale, SaleItem, Purchase, PurchaseItem,
    SupplierReturn, SupplierReturnItem, CustomerReturn, CustomerReturnItem,
    Supplier, Customer, SupplierLedger, CustomerLedger, PaymentMade, PaymentReceived
)
from app.auth import get_current_user
from app.services import money

router = APIRouter(prefix="/print", tags=["print"])
templates = Jinja2Templates(directory="app/templates")

SHOP_NAME = "Business System"
SHOP_TAGLINE = "Professional Tyre & Auto Parts"

_weasy_html = None
_weasy_tried = False


def _get_weasy():
    global _weasy_html, _weasy_tried
    if _weasy_tried:
        return _weasy_html
    _weasy_tried = True
    try:
        from weasyprint import HTML as WeasyHTML
        _weasy_html = WeasyHTML
    except Exception as e:
        print(f"WeasyPrint unavailable ({e}); print routes will serve printable HTML.")
        _weasy_html = None
    return _weasy_html


def render_pdf(request: Request, template_name: str, context: dict):
    html_str = templates.get_template(template_name).render({**context, "request": request})
    WeasyHTML = _get_weasy()
    if WeasyHTML is not None:
        try:
            pdf = WeasyHTML(string=html_str, base_url=str(request.base_url)).write_pdf()
            return Response(content=pdf, media_type="application/pdf")
        except Exception as e:
            print(f"WeasyPrint PDF failed ({e}); falling back to HTML.")
    return HTMLResponse(content=html_str)


@router.get("/sale/{sale_id}")
def print_sale(sale_id: int, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    sale = db.query(Sale).options(joinedload(Sale.customer), joinedload(Sale.items).joinedload(SaleItem.item)).filter(Sale.id == sale_id).first()
    if not sale:
        raise HTTPException(404)
    return render_pdf(request, "print/sale.html", {
        "sale": sale, "shop_name": SHOP_NAME, "shop_tagline": SHOP_TAGLINE,
    })


@router.get("/purchase/{purchase_id}")
def print_purchase(purchase_id: int, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    purchase = db.query(Purchase).options(joinedload(Purchase.supplier), joinedload(Purchase.items).joinedload(PurchaseItem.item)).filter(Purchase.id == purchase_id).first()
    if not purchase:
        raise HTTPException(404)
    return render_pdf(request, "print/purchase.html", {
        "purchase": purchase, "shop_name": SHOP_NAME, "shop_tagline": SHOP_TAGLINE,
    })


@router.get("/supplier-return/{return_id}")
def print_supplier_return(return_id: int, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ret = db.query(SupplierReturn).options(
        joinedload(SupplierReturn.supplier),
        joinedload(SupplierReturn.items).joinedload(SupplierReturnItem.item)
    ).filter(SupplierReturn.id == return_id).first()
    if not ret:
        raise HTTPException(404)
    return render_pdf(request, "print/return.html", {
        "ret": ret, "party": ret.supplier, "party_label": "Supplier",
        "return_no": ret.return_no, "shop_name": SHOP_NAME, "shop_tagline": SHOP_TAGLINE,
        "kind": "Supplier Return",
    })


@router.get("/customer-return/{return_id}")
def print_customer_return(return_id: int, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ret = db.query(CustomerReturn).options(
        joinedload(CustomerReturn.customer),
        joinedload(CustomerReturn.items).joinedload(CustomerReturnItem.item)
    ).filter(CustomerReturn.id == return_id).first()
    if not ret:
        raise HTTPException(404)
    return render_pdf(request, "print/return.html", {
        "ret": ret, "party": ret.customer, "party_label": "Customer",
        "return_no": ret.return_no, "shop_name": SHOP_NAME, "shop_tagline": SHOP_TAGLINE,
        "kind": "Customer Return",
    })


@router.get("/supplier-ledger/{supplier_id}")
def print_supplier_ledger(supplier_id: int, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    supplier = db.query(Supplier).filter(Supplier.id == supplier_id).first()
    if not supplier:
        raise HTTPException(404)
    ledger = db.query(SupplierLedger).filter(SupplierLedger.supplier_id == supplier_id).order_by(SupplierLedger.date, SupplierLedger.id).all()
    return render_pdf(request, "print/ledger.html", {
        "party_name": supplier.name, "party_code": supplier.supplier_code,
        "title": "Supplier Account Statement", "ledger": ledger,
        "balance": supplier.current_balance, "shop_name": SHOP_NAME, "shop_tagline": SHOP_TAGLINE,
    })


@router.get("/customer-ledger/{customer_id}")
def print_customer_ledger(customer_id: int, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(404)
    ledger = db.query(CustomerLedger).filter(CustomerLedger.customer_id == customer_id).order_by(CustomerLedger.date, CustomerLedger.id).all()
    return render_pdf(request, "print/ledger.html", {
        "party_name": customer.name, "party_code": customer.customer_code,
        "title": "Customer Account Statement", "ledger": ledger,
        "balance": customer.current_balance, "shop_name": SHOP_NAME, "shop_tagline": SHOP_TAGLINE,
    })


@router.get("/cash-summary")
def print_cash_summary(
    request: Request,
    day: str = Query(""),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from datetime import datetime
    cash_day = datetime.strptime(day, "%Y-%m-%d").date() if day else date.today()
    rows = []
    for s in db.query(Sale).filter(Sale.date == cash_day, Sale.payment_method == "Cash").all():
        if s.amount_received and money(s.amount_received) > 0:
            rows.append({"desc": f"Sale {s.invoice_no}", "in": money(s.amount_received), "out": 0})
    for p in db.query(PaymentReceived).filter(PaymentReceived.date == cash_day, PaymentReceived.payment_method == "Cash").all():
        rows.append({"desc": f"Receipt {p.receipt_no}", "in": money(p.amount), "out": 0})
    for p in db.query(Purchase).filter(Purchase.date == cash_day, Purchase.payment_method == "Cash").all():
        if p.amount_paid and money(p.amount_paid) > 0:
            rows.append({"desc": f"Purchase {p.invoice_no}", "in": 0, "out": money(p.amount_paid)})
    for p in db.query(PaymentMade).filter(PaymentMade.date == cash_day, PaymentMade.payment_method == "Cash").all():
        rows.append({"desc": f"Payment {p.payment_no}", "in": 0, "out": money(p.amount)})
    total_in = sum((r["in"] for r in rows), money(0))
    total_out = sum((r["out"] for r in rows), money(0))
    return render_pdf(request, "print/cash_summary.html", {
        "day": cash_day, "rows": rows, "total_in": total_in, "total_out": total_out,
        "shop_name": SHOP_NAME, "shop_tagline": SHOP_TAGLINE,
    })
