from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, ItemCategory, ItemType, Item
from app.auth import get_current_user

router = APIRouter(prefix="/settings", tags=["settings"])
templates = Jinja2Templates(directory="app/templates")

@router.get("/", response_class=HTMLResponse)
def settings_page(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db), error: str = None):
    categories = db.query(ItemCategory).order_by(ItemCategory.name).all()
    types = db.query(ItemType).order_by(ItemType.name).all()
    return templates.TemplateResponse("settings/list.html", {
        "request": request, "current_user": current_user,
        "categories": categories, "types": types,
        "active_tab": "settings", "error": error
    })

@router.post("/categories/add")
def add_category(request: Request, name: str = Form(...), current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    name = name.strip()
    if not name:
        return RedirectResponse(url="/settings?error=Category name cannot be empty", status_code=303)
    if db.query(ItemCategory).filter(ItemCategory.name == name).first():
        return RedirectResponse(url="/settings?error=Category already exists", status_code=303)
    db.add(ItemCategory(name=name))
    db.commit()
    return RedirectResponse(url="/settings", status_code=303)

@router.post("/categories/{cat_id}/delete")
def delete_category(cat_id: int, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    cat = db.query(ItemCategory).filter(ItemCategory.id == cat_id).first()
    if not cat:
        return RedirectResponse(url="/settings?error=Category not found", status_code=303)
    
    # Check if category is used
    if db.query(Item).filter(Item.category == cat.name).first():
        return RedirectResponse(url=f"/settings?error=Cannot delete category '{cat.name}' because it is in use by one or more items.", status_code=303)
        
    db.delete(cat)
    db.commit()
    return RedirectResponse(url="/settings", status_code=303)

@router.post("/types/add")
def add_type(request: Request, name: str = Form(...), current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    name = name.strip()
    if not name:
        return RedirectResponse(url="/settings?error=Type name cannot be empty", status_code=303)
    if db.query(ItemType).filter(ItemType.name == name).first():
        return RedirectResponse(url="/settings?error=Type already exists", status_code=303)
    db.add(ItemType(name=name))
    db.commit()
    return RedirectResponse(url="/settings", status_code=303)

@router.post("/types/{type_id}/delete")
def delete_type(type_id: int, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    typ = db.query(ItemType).filter(ItemType.id == type_id).first()
    if not typ:
        return RedirectResponse(url="/settings?error=Type not found", status_code=303)
        
    # Check if type is used
    if db.query(Item).filter(Item.type == typ.name).first():
        return RedirectResponse(url=f"/settings?error=Cannot delete type '{typ.name}' because it is in use.", status_code=303)
        
    db.delete(typ)
    db.commit()
    return RedirectResponse(url="/settings", status_code=303)
