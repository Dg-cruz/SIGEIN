from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
import os


def _normalize_database_url(raw_url: str) -> str:
    url = raw_url.strip().strip('"').strip("'")
    if url.startswith("postgres://"):
        url = "postgresql+psycopg2://" + url[len("postgres://") :]
    elif url.startswith("postgresql://") and "+psycopg2" not in url:
        url = "postgresql+psycopg2://" + url[len("postgresql://") :]

    # Neon exige TLS; remove channel_binding (pode quebrar em alguns psycopg2).
    parsed = urlparse(url)
    if "neon.tech" in (parsed.hostname or ""):
        query = dict(parse_qsl(parsed.query, keep_blank_values=True))
        query.pop("channel_binding", None)
        query["sslmode"] = query.get("sslmode") or "require"
        url = urlunparse(parsed._replace(query=urlencode(query)))
    return url


def get_database_url() -> str:
    env_url = os.getenv("DATABASE_URL")
    if env_url:
        return _normalize_database_url(env_url)
    return "postgresql+psycopg2://postgres:1234@localhost:5432/sigein"


SQLALCHEMY_DATABASE_URL = get_database_url()

_engine_kwargs = {"pool_pre_ping": True}
if os.getenv("VERCEL") == "1":
    # Serverless: sem pool persistente entre invocações
    _engine_kwargs["poolclass"] = NullPool
else:
    _engine_kwargs["pool_recycle"] = 280

engine = create_engine(SQLALCHEMY_DATABASE_URL, **_engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
