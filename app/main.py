from fastapi import FastAPI, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from .auth import verify_google_token, create_jwt, get_current_user_payload
from .db import SessionLocal, init_db
from .models import DbInitTest, User

app = FastAPI(title="Image Review Backend")


# ------------------- DB session dependency -------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ------------------- Misc endpoints -------------------
@app.get("/favicon.ico")
async def favicon():
    return {"status": "ok"}


@app.on_event("startup")
def startup_event():
    init_db()


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/test")
def add_sample(db: Session = Depends(get_db)):
    row = DbInitTest(testing_id="img_001")
    db.add(row)
    db.commit()
    return {"message": "Inserted sample"}


# ------------------- Schemas -------------------
class GoogleLoginIn(BaseModel):
    credential: str  # Google ID token (from GSI)


# ------------------- Auth (public) -------------------
@app.post("/api/auth/google")
def auth_google(payload: GoogleLoginIn, db: Session = Depends(get_db)):
    """
    PUBLIC: Verify Google ID token, upsert user, and return backend JWT + user.
    """
    if not payload.credential or not isinstance(payload.credential, str):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing Google credential")

    # 1) Verify Google token (audience is checked inside)
    try:
        info = verify_google_token(payload.credential)
    except HTTPException as e:
        raise e
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Google verification failed")

    sub = info.get("sub")
    if not sub:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Google token missing subject (sub)")

    # 2) Upsert user (create if missing, update if changed)
    user = db.execute(select(User).where(User.sub == sub)).scalar_one_or_none()

    if user is None:
        user = User(
            sub=sub,
            email=info.get("email"),
            given_name=info.get("given_name"),
            family_name=info.get("family_name"),
            picture=info.get("picture"),
        )
        db.add(user)
        try:
            db.commit()
        except IntegrityError:
            # Another request created the same user concurrently; fetch it
            db.rollback()
            user = db.execute(select(User).where(User.sub == sub)).scalar_one()
    else:
        # Update only provided fields (avoid overwriting with None)
        changed = False
        for field in ("email", "given_name", "family_name", "picture"):
            val = info.get(field)
            if val is not None and getattr(user, field) != val:
                setattr(user, field, val)
                changed = True
        if changed:
            db.commit()

    db.refresh(user)

    # 3) Issue backend JWT (4h as configured in env)
    token = create_jwt(sub)

    # 4) Return normalized user payload
    return {
        "ok": True,
        "token": token,
        "user": {
            "sub": user.sub,
            "email": user.email,
            "given_name": user.given_name,
            "family_name": user.family_name,
            "picture": user.picture,
        },
    }


# ------------------- Protected -------------------
@app.get("/api/me")
def me(payload=Depends(get_current_user_payload), db: Session = Depends(get_db)):
    """
    Protected: verify JWT, then resolve and return the current user from DB.
    Frontend will auto-logout on any 401.
    """
    user = db.execute(select(User).where(User.sub == payload["sub"])).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return {
        "sub": user.sub,
        "email": user.email,
        "given_name": user.given_name,
        "family_name": user.family_name,
        "picture": user.picture,
    }