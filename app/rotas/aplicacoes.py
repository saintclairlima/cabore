from typing import List
import uuid

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import obter_sessao_banco
from app.rotas.dependencias import verificar_admin_master
from app.schemas.schemas import CriarAplicacaoSchema, CriarChaveAPISchema, RespostaAplicacaoSchema, RespostaChaveAPISchema, RespostaCriacaoChaveSchema
from app.services import aplicacao_service


router = APIRouter(prefix="/aplicacoes", tags=["Aplicações e Tenants (Admin)"])

@router.post("/", response_model=RespostaAplicacaoSchema, status_code=status.HTTP_201_CREATED)
async def criar_aplicacao_route(
    dados: CriarAplicacaoSchema,
    _: bool = Depends(verificar_admin_master),
    sessao: AsyncSession = Depends(obter_sessao_banco)
):
    """Cadastra uma nova aplicação (tenant) no sistema."""
    try:
        aplicacao = await aplicacao_service.criar_aplicacao(sessao, dados)
        return aplicacao
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/chaves",
    response_model=RespostaCriacaoChaveSchema,
    status_code=status.HTTP_201_CREATED,
    responses={status.HTTP_409_CONFLICT: {"description": "O nome da chave já existe nesta aplicação."}},
)
async def criar_chave_api_route(
    dados: CriarChaveAPISchema,
    _: bool = Depends(verificar_admin_master),
    sessao: AsyncSession = Depends(obter_sessao_banco)
):
    """Gera uma nova chave de API para uma aplicação."""
    try:
        chave_obj, chave_plana = await aplicacao_service.criar_chave_api(sessao, dados)
        return {
            "id": chave_obj.id,
            "aplicacao_id": chave_obj.aplicacao_id,
            "nome": chave_obj.nome,
            "revogada": chave_obj.revogada,
            "criado_em": chave_obj.criado_em,
            "chave_api": chave_plana,
        }
    except aplicacao_service.NomeChaveAPIJaExisteError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{aplicacao_id}/chaves", response_model=List[RespostaChaveAPISchema], status_code=status.HTTP_200_OK)
async def listar_chaves_route(
    aplicacao_id: uuid.UUID = Path(..., description="UUID da aplicação para listar as chaves"),
    _: bool = Depends(verificar_admin_master),
    sessao: AsyncSession = Depends(obter_sessao_banco)
):
    """Lista as chaves de API cadastradas para uma aplicação."""
    chaves = await aplicacao_service.listar_chaves_por_aplicacao(sessao, aplicacao_id)
    return chaves


@router.patch("/chaves/{chave_id}/revogar", status_code=status.HTTP_200_OK)
async def revogar_chave_route(
    chave_id: uuid.UUID,
    _: bool = Depends(verificar_admin_master),
    sessao: AsyncSession = Depends(obter_sessao_banco)
):
    """Revoga uma chave de API, impedindo imediatamente o seu uso."""
    sucesso = await aplicacao_service.revogar_chave_api(sessao, chave_id)
    if not sucesso:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chave de API não encontrada.")
    return {"mensagem": "Chave de API revogada com sucesso."}


@router.patch("/{aplicacao_id}", response_model=RespostaAplicacaoSchema, status_code=status.HTTP_200_OK)
async def atualizar_aplicacao_route(
    aplicacao_id: uuid.UUID,
    dados: CriarAplicacaoSchema,
    _: bool = Depends(verificar_admin_master),
    sessao: AsyncSession = Depends(obter_sessao_banco)
):
    """Atualiza os dados cadastrais de uma aplicação."""
    try:
        aplicacao = await aplicacao_service.atualizar_aplicacao(sessao, aplicacao_id, dados.nome)
        if not aplicacao:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Aplicação não encontrada.")
        return aplicacao
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{aplicacao_id}", status_code=status.HTTP_200_OK)
async def remover_aplicacao_route(
    aplicacao_id: uuid.UUID,
    _: bool = Depends(verificar_admin_master),
    sessao: AsyncSession = Depends(obter_sessao_banco)
):
    """Remove uma aplicação e todos os seus recursos associados (Cascade)."""
    removido = await aplicacao_service.remover_aplicacao(sessao, aplicacao_id)
    if not removido:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Aplicação não encontrada.")
    return {"mensagem": "Aplicação e todos os seus dados vinculados foram removidos com sucesso."}