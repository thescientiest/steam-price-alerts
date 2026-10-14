from contextlib import contextmanager
from typing import Generator, List, Optional
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from config import DATABASE_URL
from models import Base, GuildSetting, TrackedGame

# For SQLite, enable check_same_thread=False
connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(DATABASE_URL, connect_args=connect_args, echo=False)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db() -> None:
    """Creates database tables if they do not exist."""
    Base.metadata.create_all(bind=engine)


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """Context manager for database sessions with automatic commit / rollback."""
    session: Session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def set_guild_channel(guild_id: int, channel_id: int) -> None:
    with get_db_session() as session:
        setting = session.get(GuildSetting, guild_id)
        if setting:
            setting.default_channel_id = channel_id
        else:
            setting = GuildSetting(guild_id=guild_id, default_channel_id=channel_id)
            session.add(setting)


def get_guild_channel(guild_id: int) -> Optional[int]:
    with get_db_session() as session:
        setting = session.get(GuildSetting, guild_id)
        return setting.default_channel_id if setting else None


def add_or_update_tracked_game(
    guild_id: int,
    app_id: int,
    game_name: str,
    channel_id: Optional[int] = None,
    header_image: Optional[str] = None,
    min_discount: int = 0,
    target_price: Optional[float] = None,
    added_by_user_id: Optional[int] = None,
    current_discount: int = 0,
    current_final_price: Optional[str] = None,
    is_on_sale: bool = False,
) -> TrackedGame:
    with get_db_session() as session:
        stmt = select(TrackedGame).where(
            TrackedGame.guild_id == guild_id, TrackedGame.app_id == app_id
        )
        game = session.execute(stmt).scalar_one_or_none()

        if game:
            game.game_name = game_name
            if channel_id is not None:
                game.channel_id = channel_id
            if header_image is not None:
                game.header_image = header_image
            game.min_discount = min_discount
            game.target_price = target_price
            game.last_discount = current_discount
            game.last_final_price = current_final_price
            game.is_on_sale = is_on_sale
        else:
            game = TrackedGame(
                guild_id=guild_id,
                channel_id=channel_id,
                app_id=app_id,
                game_name=game_name,
                header_image=header_image,
                min_discount=min_discount,
                target_price=target_price,
                last_discount=current_discount,
                last_final_price=current_final_price,
                is_on_sale=is_on_sale,
                added_by_user_id=added_by_user_id,
            )
            session.add(game)

        session.flush()
        # Detach object attributes for safe return
        session.refresh(game)
        return game


def remove_tracked_game(guild_id: int, app_id: int) -> bool:
    with get_db_session() as session:
        stmt = select(TrackedGame).where(
            TrackedGame.guild_id == guild_id, TrackedGame.app_id == app_id
        )
        game = session.execute(stmt).scalar_one_or_none()
        if game:
            session.delete(game)
            return True
        return False


def get_guild_tracked_games(guild_id: int) -> List[TrackedGame]:
    with get_db_session() as session:
        stmt = select(TrackedGame).where(TrackedGame.guild_id == guild_id).order_by(TrackedGame.game_name)
        return list(session.execute(stmt).scalars().all())


def get_all_tracked_games() -> List[TrackedGame]:
    with get_db_session() as session:
        stmt = select(TrackedGame)
        return list(session.execute(stmt).scalars().all())


def get_unique_app_ids() -> List[int]:
    with get_db_session() as session:
        stmt = select(TrackedGame.app_id).distinct()
        return list(session.execute(stmt).scalars().all())


def update_game_sale_state(
    game_id: int,
    is_on_sale: bool,
    last_discount: int,
    last_final_price: Optional[str],
) -> None:
    with get_db_session() as session:
        game = session.get(TrackedGame, game_id)
        if game:
            game.is_on_sale = is_on_sale
            game.last_discount = last_discount
            game.last_final_price = last_final_price
