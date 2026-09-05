from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr

from database import get_db
from models import User

router = APIRouter(prefix="/users", tags=["Users"])

class UserCreate(BaseModel):
    email: EmailStr

class UserResponse(BaseModel):
    id: int
    email: str

    class Config:
        from_attributes = True

@router.post("/auth", response_model=UserResponse)
def auth_user(user_data: UserCreate, db: Session = Depends(get_db)):
    # Ищем пользователя по email
    user = db.query(User).filter(User.email == user_data.email).first()
    
    # Если такого нет - создаем нового (Регистрация)
    if not user:
        user = User(email=user_data.email)
        db.add(user)
        db.commit()
        db.refresh(user)
        
    # Возвращаем данные пользователя (Вход)
    return user