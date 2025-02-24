# main.py
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timedelta
from typing import Optional, List
from bson import ObjectId
from models import (
    User, UserInDB, Task, TaskCreate, TaskUpdate,
    TokenData, Token, UserCreate
)
from auth import (
    get_current_user, create_access_token,
    get_password_hash, verify_password
)
import os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Task Management API")

# Updated CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# MongoDB connection
MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
client = AsyncIOMotorClient(MONGODB_URL)
db = client.taskmanager

@app.on_event("startup")
async def create_indexes():
    await db.users.create_index("email", unique=True)
    await db.tasks.create_index("user_id")

@app.post("/api/auth/register", response_model=User)
async def register_user(user: UserCreate):
    try:
        # Check if the email is already registered
        if await db.users.find_one({"email": user.email}):
            raise HTTPException(status_code=400, detail="Email already registered")
        
        # Create a new user document
        user_dict = {
            "_id": ObjectId(),
            "username": user.username,
            "firstName": user.firstName,
            "lastName": user.lastName,
            "email": user.email,
            "phoneNumber": user.phoneNumber,
            "hashed_password": get_password_hash(user.password),
            "created_at": datetime.utcnow()
        }
        
        # Insert the user into the database
        await db.users.insert_one(user_dict)
        
        # Return the created user (excluding sensitive data like hashed_password)
        return {
            "id": str(user_dict["_id"]),
            "username": user_dict["username"],
            "firstName": user_dict["firstName"],
            "lastName": user_dict["lastName"],
            "email": user_dict["email"],
            "phoneNumber": user_dict["phoneNumber"],
            "created_at": user_dict["created_at"]
        }
    except Exception as e:
        print(f"Error during registration: {e}")  # Log the error for debugging
        raise HTTPException(status_code=500, detail=str(e))
    
@app.post("/api/auth/login", response_model=Token)
async def login(credentials: dict):
    try:
        emailOrUsername = credentials.get("emailOrUsername")
        password = credentials.get("password")

        print(f"Login attempt with email/username: {emailOrUsername}")  # Debug log
        print(f"Password: {password}")  # Debug log

        # Check if the user exists by email or username
        db_user = await db.users.find_one({
            "$or": [
                {"email": emailOrUsername},
                {"username": emailOrUsername}  # Treat the input as username if email not found
            ]
        })

        print(f"User found in database: {db_user}")  # Debug log

        # If user not found or password is incorrect
        if not db_user or not verify_password(password, db_user["hashed_password"]):
            print("User not found or password incorrect")  # Debug log
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email/username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Generate an access token
        access_token = create_access_token(data={"sub": db_user["email"]})
        return {"access_token": access_token, "token_type": "bearer"}
    except Exception as e:
        print(f"Error during login: {e}")  # Debug log
        raise HTTPException(status_code=500, detail=str(e))
@app.post("/api/tasks", response_model=Task)
async def create_task(task: TaskCreate, current_user: User = Depends(get_current_user)):
    try:
        task_dict = task.dict()
        task_dict["user_id"] = str(current_user["_id"])
        task_dict["created_at"] = datetime.utcnow()
        task_dict["_id"] = ObjectId()
        
        await db.tasks.insert_one(task_dict)
        
        created_task = await db.tasks.find_one({"_id": task_dict["_id"]})
        created_task["id"] = str(created_task.pop("_id"))
        return created_task
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/tasks/{task_id}", response_model=Task)
async def update_task(
    task_id: str,
    task_update: TaskUpdate,
    current_user: User = Depends(get_current_user)
):
    try:
        task_oid = ObjectId(task_id)
        task = await db.tasks.find_one({
            "_id": task_oid,
            "user_id": str(current_user["_id"])
        })
        
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        update_data = task_update.dict(exclude_unset=True)
        update_data["updated_at"] = datetime.utcnow()
        
        await db.tasks.update_one(
            {"_id": task_oid},
            {"$set": update_data}
        )
        
        updated_task = await db.tasks.find_one({"_id": task_oid})
        updated_task["id"] = str(updated_task.pop("_id"))
        return updated_task
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/tasks/{task_id}")
async def delete_task(task_id: str, current_user: User = Depends(get_current_user)):
    try:
        task_oid = ObjectId(task_id)
        task = await db.tasks.find_one({
            "_id": task_oid,
            "user_id": str(current_user["_id"])
        })
        
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        await db.tasks.delete_one({"_id": task_oid})
        return {"message": "Task deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/tasks")
async def get_tasks(
    current_user: User = Depends(get_current_user),
    page: int = 1,
    limit: int = 10,
    category: Optional[str] = None,
    priority: Optional[str] = None,
    completed: Optional[bool] = None,
    due_date: Optional[str] = None
):
    try:
        skip = (page - 1) * limit
        query = {"user_id": str(current_user["_id"])}
        
        if category:
            query["category"] = category
        if priority:
            query["priority"] = priority
        if completed is not None:
            query["completed"] = completed
        if due_date:
            query["due_date"] = due_date
            
        total = await db.tasks.count_documents(query)
        cursor = db.tasks.find(query).skip(skip).limit(limit)
        
        tasks = []
        async for task in cursor:
            task["id"] = str(task.pop("_id"))
            tasks.append(task)
        
        return {
            "tasks": tasks,
            "total": total,
            "page": page,
            "limit": limit
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)