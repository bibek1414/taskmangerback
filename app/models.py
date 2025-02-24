
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None

class UserBase(BaseModel):
    email: EmailStr

class UserCreate(BaseModel):
    username: str
    firstName: str
    lastName: str
    email: EmailStr
    phoneNumber: str
    password: str

class User(UserBase):
    id: str
    created_at: datetime

    class Config:
        orm_mode = True

class UserInDB(User):
    hashed_password: str

class TaskBase(BaseModel):
    title: str
    description: Optional[str] = None
    category: Optional[str] = None
    priority: Optional[str] = "medium"
    due_date: Optional[datetime] = None

class TaskCreate(TaskBase):
    pass

class TaskUpdate(TaskBase):
    completed: Optional[bool] = None

class Task(TaskBase):
    id: str
    user_id: str
    completed: bool = False
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True