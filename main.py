import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional
from database import db, create_document, get_documents
from bson import ObjectId

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- Models ----------
class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    notes: Optional[str] = Field(None, max_length=1000)
    completed: bool = False

class TaskUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    notes: Optional[str] = Field(None, max_length=1000)
    completed: Optional[bool] = None

class TaskOut(BaseModel):
    id: str
    title: str
    notes: Optional[str]
    completed: bool

# ---------- Utils ----------

def to_task_out(doc) -> TaskOut:
    return TaskOut(
        id=str(doc.get("_id")),
        title=doc.get("title", ""),
        notes=doc.get("notes"),
        completed=bool(doc.get("completed", False)),
    )

# ---------- Health ----------
@app.get("/")
def read_root():
    return {"message": "FastAPI Backend Ready"}

@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }

    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    return response

# ---------- Tasks API ----------
TASKS_COLLECTION = "task"

@app.get("/api/tasks", response_model=List[TaskOut])
def list_tasks():
    docs = get_documents(TASKS_COLLECTION, {}, limit=None)
    return [to_task_out(d) for d in docs]

@app.post("/api/tasks", response_model=TaskOut)
def create_task(task: TaskCreate):
    data = task.model_dump()
    inserted_id = create_document(TASKS_COLLECTION, data)
    created = db[TASKS_COLLECTION].find_one({"_id": ObjectId(inserted_id)})
    return to_task_out(created)

@app.put("/api/tasks/{task_id}", response_model=TaskOut)
def update_task(task_id: str, update: TaskUpdate):
    try:
        oid = ObjectId(task_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid task id")

    update_data = {k: v for k, v in update.model_dump(exclude_unset=True).items()}
    if not update_data:
        doc = db[TASKS_COLLECTION].find_one({"_id": oid})
        if not doc:
            raise HTTPException(status_code=404, detail="Task not found")
        return to_task_out(doc)

    res = db[TASKS_COLLECTION].find_one_and_update(
        {"_id": oid},
        {"$set": update_data},
        return_document=True
    )
    if not res:
        raise HTTPException(status_code=404, detail="Task not found")
    return to_task_out(res)

@app.delete("/api/tasks/{task_id}")
def delete_task(task_id: str):
    try:
        oid = ObjectId(task_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid task id")

    res = db[TASKS_COLLECTION].delete_one({"_id": oid})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
