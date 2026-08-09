from datetime import date
from decimal import Decimal
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models import User, Item, Sale, CustomerReturn, SupplierReturn, Customer, Supplier
from app.auth import get_current_user
from app.services import money, ensure_walk_in_customer

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
def dashboard_home(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ensure_walk_in_customer(db)
    db.commit()
    today = date.today()

    today_sales = db.query(func.coalesce(func.sum(Sale.total_amount), 0)).filter(Sale.date == today).scalar() or 0
    today_sales_count = db.query(func.count(Sale.id)).filter(Sale.date == today).scalar() or 0

    cust_ret_total = db.query(func.coalesce(func.sum(CustomerReturn.total_amount), 0)).filter(CustomerReturn.date == today).scalar() or 0
    supp_ret_total = db.query(func.coalesce(func.sum(SupplierReturn.total_amount), 0)).filter(SupplierReturn.date == today).scalar() or 0
    today_returns = money(cust_ret_total) + money(supp_ret_total)

    low_stock = db.query(Item).filter(Item.status == "Active", Item.current_stock <= Item.reorder_level).order_by(Item.current_stock).limit(8).all()
    low_stock_count = db.query(func.count(Item.id)).filter(Item.status == "Active", Item.current_stock <= Item.reorder_level).scalar() or 0

    receivables = db.query(func.coalesce(func.sum(Customer.current_balance), 0)).filter(Customer.is_walk_in == False).scalar() or 0
    payables = db.query(func.coalesce(func.sum(Supplier.current_balance), 0)).scalar() or 0

    return templates.TemplateResponse("home.html", {
        "request": request,
        "current_user": current_user,
        "active_tab": "dashboard",
        "today_sales": today_sales,
        "today_sales_count": today_sales_count,
        "today_returns": today_returns,
        "low_stock": low_stock,
        "low_stock_count": low_stock_count,
        "receivables": receivables,
        "payables": payables,
        "error": None,
        "success": None,
    })
