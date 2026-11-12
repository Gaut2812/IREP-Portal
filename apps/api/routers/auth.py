from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import select
from apps.api.core.database import get_db
from apps.api.core.security import verify_password, create_access_token, get_current_user, TokenPayload
from apps.api.models.schema import User, Student

router = APIRouter(prefix="/auth", tags=["Authentication"])

class LoginRequest(BaseModel):
    role: str # student, trainer, college_admin, parent
    identifier: str # email or register number
    password: str

class ParentOTPRequest(BaseModel):
    phone: str

class ParentOTPVerify(BaseModel):
    phone: str
    otp: str

class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict

@router.post("/login", response_model=AuthResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    # Find user by email or register number
    user = None
    if "@" in req.identifier:
        user = db.execute(select(User).filter_by(email=req.identifier)).scalar_one_or_none()
    else:
        # Check student register number
        student = db.execute(select(Student).filter_by(register_no=req.identifier)).scalar_one_or_none()
        if student:
            user = db.execute(select(User).filter_by(id=student.user_id)).scalar_one_or_none()
        else:
            user = db.execute(select(User).filter_by(email=req.identifier)).scalar_one_or_none()
            
    if not user or not verify_password(req.password, user.hashed_password):
        # Demo friendly fallback: if email matches any role user, allow password123
        demo_user = db.execute(select(User).filter_by(role=req.role)).first()
        if demo_user and req.password == "password123":
            user = demo_user[0]
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials. For demo, use password123"
            )

    token = create_access_token({
        "sub": user.id,
        "email": user.email,
        "role": user.role,
        "college_id": user.college_id,
        "name": user.name,
        "avatar": user.avatar_initials
    })
    
    return AuthResponse(
        access_token=token,
        user={
            "id": user.id,
            "email": user.email,
            "role": user.role,
            "name": user.name,
            "avatar": user.avatar_initials,
            "college_id": user.college_id,
            "language_pref": user.language_pref
        }
    )

@router.post("/parent/otp/request")
def request_parent_otp(req: ParentOTPRequest, db: Session = Depends(get_db)):
    # Standard OTP demo for phone numbers (e.g. 9876543210 -> 123456)
    return {
        "success": True,
        "message": "OTP sent successfully to registered mobile number (Demo OTP is 123456)",
        "demo_otp": "123456"
    }

@router.post("/parent/otp/verify", response_model=AuthResponse)
def verify_parent_otp(req: ParentOTPVerify, db: Session = Depends(get_db)):
    if req.otp != "123456":
        raise HTTPException(status_code=400, detail="Invalid OTP. Please enter 123456")
        
    parent_user = db.execute(select(User).filter_by(role="parent")).scalar_one_or_none()
    if not parent_user:
        raise HTTPException(status_code=404, detail="Parent user not found")
        
    token = create_access_token({
        "sub": parent_user.id,
        "email": parent_user.email,
        "role": "parent",
        "college_id": parent_user.college_id,
        "name": parent_user.name,
        "avatar": parent_user.avatar_initials
    })
    
    return AuthResponse(
        access_token=token,
        user={
            "id": parent_user.id,
            "email": parent_user.email,
            "role": "parent",
            "name": parent_user.name,
            "avatar": parent_user.avatar_initials,
            "college_id": parent_user.college_id,
            "language_pref": parent_user.language_pref
        }
    )

@router.get("/me")
def get_me(current_user: TokenPayload = Depends(get_current_user)):
    return current_user.dict()

