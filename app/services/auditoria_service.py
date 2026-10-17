import logging
import uuid
from typing import List, Optional
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.database import SessaoAssincronaLocal
from app.models.modelos import AuditoriaRequisicao

logger = logging.getLogger(__name__)


async def registrar_auditoria(
    sessao: AsyncSession,
    aplicacao_id: uuid.UUID,
    operacao: str,
    tempo_execucao_ms: float,
    quantidade_resultados: int = 0,
    colecao_id: Optional[uuid.UUID] = None,
    chave_api_id: Optional[uuid.UUID] = None,
) -> AuditoriaRequisicao:
    """
    Registra uma nova requisição na tabela de auditoria do sistema.
    """
    novo_registro = AuditoriaRequisicao(
        aplicacao_id=aplicacao_id,
        colecao_id=colecao_id,
        chave_api_id=chave_api_id,
        operacao=operacao.strip(),
        tempo_execucao_ms=tempo_execucao_ms,
        quantidade_resultados=quantidade_resultados,
    )
    
    sessao.add(novo_registro)
    await sessao.commit()
    return novo_registro


async def registrar_auditoria_em_background(
    aplicacao_id: uuid.UUID,
    operacao: str,
    tempo_execucao_ms: float,
    quantidade_resultados: int = 0,
    colecao_id: Optional[uuid.UUID] = None,
    chave_api_id: Optional[uuid.UUID] = None,
) -> None:
    """Registra telemetria após a resposta, sem afetar a operação principal."""
    try:
        async with SessaoAssincronaLocal() as sessao:
            await registrar_auditoria(
                sessao=sessao,
                aplicacao_id=aplicacao_id,
                operacao=operacao,
                tempo_execucao_ms=tempo_execucao_ms,
                quantidade_resultados=quantidade_resultados,
                colecao_id=colecao_id,
                chave_api_id=chave_api_id,
            )
    except SQLAlchemyError:
        logger.exception(
            "Falha ao registrar telemetria de auditoria "
            "(aplicacao_id=%s, operacao=%s, colecao_id=%s)",
            aplicacao_id,
            operacao,
            colecao_id,
        )


async def listar_auditorias_por_aplicacao(
    sessao: AsyncSession,
    aplicacao_id: uuid.UUID,
    limite: int = 50,
    deslocamento: int = 0
) -> List[AuditoriaRequisicao]:
    """
    Lista os logs de auditoria de uma aplicação específica, ordenados dos mais recentes para os mais antigos.
    """
    stmt = (
        select(AuditoriaRequisicao)
        .where(AuditoriaRequisicao.aplicacao_id == aplicacao_id)
        .order_by(desc(AuditoriaRequisicao.criado_em))
        .offset(deslocamento)
        .limit(limite)
    )
    
    resultado = await sessao.execute(stmt)
    return list(resultado.scalars().all())