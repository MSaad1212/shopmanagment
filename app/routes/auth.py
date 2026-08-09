from fastapi import APIRouter, Depends, Request, Form, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from app.database import get_db
from app.models import User, AuditLog
from app.auth import (
    hash_password, verify_password, create_session_token, session_max_age,
    get_current_user, require_admin, SESSION_COOKIE_NAME, log_audit
)
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@router.post("/login")
def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    remember: str = Form(None),
    db: Session = Depends(get_db)
):
    remember_me = remember is not None
    user = db.query(User).filter(User.username == username).first()

    if not user:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Invalid username or password"}
        )

    if user.status != "Active":
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Account is inactive. Contact administrator."}
        )

    if user.locked_until and user.locked_until > datetime.utcnow():
        lock_remaining = (user.locked_until - datetime.utcnow()).total_seconds()
        minutes_remaining = int(lock_remaining // 60) + 1
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": f"Account is locked due to multiple failed login attempts. Try again in {minutes_remaining} min."}
        )

    if verify_password(password, user.password_hash):
        user.failed_attempts = 0
        user.locked_until = None
        db.commit()

        token = create_session_token(user.id, remember=remember_me)
        log_audit(db, user.id, "Login", f"User {username} logged in successfully.")

        response = RedirectResponse(url="/", status_code=303)
        response.set_cookie(
            key=SESSION_COOKIE_NAME,
            value=token,
            httponly=True,
            max_age=session_max_age(remember_me),
            samesite="lax"
        )
        return response
    else:
        user.failed_attempts += 1
        if user.failed_attempts >= 5:
            user.locked_until = datetime.utcnow() + timedelta(minutes=10)
            db.commit()
            log_audit(db, user.id, "Account Locked", f"User {username} locked due to 5 failed attempts.")
            return templates.TemplateResponse(
                "login.html",
                {"request": request, "error": "Account locked for 10 minutes due to 5 failed attempts."}
            )
        else:
            db.commit()
            log_audit(db, user.id, "Failed Login", f"User {username} failed login attempt {user.failed_attempts}.")
            return templates.TemplateResponse(
                "login.html",
                {"request": request, "error": f"Invalid username or password. Attempt {user.failed_attempts}/5."}
            )


@router.get("/logout")
def logout(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if token:
        from app.auth import get_user_id_from_token
        uid = get_user_id_from_token(token)
        if uid:
            log_audit(db, uid, "Logout", "User logged out.")

    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie(SESSION_COOKIE_NAME)
    return response


@router.get("/users", response_class=HTMLResponse)
def list_users(request: Request, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    users = db.query(User).all()
    return templates.TemplateResponse(
        "users.html",
        {"request": request, "users": users, "current_user": current_user, "error": None, "success": None, "active_tab": "users"}
    )


@router.post("/users")
def create_user(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    role: str = Form("Admin"),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    existing = db.query(User).filter(User.username == username).first()
    if existing:
        users = db.query(User).all()
        return templates.TemplateResponse(
            "users.html",
            {"request": request, "users": users, "current_user": current_user, "error": "Username already exists", "success": None, "active_tab": "users"}
        )

    hashed = hash_password(password)
    new_user = User(username=username, password_hash=hashed, role=role, status="Active")
    db.add(new_user)
    db.commit()

    log_audit(db, current_user.id, "Create User", f"Created user {username} with role {role}.")
    return RedirectResponse(url="/users", status_code=303)


@router.post("/users/{user_id}/toggle-status")
def toggle_user_status(
    user_id: int,
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.id == current_user.id:
        users = db.query(User).all()
        return templates.TemplateResponse(
            "users.html",
            {"request": request, "users": users, "current_user": current_user, "error": "Cannot deactivate yourself", "success": None, "active_tab": "users"}
        )

    new_status = "Inactive" if user.status == "Active" else "Active"
    user.status = new_status
    db.commit()

    log_audit(db, current_user.id, "Toggle User Status", f"Toggled status of user {user.username} to {new_status}.")
    return RedirectResponse(url="/users", status_code=303)


@router.post("/users/{user_id}/reset-password")
def reset_user_password(
    user_id: int,
    request: Request,
    new_password: str = Form(...),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if len(new_password) < 4:
        users = db.query(User).all()
        return templates.TemplateResponse(
            "users.html",
            {"request": request, "users": users, "current_user": current_user, "error": "Password must be at least 4 characters", "success": None, "active_tab": "users"}
        )
    user.password_hash = hash_password(new_password)
    user.failed_attempts = 0
    user.locked_until = None
    db.commit()
    log_audit(db, current_user.id, "Reset Password", f"Admin reset password for user {user.username}.")
    users = db.query(User).all()
    return templates.TemplateResponse(
        "users.html",
        {"request": request, "users": users, "current_user": current_user, "error": None, "success": f"Password reset for {user.username}", "active_tab": "users"}
    )


@router.get("/profile", response_class=HTMLResponse)
def profile_page(request: Request, current_user: User = Depends(get_current_user)):
    return templates.TemplateResponse(
        "profile.html",
        {"request": request, "current_user": current_user, "error": None, "success": None, "active_tab": "profile"}
    )


@router.post("/profile")
def update_profile(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not verify_password(current_password, current_user.password_hash):
        return templates.TemplateResponse(
            "profile.html",
            {"request": request, "current_user": current_user, "error": "Current password is incorrect", "success": None, "active_tab": "profile"}
        )
    if new_password != confirm_password:
        return templates.TemplateResponse(
            "profile.html",
            {"request": request, "current_user": current_user, "error": "New passwords do not match", "success": None, "active_tab": "profile"}
        )
    if len(new_password) < 4:
        return templates.TemplateResponse(
            "profile.html",
            {"request": request, "current_user": current_user, "error": "Password must be at least 4 characters", "success": None, "active_tab": "profile"}
        )
    current_user.password_hash = hash_password(new_password)
    db.commit()
    log_audit(db, current_user.id, "Change Password", "User changed their own password.")
    return templates.TemplateResponse(
        "profile.html",
        {"request": request, "current_user": current_user, "error": None, "success": "Password updated successfully", "active_tab": "profile"}
    )


@router.get("/audit-log", response_class=HTMLResponse)
def audit_log_page(
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    logs = db.query(AuditLog).order_by(AuditLog.timestamp.desc()).limit(200).all()
    return templates.TemplateResponse(
        "audit_log.html",
        {"request": request, "current_user": current_user, "logs": logs, "active_tab": "audit"}
    )
