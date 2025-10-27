from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from .db import SessionLocal, init_db, DbInitTest

app = FastAPI(title="Image Review Backend")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

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