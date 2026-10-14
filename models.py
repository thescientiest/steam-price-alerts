from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import BigInteger, Boolean, DateTime, Float, Integer, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class TrackedGame(Base):
    __tablename__ = "tracked_games"
    __table_args__ = (
        UniqueConstraint("guild_id", "app_id", name="uq_guild_app"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    channel_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    app_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    game_name: Mapped[str] = mapped_column(String(255), nullable=False)
    header_image: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    # Thresholds:
    # min_discount: Alert if discount % >= this value (e.g. 50 for >= 50% off)
    min_discount: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # target_price: Alert if current price drops below or equal to this (in dollars/currency units)
    target_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Historical state tracking (to prevent duplicate alert spam):
    last_discount: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_final_price: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    is_on_sale: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    added_by_user_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class GuildSetting(Base):
    __tablename__ = "guild_settings"

    guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    default_channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
