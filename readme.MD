# Image Review Backend

Simple FastAPI + SQLite backend.

Before running the backend ensure that port 8000 is not is use.

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



### Test Endpoint Backend

To verify that the backend is running correctly, open:
```
http://localhost:8000/api/health
```
You should see:
```json
{ "status": "ok" }
```

### Test Endpoint Backend + Database

To verify that both backend and database are running correctly, open:
```
http://localhost:8000/api/test
```
You should see:
```json
{ "message": "Inserted sample" }
```

### For Improvement

ATM Pushing to main branch initiates Actions to build the image on dockerhub, there are no separate environments implemented. This would be something to seriously consider.