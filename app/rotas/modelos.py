from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import obter_sessao_banco
from app.rotas.dependencias import verificar_admin_master
from app.schemas.schemas import AtualizarModeloEmbeddingSchema, CriarModeloEmbeddingSchema, RespostaModeloEmbeddingSchema
from app.services import modelo_service
    

router = APIRouter(prefix="/modelos", tags=["Modelos de Embedding (Admin)"])


@router.get("/", response_model=List[RespostaModeloEmbeddingSchema], status_code=status.HTTP_200_OK)
async def listar_modelos_route(
    limite: int = Query(default=50, ge=1, le=100),
    deslocamento: int = Query(default=0, ge=0, le=10000),
    sessao: AsyncSession = Depends(obter_sessao_banco),
):
    """Lista todos os modelos de embedding disponíveis no sistema."""
    modelos = await modelo_service.listar_modelos_embedding(sessao, limite=limite, deslocamento=deslocamento)
    return modelos


@router.post("/", response_model=RespostaModeloEmbeddingSchema, status_code=status.HTTP_201_CREATED)
async def criar_modelo_route(
    dados: CriarModeloEmbeddingSchema,
    _: bool = Depends(verificar_admin_master),
    sessao: AsyncSession = Depends(obter_sessao_banco),
):
    """Cadastra um novo modelo de embedding no sistema (Apenas Admin)."""
    try:
        modelo = await modelo_service.criar_modelo_embedding(sessao, dados)
        return modelo
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{modelo_id}", response_model=RespostaModeloEmbeddingSchema, status_code=status.HTTP_200_OK)
async def obter_modelo_por_id_route(
    modelo_id: str,
    sessao: AsyncSession = Depends(obter_sessao_banco),
):
    """Consulta os detalhes de um modelo de embedding específico pelo seu ID."""
    modelo = await modelo_service.obter_modelo_por_id(sessao, modelo_id)
    if not modelo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Modelo de embedding não encontrado.")
    return modelo


@router.patch("/{modelo_id}", response_model=RespostaModeloEmbeddingSchema, status_code=status.HTTP_200_OK)
async def atualizar_modelo_route(
    modelo_id: str,
    dados: AtualizarModeloEmbeddingSchema,
    _: bool = Depends(verificar_admin_master),
    sessao: AsyncSession = Depends(obter_sessao_banco),
):
    """Atualiza dados cadastrais de um modelo de embedding (Apenas Admin)."""
    modelo = await modelo_service.atualizar_modelo_embedding(sessao, modelo_id, dados)
    if not modelo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Modelo de embedding não encontrado.")
    return modelo