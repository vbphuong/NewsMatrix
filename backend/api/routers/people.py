from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import joinedload

from deps import bcrypt_context, db_dependency, user_dependency
from models import Role, User

router = APIRouter(
    prefix="/people",
    tags=["people"],
)


class RoleResponse(BaseModel):
    role_id: int
    role_name: str

    model_config = {"from_attributes": True}


class UserResponse(BaseModel):
    user_id: int
    email: str
    role_name: str
    updated_at: Optional[datetime] = None


class UserCreateRequest(BaseModel):
    email: EmailStr
    password: str
    role_name: str


class UserUpdateRequest(BaseModel):
    email: EmailStr
    password: Optional[str] = None
    role_name: str


class UserListResponse(BaseModel):
    user_id: int
    email: str
    role_name: str
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


def require_admin(current_user: user_dependency) -> None:
    if current_user.get("role") != "Admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")


def get_or_404_role(db, role_name: str) -> Role:
    role = db.query(Role).filter(Role.role_name == role_name).first()
    if not role:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Role '{role_name}' does not exist")
    return role


def serialize_user(user: User) -> UserListResponse:
    return UserListResponse(
        user_id=user.user_id,
        email=user.email,
        role_name=user.role.role_name if user.role else "User",
        updated_at=user.updated_at,
    )


@router.get("/roles", response_model=list[RoleResponse])
async def list_roles(current_user: user_dependency, db: db_dependency):
    require_admin(current_user)
    roles = db.query(Role).order_by(Role.role_name.asc()).all()
    return [RoleResponse(role_id=role.role_id, role_name=role.role_name) for role in roles]


@router.get("/users", response_model=list[UserListResponse])
async def list_users(current_user: user_dependency, db: db_dependency):
    require_admin(current_user)
    users = (
        db.query(User)
        .options(joinedload(User.role))
        .order_by(User.user_id.desc())
        .all()
    )
    return [serialize_user(user) for user in users]


@router.post("/users", response_model=UserListResponse, status_code=status.HTTP_201_CREATED)
async def create_user(current_user: user_dependency, db: db_dependency, payload: UserCreateRequest):
    require_admin(current_user)

    existing_user = db.query(User).filter(User.email == payload.email).first()
    if existing_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already exists")

    role = get_or_404_role(db, payload.role_name)
    user = User(
        email=payload.email,
        password=bcrypt_context.hash(payload.password),
        role_id=role.role_id,
        updated_at=datetime.now(timezone.utc),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return serialize_user(user)


@router.put("/users/{user_id}", response_model=UserListResponse)
async def update_user(user_id: int, current_user: user_dependency, db: db_dependency, payload: UserUpdateRequest):
    require_admin(current_user)

    user = db.query(User).options(joinedload(User.role)).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    existing_user = db.query(User).filter(User.email == payload.email, User.user_id != user_id).first()
    if existing_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already exists")

    role = get_or_404_role(db, payload.role_name)
    user.email = payload.email
    user.role_id = role.role_id
    user.updated_at = datetime.now(timezone.utc)
    if payload.password:
        user.password = bcrypt_context.hash(payload.password)

    db.commit()
    db.refresh(user)
    return serialize_user(user)


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: int, current_user: user_dependency, db: db_dependency):
    require_admin(current_user)

    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    db.delete(user)
    db.commit()
    return None
