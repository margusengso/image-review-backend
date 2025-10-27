# Image Review Backend

Simple FastAPI + SQLite backend.

---

## First run (setup)

```
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```


## Consecutive run

```
source .venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```