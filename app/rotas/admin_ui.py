from datetime import datetime, timedelta, timezone
import asyncio
import uuid
import os

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import desc, func, select, text, union_all
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import obter_sessao_banco
from app.models.modelos import (
    Aplicacao,
    AuditoriaRequisicao,
    ChaveAPI,
    ModeloEmbedding,
    Colecao,
    Embedding512,
    Embedding768,
    Embedding1024,
    Embedding1536,
    EmbeddingHalfVec3072,
)
from app.rotas.dependencias import verificar_admin_master
from app.schemas.schemas import AtualizarColecaoSchema, CriarColecaoSchema, RespostaColecaoSchema
from app.services import colecao_service, modelo_service
from app.services.inferencia_service import motor_inferencia

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


@router.get("/colecoes")
async def listar_colecoes_admin(
    aplicacao_id: uuid.UUID | None = Query(default=None),
    modelo_embedding_id: str | None = Query(default=None),
    limite: int = Query(default=100, ge=1, le=1000),
    deslocamento: int = Query(default=0, ge=0, le=10000),
    _: bool = Depends(verificar_admin_master),
    sessao: AsyncSession = Depends(obter_sessao_banco),
):
    """Lista coleções de todos os tenants, com modelo, aplicação e total de embeddings."""
    tabelas_embeddings = (
        Embedding512,
        Embedding768,
        Embedding1024,
        Embedding1536,
        EmbeddingHalfVec3072,
    )
    consultas_contagem = [
        select(
            tabela.colecao_id.label("colecao_id"),
            func.count().label("total"),
        ).group_by(tabela.colecao_id)
        for tabela in tabelas_embeddings
    ]
    contagens = union_all(*consultas_contagem).subquery("contagens_embeddings")

    consulta = (
        select(
            Colecao,
            Aplicacao.nome.label("aplicacao_nome"),
            Aplicacao.ativa.label("aplicacao_ativa"),
            ModeloEmbedding.nome.label("modelo_nome"),
            ModeloEmbedding.dimensoes.label("modelo_dimensoes"),
            ModeloEmbedding.metrica_distancia.label("metrica_distancia"),
            func.coalesce(contagens.c.total, 0).label("quantidade_embeddings"),
        )
        .join(Aplicacao, Aplicacao.id == Colecao.aplicacao_id)
        .join(ModeloEmbedding, ModeloEmbedding.id == Colecao.modelo_embedding_id)
        .outerjoin(contagens, contagens.c.colecao_id == Colecao.id)
        .order_by(desc(Colecao.criado_em), Colecao.nome)
    )
    if aplicacao_id:
        consulta = consulta.where(Colecao.aplicacao_id == aplicacao_id)
    if modelo_embedding_id:
        consulta = consulta.where(Colecao.modelo_embedding_id == modelo_embedding_id)

    registros = (
        await sessao.execute(consulta.offset(deslocamento).limit(limite))
    ).all()

    return [
        {
            "id": str(registro.Colecao.id),
            "nome": registro.Colecao.nome,
            "aplicacao_id": str(registro.Colecao.aplicacao_id),
            "aplicacao_nome": registro.aplicacao_nome,
            "aplicacao_ativa": registro.aplicacao_ativa,
            "modelo_embedding_id": registro.Colecao.modelo_embedding_id,
            "modelo_nome": registro.modelo_nome,
            "modelo_dimensoes": registro.modelo_dimensoes,
            "metrica_distancia": registro.metrica_distancia.value,
            "tipo_armazenamento": registro.Colecao.tipo_armazenamento.value,
            "quantidade_embeddings": int(registro.quantidade_embeddings),
            "publica": registro.Colecao.publica,
            "criado_em": registro.Colecao.criado_em.isoformat(),
        }
        for registro in registros
    ]


@router.post(
    "/colecoes",
    response_model=RespostaColecaoSchema,
    status_code=status.HTTP_201_CREATED,
)
async def criar_colecao_admin(
    dados: CriarColecaoSchema,
    _: bool = Depends(verificar_admin_master),
    sessao: AsyncSession = Depends(obter_sessao_banco),
):
    """Cria uma coleção para a aplicação escolhida pelo administrador."""
    try:
        return await colecao_service.criar_colecao(sessao, dados)
    except ValueError as erro:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(erro),
        ) from erro


@router.patch(
    "/colecoes/{colecao_id}",
    response_model=RespostaColecaoSchema,
    status_code=status.HTTP_200_OK,
)
async def atualizar_colecao_admin(
    colecao_id: uuid.UUID,
    dados: AtualizarColecaoSchema,
    _: bool = Depends(verificar_admin_master),
    sessao: AsyncSession = Depends(obter_sessao_banco),
):
    """Atualiza uma coleção de qualquer aplicação."""

    try:
        colecao = await colecao_service.atualizar_colecao_admin(
            sessao=sessao,
            colecao_id=colecao_id,
            dados=dados,
        )

        if not colecao:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Coleção não encontrada.",
            )

        return colecao

    except ValueError as erro:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(erro),
        ) from erro


@router.delete("/colecoes/{colecao_id}", status_code=status.HTTP_200_OK)
async def excluir_colecao_admin(
    colecao_id: uuid.UUID,
    _: bool = Depends(verificar_admin_master),
    sessao: AsyncSession = Depends(obter_sessao_banco),
):
    """Remove uma coleção de qualquer aplicação. A exclusão também remove seus embeddings."""
    removida = await colecao_service.remover_colecao_admin(sessao, colecao_id)
    if not removida:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Coleção não encontrada.",
        )
    return {"mensagem": "Coleção e embeddings vinculados removidos com sucesso."}


TEMPO_LIMITE_VERIFICACAO_SEGUNDOS = 2


@router.get("/health")
async def obter_status_infraestrutura(
    _: bool = Depends(verificar_admin_master),
    sessao: AsyncSession = Depends(obter_sessao_banco),
):
    """Retorna o estado atual dos componentes da infraestrutura."""

    # Estado do motor de inferência, sem carregar modelos.
    status_motor = motor_inferencia.obter_status()

    # Verifica a conectividade com o PostgreSQL.
    try:
        await asyncio.wait_for(
            sessao.execute(text("SELECT 1")),
            timeout=TEMPO_LIMITE_VERIFICACAO_SEGUNDOS,
        )

        status_banco = "operacional"

    except (SQLAlchemyError, TimeoutError):
        status_banco = "indisponivel"

    # Consulta os modelos somente se o banco estiver disponível.
    if status_banco == "operacional":
        try:
            status_modelos = await modelo_service.obter_status_modelos(
                sessao=sessao
            )
        except SQLAlchemyError:
            status_banco = "indisponivel"
            status_modelos = None
    else:
        status_modelos = None

    status_geral = (
        "operacional"
        if status_banco == "operacional"
        else "degradado"
    )

    resposta = {
        "status": status_geral,
        "api": {
            "status": "operacional",
        },
        "banco": {
            "status": status_banco,
        },
        "inferencia": status_motor,
        "modelos": status_modelos,
    }

    codigo_http = (
        status.HTTP_200_OK
        if status_geral == "operacional"
        else status.HTTP_503_SERVICE_UNAVAILABLE
    )

    return JSONResponse(
        status_code=codigo_http,
        content=resposta,
    )