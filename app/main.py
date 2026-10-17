import asyncio
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.database import motor_banco
from app.rotas.v1 import router as router_v1

logger = logging.getLogger(__name__)
TEMPO_LIMITE_PRONTIDAO_SEGUNDOS = 2

app = FastAPI(
    title="Caboré API - Mecanismo de Busca Vetorial e Recomendação",
    version="0.1.0"
)

app.include_router(router_v1)


@app.exception_handler(RequestValidationError)
async def tratar_erro_validacao_requisicao(
    _requisicao: Request, erro: RequestValidationError
) -> JSONResponse:
    detalhes = [
        {
            "loc": detalhe.get("loc", ()),
            "msg": "O valor enviado é inválido.",
            "type": detalhe.get("type", "value_error"),
        }
        for detalhe in erro.errors()
    ]
    return JSONResponse(status_code=422, content={"detail": detalhes})


@app.get("/status")
async def verificar_status():
    """Informa se o processo está ativo, sem consultar dependências externas."""
    return {"status": "operacional", "servico": "cabore"}


@app.get("/ready")
async def verificar_prontidao() -> JSONResponse:
    """Verifica a conectividade com o banco antes de receber tráfego."""
    try:
        await asyncio.wait_for(_verificar_conexao_banco(), timeout=TEMPO_LIMITE_PRONTIDAO_SEGUNDOS)
    except (SQLAlchemyError, TimeoutError):
        logger.warning("Verificação de prontidão falhou ao consultar o banco.", exc_info=True)
        return JSONResponse(
            status_code=503,
            content={
                "status": "indisponivel",
                "dependencias": {"banco": "indisponivel"},
            },
        )

    return JSONResponse(
        status_code=200,
        content={"status": "pronto", "dependencias": {"banco": "operacional"}},
    )


async def _verificar_conexao_banco() -> None:
    async with motor_banco.connect() as conexao:
        await conexao.execute(text("SELECT 1"))