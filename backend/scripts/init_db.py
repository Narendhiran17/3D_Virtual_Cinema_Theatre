import asyncio
from app.core.database import engine
from app.models import Base


async def init_database():
    async with engine.begin() as conn:
        print("Initializing database schema from SQLAlchemy models...")
        await conn.run_sync(Base.metadata.create_all)
        print("PostgreSQL tables successfully verified and initialized.")


if __name__ == "__main__":
    asyncio.run(init_database())
