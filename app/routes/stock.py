from decimal import Decimal
from fastapi import APIRouter, Depends, Request, Form, HTTPException, status, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, Item, StockMovement, ItemCategory, ItemType
from app.auth import get_current_user, log_audit
from app.services import next_code, apply_stock_change, money

router = APIRouter(prefix="/stock", tags=["stock"])
templates = Jinja2Templates(directory="app/templates")


@router.get("", response_class=HTMLResponse)
def list_items(
    request: Request,
    q: str = Query(""),
    brand: str = Query(""),
    category: str = Query(""),
    low_stock: str = Query(""),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Item)
    if q:
        like = f"%{q}%"
        query = query.filter(
            (Item.item_code.ilike(like)) |
            (Item.brand.ilike(like)) |
            (Item.size.ilike(like)) |
            (Item.pattern.ilike(like))
        )
    if brand:
        query = query.filter(Item.brand.ilike(f"%{brand}%"))
    if category:
        query = query.filter(Item.category == category)
    if low_stock:
        query = query.filter(Item.current_stock <= Item.reorder_level)

    items = query.order_by(Item.item_code).all()
    brands = [r[0] for r in db.query(Item.brand).distinct().order_by(Item.brand).all() if r[0]]
    categories = [c.name for c in db.query(ItemCategory).order_by(ItemCategory.name).all()]
    return templates.TemplateResponse("stock/list.html", {
        "request": request,
        "current_user": current_user,
        "items": items,
        "categories": categories,
        "brands": brands,
        "filters": {"q": q, "brand": brand, "category": category, "low_stock": low_stock},
        "active_tab": "stock",
        "error": None,
        "success": None,
    })


@router.get("/low", response_class=HTMLResponse)
def low_stock_report(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    items = db.query(Item).filter(Item.current_stock <= Item.reorder_level, Item.status == "Active").order_by(Item.current_stock).all()
    return templates.TemplateResponse("stock/low.html", {
        "request": request, "current_user": current_user, "items": items, "active_tab": "stock",
        "error": None, "success": None,
    })


@router.get("/new", response_class=HTMLResponse)
def new_item_form(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    categories = [c.name for c in db.query(ItemCategory).order_by(ItemCategory.name).all()]
    types = [t.name for t in db.query(ItemType).order_by(ItemType.name).all()]
    return templates.TemplateResponse("stock/form.html", {
        "request": request, "current_user": current_user, "item": None,
        "categories": categories, "types": types, "active_tab": "stock",
        "error": None, "success": None,
    })


@router.post("/new")
def create_item(
    request: Request,
    brand: str = Form(...),
    size: str = Form(""),
    pattern: str = Form(""),
    type: str = Form(""),
    category: str = Form(...),
    purchase_price: str = Form("0"),
    sale_price: str = Form("0"),
    reorder_level: int = Form(5),
    unit: str = Form("Piece"),
    status: str = Form("Active"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    code = next_code(db, Item, "item_code", "TYR")
    item = Item(
        item_code=code,
        brand=brand.strip(),
        size=size.strip() or None,
        pattern=pattern.strip() or None,
        type=type or None,
        category=category,
        purchase_price=money(purchase_price),
        sale_price=money(sale_price),
        current_stock=0,
        reorder_level=reorder_level,
        unit=unit,
        status=status,
    )
    db.add(item)
    db.commit()
    log_audit(db, current_user.id, "Create Item", f"Created item {code} — {brand}")
    return RedirectResponse(url="/stock", status_code=303)


@router.get("/{item_id}", response_class=HTMLResponse)
def item_detail(item_id: int, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(404, "Item not found")
    movements = db.query(StockMovement).filter(StockMovement.item_id == item_id).order_by(StockMovement.created_at.desc()).all()
    return templates.TemplateResponse("stock/detail.html", {
        "request": request, "current_user": current_user, "item": item, "movements": movements,
        "active_tab": "stock", "error": None, "success": None,
    })


@router.get("/{item_id}/edit", response_class=HTMLResponse)
def edit_item_form(item_id: int, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(404, "Item not found")
    categories = [c.name for c in db.query(ItemCategory).order_by(ItemCategory.name).all()]
    types = [t.name for t in db.query(ItemType).order_by(ItemType.name).all()]
    return templates.TemplateResponse("stock/form.html", {
        "request": request, "current_user": current_user, "item": item,
        "categories": categories, "types": types, "active_tab": "stock",
        "error": None, "success": None,
    })


@router.post("/{item_id}/edit")
def update_item(
    item_id: int,
    request: Request,
    brand: str = Form(...),
    size: str = Form(""),
    pattern: str = Form(""),
    type: str = Form(""),
    category: str = Form(...),
    purchase_price: str = Form("0"),
    sale_price: str = Form("0"),
    reorder_level: int = Form(5),
    unit: str = Form("Piece"),
    status: str = Form("Active"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(404, "Item not found")
    item.brand = brand.strip()
    item.size = size.strip() or None
    item.pattern = pattern.strip() or None
    item.type = type or None
    item.category = category
    item.purchase_price = money(purchase_price)
    item.sale_price = money(sale_price)
    item.reorder_level = reorder_level
    item.unit = unit
    item.status = status
    db.commit()
    log_audit(db, current_user.id, "Update Item", f"Updated item {item.item_code}")
    return RedirectResponse(url=f"/stock/{item_id}", status_code=303)


@router.get("/{item_id}/adjust", response_class=HTMLResponse)
def adjust_form(item_id: int, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(404, "Item not found")
    return templates.TemplateResponse("stock/adjust.html", {
        "request": request, "current_user": current_user, "item": item,
        "active_tab": "stock", "error": None, "success": None,
    })


@router.post("/{item_id}/adjust")
def adjust_stock(
    item_id: int,
    request: Request,
    quantity_change: int = Form(...),
    reason: str = Form(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(404, "Item not found")
    if not reason.strip():
        return templates.TemplateResponse("stock/adjust.html", {
            "request": request, "current_user": current_user, "item": item,
            "active_tab": "stock", "error": "Reason is required", "success": None,
        })
    try:
        apply_stock_change(
            db, item, quantity_change, "adjustment",
            user_id=current_user.id, reference_type="adjustment", note=reason.strip()
        )
        db.commit()
        log_audit(db, current_user.id, "Stock Adjustment", f"{item.item_code}: {quantity_change:+d} — {reason}")
    except ValueError as e:
        return templates.TemplateResponse("stock/adjust.html", {
            "request": request, "current_user": current_user, "item": item,
            "active_tab": "stock", "error": str(e), "success": None,
        })
    return RedirectResponse(url=f"/stock/{item_id}", status_code=303)
