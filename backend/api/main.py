from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import assistant, auth, categories, documents, news, organizations, people
from database import Base, engine, SessionLocal
from models import Role

app = FastAPI()

Base.metadata.create_all(bind=engine)

app.include_router(auth.router)
app.include_router(news.router)
app.include_router(categories.router)
app.include_router(documents.router)
app.include_router(assistant.router)
app.include_router(organizations.router)
app.include_router(people.router)


def seed_default_roles() -> None:
    db = SessionLocal()
    try:
        for role_name in ("User", "Admin", "Journalist"):
            existing_role = db.query(Role).filter(Role.role_name == role_name).first()
            if not existing_role:
                db.add(Role(role_name=role_name))
        db.commit()
    finally:
        db.close()


seed_default_roles()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def health_check():
    return "Health check complete"