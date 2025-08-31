import enum
import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    String,
    Text,
    Boolean,
    DateTime,
    Integer,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy import JSON
from .db import Base

class Platform(Base):
    __tablename__ = "platforms"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)


class Resource(Base):
    __tablename__ = "resources"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    slug = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)


class ResourceShopID(Base):
    __tablename__ = "resource_shop_ids"
    resource_id = Column(String(36), ForeignKey("resources.id", ondelete="CASCADE"), primary_key=True)
    platform_id = Column(Integer, ForeignKey("platforms.id", ondelete="CASCADE"), primary_key=True)
    external_resource_id = Column(String, nullable=False)


class User(Base):
    __tablename__ = "users"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    platform_id = Column(Integer, ForeignKey("platforms.id"), nullable=False)
    external_user_id = Column(String, nullable=False)
    username = Column(String)
    # Optional Discord ID; can be set later. Must be unique per platform when present.
    discord_id = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    __table_args__ = (
        UniqueConstraint("platform_id", "external_user_id", name="uq_user_platform_external"),
        UniqueConstraint("platform_id", "discord_id", name="uq_user_platform_discord"),
    )


class Purchase(Base):
    __tablename__ = "purchases"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    resource_id = Column(String(36), ForeignKey("resources.id"), nullable=False)
    platform_id = Column(Integer, ForeignKey("platforms.id"), nullable=False)
    verified_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    # A user can only be verified once for a given resource per platform.
    __table_args__ = (UniqueConstraint("platform_id", "user_id", "resource_id", name="uq_purchase_unique"),)


class APIKey(Base):
    __tablename__ = "api_keys"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String)
    hash = Column(Text, nullable=False)
    method = Column(String, nullable=False, default="pbkdf2_sha256")
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    last_used_at = Column(DateTime(timezone=True))
    scopes = Column(JSON)
