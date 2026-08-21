from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.core.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    connect_args={"options": "-c client_encoding=UTF8"},  # 强制 UTF-8，修复 Windows 中文乱码
)

# 双重保险：每条新连接建立后再 SET client_encoding
@event.listens_for(engine, "connect")
def set_encoding(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("SET client_encoding TO 'UTF8'")
    cursor.close()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
