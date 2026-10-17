from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.models.modelos import ModeloEmbedding
from app.schemas.schemas import AtualizarModeloEmbeddingSchema, CriarModeloEmbeddingSchema


async def criar_modelo_embedding(
    sessao: AsyncSession, dados: CriarModeloEmbeddingSchema
) -> ModeloEmbedding:
    """Cadastra um novo modelo de embedding no sistema."""
    
    # 1. Valida se já existe um modelo com o mesmo ID exato
    existente = await obter_modelo_por_id(sessao, dados.id)
    if existente:
        raise ValueError(f"Já existe um modelo de embedding cadastrado com o ID '{dados.id}'.")

    # 2. Persiste o novo modelo
    novo_modelo = ModeloEmbedding(
        id=dados.id.strip(),
        nome=dados.nome.strip(),
        provedor=dados.provedor.strip(),
        dimensoes=dados.dimensoes,
        identificador_repositorio=dados.identificador_repositorio.strip() if dados.identificador_repositorio else None,
        metrica_distancia=dados.metrica_distancia,
    )
    
    sessao.add(novo_modelo)
    await sessao.commit()
    await sessao.refresh(novo_modelo)
    return novo_modelo


async def obter_modelo_por_id(sessao: AsyncSession, modelo_id: str) -> ModeloEmbedding:
    """Busca um modelo de embedding pelo seu ID."""
    resultado = await sessao.execute(
        select(ModeloEmbedding).where(ModeloEmbedding.id == modelo_id)
    )
    modelo = resultado.scalar_one_or_none()
    if not modelo:
        raise ValueError(f"Modelo de embedding com ID '{modelo_id}' não encontrado.")
    return modelo


async def listar_modelos_embedding(
    sessao: AsyncSession, limite: int = 50, deslocamento: int = 0
) -> List[ModeloEmbedding]:
    """Lista todos os modelos de embedding suportados pelo sistema."""
    resultado = await sessao.execute(
        select(ModeloEmbedding).offset(deslocamento).limit(limite)
    )
    return list(resultado.scalars().all())


async def alterar_status_modelo(
    sessao: AsyncSession, modelo_id: str, ativo: bool
) -> Optional[ModeloEmbedding]:
    """Ativa ou desativa um modelo de embedding."""
    stmt = (
        update(ModeloEmbedding)
        .where(ModeloEmbedding.id == modelo_id)
        .values(ativo=ativo)
        .returning(ModeloEmbedding)
    )
    resultado = await sessao.execute(stmt)
    await sessao.commit()
    return resultado.scalar_one_or_none()


async def atualizar_modelo_embedding(
    sessao: AsyncSession, modelo_id: str, dados: AtualizarModeloEmbeddingSchema
) -> Optional[ModeloEmbedding]:
    """Atualiza os dados cadastrais permitidos de um modelo de embedding."""
    modelo = await obter_modelo_por_id(sessao, modelo_id)
    if not modelo:
        return None

    # Pega apenas os campos que foram enviados na requisição
    dados_atualizacao = dados.model_dump(exclude_unset=True)

    for campo, valor in dados_atualizacao.items():
        setattr(modelo, campo, valor)

    await sessao.commit()
    await sessao.refresh(modelo)
    return modelo
