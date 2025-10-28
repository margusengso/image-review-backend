from fastapi import FastAPI, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
import requests

from .auth import verify_google_token, create_jwt, get_current_user_payload
from .db import SessionLocal, init_db
from .models import DbInitTest, User, TestImage, LabelSubmission

app = FastAPI(title="Image Review Backend")

MANIFEST_URL = "https://homework-bucket-images.s3.eu-north-1.amazonaws.com/manifest.json"

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
    with SessionLocal() as db:
        seed_from_manifest_if_needed(db)


def seed_from_manifest_if_needed(db: Session):
    """Read the AWS manifest and insert images if not yet present."""
    already = db.execute(select(TestImage.id).limit(1)).first()
    if already:
        return

    try:
        resp = requests.get(MANIFEST_URL, timeout=15)
        resp.raise_for_status()
        manifest = resp.json()
        images = manifest.get("images", [])
    except Exception as e:
        print(f"⚠️ Failed to load manifest: {e}")
        return

    to_insert = 0
    for item in images:
        img_id = item.get("id")
        url = item.get("url")
        if not img_id or not url:
            continue
        db.add(TestImage(
            id=img_id,
            url=url,
            suggested_label=item.get("suggested_label"),
            confidence=item.get("confidence"),
        ))
        to_insert += 1

    if to_insert:
        db.commit()
        print(f"✅ Seeded {to_insert} images from manifest.json")


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

class LabelIn(BaseModel):
    image_id: str
    label: str


# ------------------- Auth (public) -----------------
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

# ------------------- Protected helpers -------------------
def require_user(db: Session, payload: dict) -> User:
    user = db.execute(select(User).where(User.sub == payload["sub"])).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user

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


@app.get("/api/images/next")
def get_next_image(payload=Depends(get_current_user_payload), db: Session = Depends(get_db)):
    """
    JWT-protected: return ONE image that the current user has NOT yet labeled.
    {
      "id": "img_123",
      "url": "https://...",
      "suggested_label": "dog",
      "confidence": 0.88
    }
    If no more images, returns all fields as None.
    """
    user = require_user(db, payload)

    # anti-join: image with NO submission by this user
    subquery = (
        select(LabelSubmission.id)
        .where(LabelSubmission.image_id == TestImage.id, LabelSubmission.user_id == user.id)
        .exists()
    )

    img = db.execute(select(TestImage).where(~subquery).order_by(TestImage.id).limit(1)).scalar_one_or_none()
    if not img:
        return {"id": None, "url": None, "suggested_label": None, "confidence": None}

    return {
        "id": img.id,
        "url": img.url,
        "suggested_label": img.suggested_label,
        "confidence": img.confidence,
    }


@app.post("/api/labels")
def submit_label(body: LabelIn, payload=Depends(get_current_user_payload), db: Session = Depends(get_db)):
    """
    JWT-protected: upsert user's FINAL label for an image.
    Body: {"image_id":"img_123","label":"dog"}
    """
    user = require_user(db, payload)

    img = db.execute(select(TestImage).where(TestImage.id == body.image_id)).scalar_one_or_none()
    if not img:
        raise HTTPException(status_code=404, detail="Image not found")

    submission = db.execute(
        select(LabelSubmission).where(
            LabelSubmission.image_id == body.image_id,
            LabelSubmission.user_id == user.id,
        )
    ).scalar_one_or_none()

    if submission:
        submission.label = body.label
    else:
        submission = LabelSubmission(image_id=body.image_id, user_id=user.id, label=body.label)
        db.add(submission)

    db.commit()
    return {"ok": True, "image_id": body.image_id, "label": body.label}