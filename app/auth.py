import os, datetime
from fastapi import HTTPException, Header, Depends
from jose import jwt, JWTError, ExpiredSignatureError
from google.oauth2 import id_token
from google.auth.transport import requests as grequests
from dotenv import load_dotenv

load_dotenv()  # Using just one default environment for this case. no local, dev, staging and prod logic...

JWT_SECRET_KEY     = os.getenv("JWT_SECRET_KEY")
JWT_ALGORITHM      = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "240"))
GOOGLE_CLIENT_ID   = os.getenv("GOOGLE_CLIENT_ID")

def verify_google_token(token: str):
    try:
        return id_token.verify_oauth2_token(token, grequests.Request(), audience=GOOGLE_CLIENT_ID)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid Google credential")

def create_jwt(user_sub: str) -> str:
    exp = datetime.datetime.utcnow() + datetime.timedelta(minutes=JWT_EXPIRE_MINUTES)
    payload = {"sub": user_sub, "exp": exp}
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

def verify_jwt(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

def get_current_user_payload(authorization: str = Header(...)):
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="Invalid auth header format")
    return verify_jwt(token)