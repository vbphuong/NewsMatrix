from typing import Annotated
from sqlalchemy.orm import Session 
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext
from jose import jwt, JWTError
from dotenv import load_dotenv
import os 
from api.database import SessionLocal
from api.models import User

load_dotenv()

SECRET_KEY = os.getenv("AUTH_SECRET_KEY")
ALGORITHM = os.getenv("AUTH_ALGORITHM")

def get_db():
    db = SessionLocal()
    try:
        yield db 
    finally: 
        db.close()

db_dependency = Annotated[Session, Depends(get_db)]

bcrypt_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_bearer = OAuth2PasswordBearer(tokenUrl="/auth/token")

async def get_current_user(token: Annotated[str, Depends(oauth2_bearer)]):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        user_id: int = payload.get("id")
        if username is None or user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate user")

        from api.services.scalability import get_redis_client
        import json
        cache = get_redis_client()
        if cache:
            cached_user = cache.get(f"user:profile:{user_id}")
            if cached_user:
                try:
                    return json.loads(cached_user)
                except Exception:
                    pass

        db = SessionLocal()
        try:
            user = db.query(User).filter(User.user_id == user_id).first()
            if not user:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate user")

            role_name = user.role.role_name if user.role else payload.get("role")
            user_data = {
                'username': user.email,
                'id': user.user_id,
                'role': role_name,
                'organization_id': user.organization_id,
            }
            if cache:
                try:
                    cache.set(f"user:profile:{user_id}", json.dumps(user_data), ex=120)  # cache for 2 minutes
                except Exception:
                    pass
            return user_data
        finally:
            db.close()
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate user")

user_dependency = Annotated[dict, Depends(get_current_user)]