import os
import uvicorn
from fastapi import FastAPI, Request, status, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from dotenv import load_dotenv

from app.database import engine, Base, SessionLocal
from app.models import User
from app.auth import hash_password
from app.routes import auth, dashboard, stock, suppliers, customers, returns, ledger_reports, print_pdf, settings
from app.services import ensure_walk_in_customer

load_dotenv()

try:
    Base.metadata.create_all(bind=engine)
    print("Database tables initialized successfully.")
except Exception as e:
    print(f"Error initializing database: {e}")

db = SessionLocal()
try:
    admin_user = db.query(User).filter(User.username == "admin").first()
    if not admin_user:
        hashed = hash_password("admin123")
        admin_user = User(
            username="admin",
            password_hash=hashed,
            role="Admin",
            status="Active"
        )
        db.add(admin_user)
        db.commit()
        print("Default admin user created (admin / admin123).")
    ensure_walk_in_customer(db)
    
    from app.models import ItemCategory, ItemType
    from app.services import CATEGORIES, ITEM_TYPES
    if not db.query(ItemCategory).first():
        for cat in CATEGORIES:
            db.add(ItemCategory(name=cat))
    if not db.query(ItemType).first():
        for t in ITEM_TYPES:
            db.add(ItemType(name=t))
            
    db.commit()
except Exception as e:
    print(f"Error seeding database: {e}")
finally:
    db.close()

app = FastAPI(title="Business Management System")


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if exc.status_code == status.HTTP_401_UNAUTHORIZED:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    raise exc

app.mount("/static", StaticFiles(directory="public/static"), name="static")

app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(stock.router)
app.include_router(suppliers.router)
app.include_router(customers.router)
app.include_router(returns.router)
app.include_router(ledger_reports.router)
app.include_router(print_pdf.router)
app.include_router(settings.router)

if __name__ == "__main__":
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("run:app", host=host, port=port, reload=True)
