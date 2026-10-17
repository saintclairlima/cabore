

import time
from typing import List
import uuid

from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import obter_sessao_banco
from app.limites import LIMITE_MAXIMO_ITENS_LOTE
from app.models.modelos import Aplicacao
from app.rotas.dependencias import obter_aplicacao_atual
from app.schemas.schemas import InserirEmbeddingSchema, RemoverEmbeddingSchema, RequisicaoBuscaSchema
from app.services import auditoria_service, busca_service, colecao_service, embedding_service


router = APIRouter(prefix="/embeddings", tags=["Embeddings e busca"])

@router.post("/", status_code=status.HTTP_201_CREATED)
async def inserir_embedding_route(
    dados: InserirEmbeddingSchema,
    tarefas: BackgroundTasks,
    aplicacao: Aplicacao = Depends(obter_aplicacao_atual),
    sessao: AsyncSession = Depends(obter_sessao_banco),
):
    """Insere um embedding individual com comportamento get-or-create por hash."""
    inicio = time.perf_counter()
    try:
        # Valida se a coleção pertence à aplicação autenticada
        colecao = await colecao_service.obter_colecao_por_id(sessao, dados.colecao_id, aplicacao_id=aplicacao.id)
        if not colecao:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Coleção não encontrada ou acesso negado.")

        registro = await embedding_service.inserir_embedding(sessao, dados)
        
        tempo_ms = round((time.perf_counter() - inicio) * 1000, 2)
        tarefas.add_task(
            auditoria_service.registrar_auditoria_em_background,
            aplicacao.id,
            "inserir_embedding",
            tempo_ms,
            quantidade_resultados=1,
            colecao_id=dados.colecao_id,
        )

        return {
            "id": str(registro.id),
            "colecao_id": str(registro.colecao_id),
            "conteudo_hash": registro.conteudo_hash,
            "metadados": registro.metadados,
            "criado_em": registro.criado_em,
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/lote", status_code=status.HTTP_201_CREATED)
async def inserir_embeddings_lote_route(
    colecao_id: uuid.UUID,
    tarefas: BackgroundTasks,
    lista_dados: List[InserirEmbeddingSchema] = Body(
        ..., min_length=1, max_length=LIMITE_MAXIMO_ITENS_LOTE
    ),
    aplicacao: Aplicacao = Depends(obter_aplicacao_atual),
    sessao: AsyncSession = Depends(obter_sessao_banco),
):
    """Insere múltiplos embeddings em lote para uma coleção da aplicação."""
    inicio = time.perf_counter()
    try:
        colecao = await colecao_service.obter_colecao_por_id(sessao, colecao_id, aplicacao_id=aplicacao.id)
        if not colecao:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Coleção não encontrada ou acesso negado.")

        registros = await embedding_service.inserir_embeddings_lote(sessao, colecao_id, lista_dados)
        
        tempo_ms = round((time.perf_counter() - inicio) * 1000, 2)
        tarefas.add_task(
            auditoria_service.registrar_auditoria_em_background,
            aplicacao.id,
            "inserir_embeddings_lote",
            tempo_ms,
            quantidade_resultados=len(registros),
            colecao_id=colecao_id,
        )

        return [
            {
                "id": str(r.id),
                "colecao_id": str(r.colecao_id),
                "conteudo_hash": r.conteudo_hash,
                "metadados": r.metadados,
            }
            for r in registros
        ]
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/buscar")
async def buscar_embeddings_route(
    parametros_busca: RequisicaoBuscaSchema,
    tarefas: BackgroundTasks,
    aplicacao: Aplicacao = Depends(obter_aplicacao_atual),
    sessao: AsyncSession = Depends(obter_sessao_banco),
):
    """
    Realiza busca semântica global/multi-coleções suportando modelos de dimensões mistas,
    filtragem por metadados JSONB e isolamento estrito por tenant.
    """
    inicio = time.perf_counter()
    try:
        resultados = await busca_service.buscar_similaridade(
            sessao=sessao,
            nomes_ou_ids_colecoes=parametros_busca.colecoes_nomes_ou_ids,
            texto_consulta=parametros_busca.texto_consulta,
            limite=parametros_busca.limite,
            filtro_metadados=parametros_busca.filtro_metadados,
            aplicacao_id=aplicacao.id,
        )

        tempo_ms = round((time.perf_counter() - inicio) * 1000, 2)
        tarefas.add_task(
            auditoria_service.registrar_auditoria_em_background,
            aplicacao.id,
            "buscar_similaridade",
            tempo_ms,
            quantidade_resultados=len(resultados),
        )

        return resultados
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{embedding_id}")
async def remover_embedding_route(
    embedding_id: uuid.UUID,
    dados_remocao: RemoverEmbeddingSchema,
    aplicacao: Aplicacao = Depends(obter_aplicacao_atual),
    sessao: AsyncSession = Depends(obter_sessao_banco),
):
    """Remove um embedding específico pertencente a uma coleção da aplicação."""
    colecao = await colecao_service.obter_colecao_por_id(sessao, dados_remocao.colecao_id, aplicacao_id=aplicacao.id)
    if not colecao:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Coleção não encontrada ou acesso negado.")

    removido = await embedding_service.remover_embedding(
        sessao, embedding_id, dados_remocao.colecao_id
    )
    if not removido:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Embedding não encontrado.")

    return {"mensagem": "Embedding removido com sucesso."}