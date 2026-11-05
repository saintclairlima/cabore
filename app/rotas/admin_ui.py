from datetime import datetime, timedelta, timezone
import os

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import obter_sessao_banco
from app.models.modelos import (
    Aplicacao,
    AuditoriaRequisicao,
    ChaveAPI,
    ModeloEmbedding,
)
from app.rotas.dependencias import verificar_admin_master

router = APIRouter(prefix="/admin", tags=["Painel Administrativo"])

# Define o caminho absoluto para o arquivo HTML com base na localização deste arquivo Python
CAMINHO_TEMPLATE = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "templates", "admin.html")
)

@router.get("/", response_class=FileResponse)
async def painel_admin():
    """Retorna o arquivo HTML estático do painel administrativo."""
    if not os.path.exists(CAMINHO_TEMPLATE):
        return {"erro": "Arquivo de template admin.html não encontrado."}, 404
        
    return FileResponse(CAMINHO_TEMPLATE)


@router.get("/analytics")
async def obter_analytics_admin(
    dias: int = Query(default=30, ge=7, le=90),
    _: bool = Depends(verificar_admin_master),
    sessao: AsyncSession = Depends(obter_sessao_banco),
):
    """Retorna métricas agregadas e eventos recentes da auditoria para o painel."""
    agora = datetime.now(timezone.utc)
    inicio = agora - timedelta(days=dias)
    hoje = agora.replace(hour=0, minute=0, second=0, microsecond=0)

    resumo = (
        await sessao.execute(
            select(
                func.count(AuditoriaRequisicao.id),
                func.avg(AuditoriaRequisicao.tempo_execucao_ms),
                func.percentile_cont(0.95).within_group(
                    AuditoriaRequisicao.tempo_execucao_ms
                ),
                func.coalesce(func.sum(AuditoriaRequisicao.quantidade_resultados), 0),
            ).where(AuditoriaRequisicao.criado_em >= inicio)
        )
    ).one()
    requisicoes_hoje = await sessao.scalar(
        select(func.count(AuditoriaRequisicao.id)).where(
            AuditoriaRequisicao.criado_em >= hoje
        )
    )
    aplicacoes_ativas = await sessao.scalar(
        select(func.count(Aplicacao.id)).where(Aplicacao.ativa.is_(True))
    )
    chaves_ativas = await sessao.scalar(
        select(func.count(ChaveAPI.id)).where(ChaveAPI.revogada.is_(False))
    )
    modelos_ativos = await sessao.scalar(
        select(func.count(ModeloEmbedding.id)).where(ModeloEmbedding.ativo.is_(True))
    )

    dia = func.date_trunc(
        "day", func.timezone("UTC", AuditoriaRequisicao.criado_em)
    )
    resultados_por_dia = (
        await sessao.execute(
            select(
                dia.label("dia"),
                func.count(AuditoriaRequisicao.id).label("requisicoes"),
                func.avg(AuditoriaRequisicao.tempo_execucao_ms).label("latencia_media"),
            )
            .where(AuditoriaRequisicao.criado_em >= inicio)
            .group_by(dia)
            .order_by(dia)
        )
    ).all()
    operacoes = (
        await sessao.execute(
            select(
                AuditoriaRequisicao.operacao,
                func.count(AuditoriaRequisicao.id).label("total"),
            )
            .where(AuditoriaRequisicao.criado_em >= inicio)
            .group_by(AuditoriaRequisicao.operacao)
            .order_by(desc("total"))
        )
    ).all()
    aplicacoes_top = (
        await sessao.execute(
            select(
                Aplicacao.id,
                Aplicacao.nome,
                func.count(AuditoriaRequisicao.id).label("requisicoes"),
            )
            .select_from(AuditoriaRequisicao)
            .outerjoin(
                Aplicacao,
                AuditoriaRequisicao.aplicacao_id == Aplicacao.id,
            )
            .where(AuditoriaRequisicao.criado_em >= inicio)
            .group_by(Aplicacao.id, Aplicacao.nome)
            .order_by(desc("requisicoes"))
            .limit(5)
        )
    ).all()
    recentes = (
        await sessao.execute(
            select(
                AuditoriaRequisicao.id,
                AuditoriaRequisicao.aplicacao_id,
                Aplicacao.nome.label("aplicacao_nome"),
                AuditoriaRequisicao.colecao_id,
                AuditoriaRequisicao.operacao,
                AuditoriaRequisicao.tempo_execucao_ms,
                AuditoriaRequisicao.quantidade_resultados,
                AuditoriaRequisicao.criado_em,
            )
            .outerjoin(
                Aplicacao,
                AuditoriaRequisicao.aplicacao_id == Aplicacao.id,
            )
            .order_by(desc(AuditoriaRequisicao.criado_em))
            .limit(15)
        )
    ).all()

    return {
        "periodo_dias": dias,
        "metricas": {
            "requisicoes": resumo[0],
            "requisicoes_hoje": requisicoes_hoje or 0,
            "latencia_media_ms": float(resumo[1] or 0),
            "latencia_p95_ms": float(resumo[2] or 0),
            "resultados": resumo[3],
            "aplicacoes_ativas": aplicacoes_ativas or 0,
            "chaves_ativas": chaves_ativas or 0,
            "modelos_ativos": modelos_ativos or 0,
        },
        "serie_diaria": [
            {
                "dia": registro.dia.date().isoformat(),
                "requisicoes": registro.requisicoes,
                "latencia_media_ms": float(registro.latencia_media or 0),
            }
            for registro in resultados_por_dia
        ],
        "operacoes": [
            {"nome": registro.operacao, "total": registro.total}
            for registro in operacoes
        ],
        "aplicacoes_top": [
            {
                "id": str(registro.id) if registro.id else None,
                "nome": registro.nome or "Aplicação removida",
                "requisicoes": registro.requisicoes,
            }
            for registro in aplicacoes_top
        ],
        "recentes": [
            {
                "id": registro.id,
                "aplicacao_id": str(registro.aplicacao_id)
                if registro.aplicacao_id
                else None,
                "aplicacao_nome": registro.aplicacao_nome or "Aplicação removida",
                "colecao_id": str(registro.colecao_id) if registro.colecao_id else None,
                "operacao": registro.operacao,
                "tempo_execucao_ms": float(registro.tempo_execucao_ms),
                "quantidade_resultados": registro.quantidade_resultados,
                "criado_em": registro.criado_em.isoformat(),
            }
            for registro in recentes
        ],
    }
