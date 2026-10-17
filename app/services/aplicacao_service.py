import uuid
import secrets
import hashlib
from typing import List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert as inserir_postgresql

from app.models.modelos import Aplicacao, ChaveAPI
from app.schemas.schemas import CriarAplicacaoSchema, CriarChaveAPISchema


class NomeChaveAPIJaExisteError(ValueError):
    """Indica conflito com o nome de chave único dentro da aplicação."""


def _gerar_hash_chave(chave_plana: str) -> str:
    """Gera um hash SHA-256 da chave de API para armazenamento seguro."""
    return hashlib.sha256(chave_plana.encode("utf-8")).hexdigest()


async def criar_aplicacao(
    sessao: AsyncSession, dados: CriarAplicacaoSchema
) -> Aplicacao:
    """Cria uma nova aplicação (tenant) após verificar duplicidade de nome."""
    
    # Verifica se já existe aplicação com o mesmo nome (ignorando maiúsculas/minúsculas)
    consulta_nome = select(Aplicacao).where(
        func.lower(Aplicacao.nome) == dados.nome.strip().lower()
    )
    resultado_nome = await sessao.execute(consulta_nome)
    if resultado_nome.scalar_one_or_none():
        raise ValueError(f"Já existe uma aplicação cadastrada com o nome '{dados.nome}'.")

    # Persiste a nova aplicação
    nova_aplicacao = Aplicacao(nome=dados.nome.strip())
    sessao.add(nova_aplicacao)
    await sessao.commit()
    await sessao.refresh(nova_aplicacao)
    return nova_aplicacao


async def obter_aplicacao_por_id(
    sessao: AsyncSession, aplicacao_id: uuid.UUID
) -> Optional[Aplicacao]:
    """Busca uma aplicação pelo seu ID."""
    resultado = await sessao.execute(
        select(Aplicacao).where(Aplicacao.id == aplicacao_id)
    )
    return resultado.scalar_one_or_none()


async def listar_aplicacoes(
    sessao: AsyncSession, limite: int = 50, deslocamento: int = 0
) -> List[Aplicacao]:
    """Lista as aplicações cadastradas com paginação simples."""
    resultado = await sessao.execute(
        select(Aplicacao).offset(deslocamento).limit(limite)
    )
    return list(resultado.scalars().all())


async def criar_chave_api(
    sessao: AsyncSession, dados: CriarChaveAPISchema
) -> Tuple[ChaveAPI, str]:
    """
    Gera uma nova chave de API para uma aplicação.
    Retorna uma tupla contendo o objeto persistido (com o hash) e a chave plana original 
    (que deve ser exibida ao usuário apenas neste momento).
    """
    # 1. Valida se a aplicação existe
    aplicacao = await obter_aplicacao_por_id(sessao, dados.aplicacao_id)
    if not aplicacao:
        raise ValueError("Aplicação informada não foi encontrada.")

    nome_chave = dados.nome.strip()

    # 2. Gera uma chave criptográfica aleatória segura (ex: cb_live_...)
    chave_plana = f"cb_{secrets.token_urlsafe(32)}"
    chave_hash = _gerar_hash_chave(chave_plana)

    # 3. Persiste apenas o hash no banco de dados
    chave_id = uuid.uuid4()
    instrucao = (
        inserir_postgresql(ChaveAPI)
        .values(
            id=chave_id,
            aplicacao_id=dados.aplicacao_id,
            nome=nome_chave,
            chave_hash=chave_hash,
            revogada=False,
        )
        .on_conflict_do_nothing(
            index_elements=[
                ChaveAPI.aplicacao_id,
                func.lower(ChaveAPI.nome),
            ]
        )
        .returning(ChaveAPI.id)
    )
    resultado_insercao = await sessao.execute(instrucao)
    chave_id_inserida = resultado_insercao.scalar_one_or_none()
    if chave_id_inserida is None:
        await sessao.rollback()
        raise NomeChaveAPIJaExisteError(
            f"Já existe uma chave de API com o nome '{dados.nome}' para esta aplicação."
        )

    await sessao.commit()
    nova_chave = await sessao.get(ChaveAPI, chave_id_inserida)
    if nova_chave is None:
        raise RuntimeError("A chave de API inserida não foi encontrada.")

    return nova_chave, chave_plana

async def validar_chave_api(
    sessao: AsyncSession, chave_plana: str
) -> Optional[Aplicacao]:
    """
    Valida uma chave de API enviada no header da requisição,
    retornando a Aplicação (tenant) associada se a chave for válida e ativa.
    """
    chave_hash = _gerar_hash_chave(chave_plana)
    
    resultado = await sessao.execute(
        select(ChaveAPI, Aplicacao)
        .join(Aplicacao, ChaveAPI.aplicacao_id == Aplicacao.id)
        .where(
            ChaveAPI.chave_hash == chave_hash,
            ChaveAPI.revogada == False
        )
    )
    linha = resultado.first()
    
    if not linha:
        return None
        
    return linha.Aplicacao

async def listar_chaves_por_aplicacao(
    sessao: AsyncSession, aplicacao_id: uuid.UUID
) -> List[ChaveAPI]:
    """Lista todas as chaves de API associadas a uma aplicação."""
    resultado = await sessao.execute(
        select(ChaveAPI).where(ChaveAPI.aplicacao_id == aplicacao_id)
    )
    return list(resultado.scalars().all())


async def revogar_chave_api(
    sessao: AsyncSession, chave_id: uuid.UUID
) -> bool:
    """Revoga uma chave de API específica pelo ID."""
    instrucao = (
        update(ChaveAPI)
        .where(ChaveAPI.id == chave_id)
        .values(revogada=True)
    )
    resultado = await sessao.execute(instrucao)
    await sessao.commit()
    return resultado.rowcount > 0


async def atualizar_aplicacao(
    sessao: AsyncSession, aplicacao_id: uuid.UUID, novo_nome: str
) -> Optional[Aplicacao]:
    """Atualiza o nome de uma aplicação (tenant)."""
    # Verifica duplicidade de nome
    consulta_nome = select(Aplicacao).where(
        func.lower(Aplicacao.nome) == novo_nome.strip().lower(),
        Aplicacao.id != aplicacao_id
    )
    if (await sessao.execute(consulta_nome)).scalar_one_or_none():
        raise ValueError(f"Já existe outra aplicação com o nome '{novo_nome}'.")

    instrucao = (
        update(Aplicacao)
        .where(Aplicacao.id == aplicacao_id)
        .values(nome=novo_nome.strip())
        .returning(Aplicacao)
    )
    resultado = await sessao.execute(instrucao)
    await sessao.commit()
    return resultado.scalar_one_or_none()


async def remover_aplicacao(
    sessao: AsyncSession, aplicacao_id: uuid.UUID
) -> bool:
    """
    Remove uma aplicação. Graças ao cascade configurado nas foreign keys, 
    chaves, coleções e embeddings vinculados serão apagados automaticamente.
    """
    instrucao = delete(Aplicacao).where(Aplicacao.id == aplicacao_id)
    resultado = await sessao.execute(instrucao)
    await sessao.commit()
    return resultado.rowcount > 0
