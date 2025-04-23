import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv
from typing import List, Union
from sqlalchemy.engine.url import URL # Correct import for SQLAlchemy 2.0+

# Load .env file if it exists
load_dotenv()

class Settings(BaseSettings):
    PROJECT_NAME: str = "Online Exam System API"
    API_V1_STR: str = "/api/v1"

    # Database configuration (adjust driver based on requirements.txt)
    DB_DRIVER: str = os.getenv("DB_DRIVER", "mysql+aiomysql") # Use 'postgresql+asyncpg' for PostgreSQL
    DB_HOST: str = os.getenv("DB_HOST", "192.168.200.3")
    DB_PORT: int = int(os.getenv("DB_PORT", 3306))
    DB_USER: str = os.getenv("DB_USER", "root")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "123456")
    DB_NAME: str = os.getenv("DB_NAME", "ExamSys_2025_db")

    # Asynchronous SQLAlchemy database URL
    # Note: For aiomysql, ensure the database exists before connecting
    # Note: For asyncpg, the URL format is slightly different
    SQLALCHEMY_DATABASE_URI: Union[URL, str] = URL.create(
        drivername=DB_DRIVER,
        username=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
    )

    # JWT Settings
    SECRET_KEY: str = os.getenv("SECRET_KEY", "a_very_secret_key_change_this_in_production") # CHANGE THIS!
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7 # 7 days

    # CORS Origins (adjust in production)
    BACKEND_CORS_ORIGINS: List[str] = ["*"] # Allows all origins for development

    # Celery / Redis
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", 6379))
    CELERY_BROKER_URL: str = f"redis://{REDIS_HOST}:{REDIS_PORT}/0"
    CELERY_RESULT_BACKEND: str = f"redis://{REDIS_HOST}:{REDIS_PORT}/1"

    class Config:
        case_sensitive = True
        # If using .env file:
        env_file = ".env"
        env_file_encoding = 'utf-8'

settings = Settings()

# Example .env file content:
# DB_HOST=127.0.0.1
# DB_PORT=3306
# DB_USER=myuser
# DB_PASSWORD=mypassword
# DB_NAME=myexamdb
# SECRET_KEY=super_secret_random_string_please_generate_one
# REDIS_HOST=127.0.0.1
# REDIS_PORT=6379