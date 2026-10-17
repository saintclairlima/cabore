

from typing import List
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import obter_sessao_banco
from app.models.modelos import Aplicacao
from app.rotas.dependencias import obter_aplicacao_atual
from app.schemas.schemas import AtualizarColecaoSchema, CriarColecaoPayloadSchema, CriarColecaoSchema, RespostaColecaoSchema
from app.services import colecao_service


router = APIRouter(prefix="/colecoes", tags=["Coleções"])

@router.post("/", response_model=RespostaColecaoSchema, status_code=status.HTTP_201_CREATED)
async def criar_colecao_route(
    dados: CriarColecaoPayloadSchema,
    aplicacao: Aplicacao = Depends(obter_aplicacao_atual),
    sessao: AsyncSession = Depends(obter_sessao_banco),
):
    """Cria uma nova coleção vinculada à aplicação autenticada."""
    # Garante que a coleção está sendo criada para o próprio tenant autenticado
    try:
        dados_completos = CriarColecaoSchema(
            aplicacao_id=aplicacao.id,
            **dados.model_dump()
        )

        colecao = await colecao_service.criar_colecao(sessao, dados_completos)
        return colecao
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/", response_model=List[RespostaColecaoSchema], status_code=status.HTTP_200_OK)
async def listar_colecoes_route(
    limite: int = Query(default=50, ge=1, le=1000),
    deslocamento: int = Query(default=0, ge=0, le=10000),
    aplicacao: Aplicacao = Depends(obter_aplicacao_atual),
    sessao: AsyncSession = Depends(obter_sessao_banco),
):
    """Lista todas as coleções pertencentes à aplicação autenticada."""
    colecoes = await colecao_service.listar_colecoes(
        sessao, aplicacao_id=aplicacao.id, limite=limite, deslocamento=deslocamento
    )

    return colecoes


@router.patch("/{colecao_id}", response_model=RespostaColecaoSchema, status_code=status.HTTP_200_OK)
async def atualizar_colecao_route(
    colecao_id: uuid.UUID,
    dados: AtualizarColecaoSchema,
    aplicacao: Aplicacao = Depends(obter_aplicacao_atual),
    sessao: AsyncSession = Depends(obter_sessao_banco),
):
    """Atualiza metadados ou visibilidade de uma coleção do tenant autenticado."""
    colecao = await colecao_service.atualizar_colecao(
        sessao=sessao,
        colecao_id=colecao_id,
        aplicacao_id=aplicacao.id,
        dados=dados,
    )
    if not colecao:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Coleção não encontrada ou acesso negado.")
    
    return colecao


@router.delete("/{colecao_id}", status_code=status.HTTP_200_OK)
async def remover_colecao_route(
    colecao_id: uuid.UUID,
    aplicacao: Aplicacao = Depends(obter_aplicacao_atual),
    sessao: AsyncSession = Depends(obter_sessao_banco),
):
    """Remove uma coleção e todos os seus vetores vinculados (Hard Delete com Cascade)."""
    removido = await colecao_service.remover_colecao(
        sessao=sessao,
        colecao_id=colecao_id,
        aplicacao_id=aplicacao.id,
    )
    if not removido:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Coleção não encontrada ou acesso negado.")
    
    return {"mensagem": "Coleção e todos os seus embeddings vinculados foram removidos com sucesso."}