import os
import ssl
from datetime import datetime, timezone
from sqlalchemy import create_engine, String, ForeignKey, DateTime, JSON, Integer
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from sqlalchemy.engine import URL

def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)

def database_settings():
    url = os.getenv('DATABASE_URL')
    if not url and os.getenv('DB_HOST'):
        url = URL.create(
            'mysql+pymysql', username=os.environ['DB_USER'],
            password=os.environ['DB_PASSWORD'], host=os.environ['DB_HOST'],
            port=int(os.getenv('DB_PORT', '3306')),
            database=os.getenv('DB_NAME', 'naturalens'), query={'charset': 'utf8mb4'},
        )
    url = url or 'sqlite:///./naturalens.db'
    options = {}
    if os.getenv('DB_SSL_CA'):
        # Verifica tanto la autoridad certificadora como el nombre del servidor RDS.
        options['ssl'] = ssl.create_default_context(cafile=os.environ['DB_SSL_CA'])
    return url, options

db_url, connect_options = database_settings()
engine = create_engine(db_url, connect_args=connect_options, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    phone: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

class LoginSession(Base):
    __tablename__ = 'sessions'
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    csrf: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)

class Capture(Base):
    __tablename__ = 'captures'
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    photo_key: Mapped[str] = mapped_column(String(255))
    predictions: Mapped[list] = mapped_column(JSON)
    inference_ms: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, index=True)

class View(Base):
    __tablename__ = 'views'
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    capture_id: Mapped[int] = mapped_column(ForeignKey('captures.id'), index=True)
    viewed_at: Mapped[datetime] = mapped_column(DateTime, default=now)

def get_db():
    with SessionLocal() as db:
        yield db
