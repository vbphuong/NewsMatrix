from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func

from deps import db_dependency, user_dependency
from models import Category

router = APIRouter(
    prefix="/categories",
    tags=["categories"],
)


class CategoryRequest(BaseModel):
    name: str


class CategoryResponse(BaseModel):
    category_id: int
    name: str


def require_admin(current_user: user_dependency) -> None:
    if current_user.get("role") != "Admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")


def get_category_or_404(db, category_id: int) -> Category:
    category = db.query(Category).filter(Category.category_id == category_id).first()
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    return category


@router.get("", response_model=list[CategoryResponse])
async def list_categories(db: db_dependency):
    categories = db.query(Category).order_by(func.lower(Category.name).asc()).all()
    return [CategoryResponse(category_id=category.category_id, name=category.name) for category in categories]


@router.post("", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
async def create_category(payload: CategoryRequest, current_user: user_dependency, db: db_dependency):
    require_admin(current_user)

    category_name = payload.name.strip()
    if not category_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Category name is required")

    existing = db.query(Category).filter(func.lower(Category.name) == category_name.lower()).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Category already exists")

    category = Category(name=category_name)
    db.add(category)
    db.commit()
    db.refresh(category)

    return CategoryResponse(category_id=category.category_id, name=category.name)


@router.put("/{category_id}", response_model=CategoryResponse)
async def update_category(category_id: int, payload: CategoryRequest, current_user: user_dependency, db: db_dependency):
    require_admin(current_user)

    category = get_category_or_404(db, category_id)
    category_name = payload.name.strip()
    if not category_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Category name is required")

    existing = (
        db.query(Category)
        .filter(func.lower(Category.name) == category_name.lower(), Category.category_id != category_id)
        .first()
    )
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Category already exists")

    category.name = category_name
    db.commit()
    db.refresh(category)

    return CategoryResponse(category_id=category.category_id, name=category.name)


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(category_id: int, current_user: user_dependency, db: db_dependency):
    require_admin(current_user)
    category = get_category_or_404(db, category_id)

    db.delete(category)
    db.commit()
    return None