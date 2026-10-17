from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from app.config import configuracoes

motor_banco = create_async_engine(
    configuracoes.DATABASE_URL.get_secret_value(),
    echo=configuracoes.AMBIENTE == "desenvolvimento",
    hide_parameters=True,
)

SessaoAssincronaLocal = async_sessionmaker(
    bind=motor_banco,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)

class Base(DeclarativeBase):
    pass

async def obter_sessao_banco() -> AsyncGenerator[AsyncSession, None]:
    async with SessaoAssincronaLocal() as sessao:
        yield sessao