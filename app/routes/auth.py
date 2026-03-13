import os
from datetime import timedelta
from fastapi import APIRouter, Depends, Request, Form, status, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.core.auth import authenticate_user, create_access_token, get_password_hash, ACCESS_TOKEN_EXPIRE_MINUTES, verify_password, oauth
from app.core.ui import templates, render_template

router = APIRouter(tags=["Authentication"])

@router.get("/login/google")
async def login_google(request: Request):
    # Google will redirect back to this URL
    redirect_uri = request.url_for('auth_google')
    return await oauth.google.authorize_redirect(request, str(redirect_uri))

@router.get("/auth/google")
async def auth_google(request: Request, db: Session = Depends(get_db)):
    try:
        token = await oauth.google.authorize_access_token(request)
    except Exception:
        return RedirectResponse(url="/login?error=Could+not+authenticate+with+Google")

    user_info = token.get('userinfo')
    if not user_info:
        # Extra safety: fetch userinfo manually if not parsed automatically
        resp = await oauth.google.get('https://www.googleapis.com/oauth2/v3/userinfo', token=token)
        user_info = resp.json()

    if not user_info:
        return RedirectResponse(url="/login?error=Failed+to+get+user+info")

    email = user_info.get('email')
    username = user_info.get('name') or (email.split('@')[0] if email else "GoogleUser")
    
    # Check if user exists
    user = db.query(User).filter(User.email == email).first()
    
    if not user:
        # Create new user for Google Sign-in
        # They won't have a password, so we set a random long hash that can't be guessed
        placeholder_pass = get_password_hash(os.urandom(32).hex())
        user = User(
            username=username,
            email=email,
            hashed_password=placeholder_pass
        )
        db.add(user)
        db.commit()
    
    # Create session token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    
    response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(
        key="access_token", 
        value=f"Bearer {access_token}", 
        httponly=True,
        max_age=60 * 60 * 24 * 7,
        samesite="lax"
    )
    return response

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return render_template("auth/login.html", request)

@router.post("/login")
async def login(
    response: Response,
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    user = authenticate_user(db, username, password)
    if not user:
        return render_template(
            "auth/login.html", 
            request,
            {"error": "Invalid username or password"}
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    
    redirect_resp = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    redirect_resp.set_cookie(
        key="access_token", 
        value=f"Bearer {access_token}", 
        httponly=True,
        max_age=60 * 60 * 24 * 7,
        samesite="lax"
    )
    return redirect_resp

@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return render_template("auth/register.html", request)

@router.post("/register")
async def register(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    db: Session = Depends(get_db)
):
    if password != confirm_password:
        return render_template(
            "auth/register.html", 
            request,
            {"error": "Passwords do not match"}
        )
    
    existing_user = db.query(User).filter((User.username == username) | (User.email == email)).first()
    if existing_user:
        return render_template(
            "auth/register.html", 
            request,
            {"error": "Username or email already exists"}
        )
    
    hashed_password = get_password_hash(password)
    new_user = User(username=username, email=email, hashed_password=hashed_password)
    db.add(new_user)
    db.commit()
    
    return RedirectResponse(url="/login?msg=Registered+successfully", status_code=status.HTTP_303_SEE_OTHER)

@router.get("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie("access_token")
    return response
