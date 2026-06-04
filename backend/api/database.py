from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from dotenv import load_dotenv
import os

load_dotenv(override=True)

SQLALCHEMY_DATABASE_URL = os.getenv("SQL_ALCHEMY_DATABASE_URL") 

engine = create_engine(SQLALCHEMY_DATABASE_URL)
 
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()