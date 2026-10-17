import uuid
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete, update

from app.models.modelos import Colecao, ModeloEmbedding, Aplicacao
from app.schemas.schemas import AtualizarColecaoSchema, CriarColecaoSchema


async def _verificar_aplicacao_existe(sessao: AsyncSession, aplicacao_id: uuid.UUID) -> bool:
    """Verifica se a aplicação (tenant) existe."""
    resultado = await sessao.execute(
        select(Aplicacao.id).where(
            Aplicacao.id == aplicacao_id,
            Aplicacao.ativa == True
        )
    )
    return resultado.scalar_one_or_none() is not None


async def _verificar_modelo_existe(sessao: AsyncSession, modelo_id: str) -> bool:
    """Verifica se o modelo de embedding está cadastrado e ativo no sistema."""
    resultado = await sessao.execute(
        select(ModeloEmbedding.id).where(
            ModeloEmbedding.id == modelo_id,
            ModeloEmbedding.ativo == True
        )
    )
    return resultado.scalar_one_or_none() is not None


async def criar_colecao(sessao: AsyncSession, dados: CriarColecaoSchema) -> Colecao:
    """
    Cria uma nova coleção lógica associada a uma aplicação e a um modelo de embedding,
    validando duplicidade de nome no escopo do tenant e existência das dependências.
    """
    # 1. Valida se a aplicação existe
    if not await _verificar_aplicacao_existe(sessao, dados.aplicacao_id):
        raise ValueError("A aplicação informada não foi encontrada.")

    # 2. Valida se o modelo de embedding existe
    if not await _verificar_modelo_existe(sessao, dados.modelo_embedding_id):
        raise ValueError(f"O modelo de embedding '{dados.modelo_embedding_id}' não está cadastrado.")

    # 3. Valida se já existe uma coleção com o mesmo nome para esta mesma aplicação
    consulta_nome = select(Colecao).where(
        Colecao.aplicacao_id == dados.aplicacao_id,
        func.lower(Colecao.nome) == dados.nome.strip().lower()
    )
    resultado_nome = await sessao.execute(consulta_nome)
    if resultado_nome.scalar_one_or_none():
        raise ValueError(f"Já existe uma coleção com o nome '{dados.nome}' nesta aplicação.")

    # 4. Instancia e persiste a nova coleção
    nova_colecao = Colecao(
        nome=dados.nome.strip(),
        aplicacao_id=dados.aplicacao_id,
        modelo_embedding_id=dados.modelo_embedding_id,
        tipo_armazenamento=dados.tipo_armazenamento,
        configuracao_embedding=dados.configuracao_embedding or {},
        metadados=dados.metadados or {},
        publica=dados.publica,
    )
    
    sessao.add(nova_colecao)
    await sessao.commit()
    await sessao.refresh(nova_colecao)
    return nova_colecao


async def obter_colecao_por_id(
    sessao: AsyncSession, colecao_id: uuid.UUID, aplicacao_id: Optional[uuid.UUID] = None
) -> Optional[Colecao]:
    """Busca uma coleção pelo ID, aplicando opcionalmente o filtro de tenant."""
    consulta = select(Colecao).where(Colecao.id == colecao_id)
    
    if aplicacao_id:
        consulta = consulta.where(Colecao.aplicacao_id == aplicacao_id)
        
    resultado = await sessao.execute(consulta)
    return resultado.scalar_one_or_none()


async def listar_colecoes(
    sessao: AsyncSession,
    aplicacao_id: Optional[uuid.UUID] = None,
    limite: int = 50,
    deslocamento: int = 0
) -> List[Colecao]:
    """Lista coleções cadastradas, com suporte a paginação e filtro por tenant."""
    consulta = select(Colecao)
    
    if aplicacao_id:
        consulta = consulta.where(Colecao.aplicacao_id == aplicacao_id)
        
    consulta = consulta.offset(deslocamento).limit(limite)
    
    resultado = await sessao.execute(consulta)
    return list(resultado.scalars().all())


async def atualizar_colecao(
    sessao: AsyncSession,
    colecao_id: uuid.UUID,
    aplicacao_id: uuid.UUID,
    dados: AtualizarColecaoSchema,
) -> Optional[Colecao]:
    """Atualiza metadados ou a visibilidade (pública/privada) de uma coleção."""
    
    # Verifica se a coleção pertence ao tenant
    colecao = await obter_colecao_por_id(sessao, colecao_id, aplicacao_id)
    if not colecao:
        return None

    valores_atualizacao = dados.model_dump(exclude_unset=True)

    if not valores_atualizacao:
        return colecao

    instrucao = (
        update(Colecao)
        .where(Colecao.id == colecao_id, Colecao.aplicacao_id == aplicacao_id)
        .values(**valores_atualizacao)
        .returning(Colecao)
    )
    
    resultado = await sessao.execute(instrucao)
    await sessao.commit()
    return resultado.scalar_one_or_none()


async def remover_colecao(
    sessao: AsyncSession, colecao_id: uuid.UUID, aplicacao_id: uuid.UUID
) -> bool:
    """
    Remove uma coleção e, devido ao CASCADE configurado no banco, 
    todos os embeddings vinculados a ela serão apagados automaticamente.
    """
    stmt = delete(Colecao).where(
        Colecao.id == colecao_id,
        Colecao.aplicacao_id == aplicacao_id
    )
    resultado = await sessao.execute(stmt)
    await sessao.commit()
    return resultado.rowcount > 0