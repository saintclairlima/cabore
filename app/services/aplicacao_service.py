import uuid
import secrets
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert as inserir_postgresql

from app.models.modelos import (
    Aplicacao,
    ChaveAPI,
    Colecao,
    ModeloEmbedding,
    AuditoriaRequisicao,
    Embedding256,
    Embedding512,
    Embedding768,
    Embedding1024,
    Embedding1536,
    EmbeddingHalfVec3072,
)
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


async def obter_detalhes_aplicacao(
    sessao: AsyncSession,
    aplicacao_id: uuid.UUID,
    dias: int = 30,
) -> Optional[dict]:
    """
    Recupera os dados cadastrais, coleções, embeddings e chaves
    associados a uma aplicação.
    """
    
    resultado_aplicacao = await sessao.execute(
        select(Aplicacao).where(Aplicacao.id == aplicacao_id)
    )
    aplicacao = resultado_aplicacao.scalar_one_or_none()

    if aplicacao is None:
        return None
    
    resultado_colecoes = await sessao.execute(
        select(Colecao, ModeloEmbedding)
        .join(
            ModeloEmbedding,
            Colecao.modelo_embedding_id == ModeloEmbedding.id,
        )
        .where(Colecao.aplicacao_id == aplicacao_id)
        .order_by(Colecao.criado_em.desc())
    )

    linhas_colecoes = resultado_colecoes.all()
    
    classes_embedding = [
        Embedding256,
        Embedding512,
        Embedding768,
        Embedding1024,
        Embedding1536,
        EmbeddingHalfVec3072,
    ]

    quantidades_embeddings: Dict[uuid.UUID, int] = {}

    for classe_embedding in classes_embedding:
        resultado_contagem = await sessao.execute(
            select(
                classe_embedding.colecao_id,
                func.count(classe_embedding.id),
            )
            .join(
                Colecao,
                Colecao.id == classe_embedding.colecao_id,
            )
            .where(Colecao.aplicacao_id == aplicacao_id)
            .group_by(classe_embedding.colecao_id)
        )

        for colecao_id, quantidade in resultado_contagem.all():
            quantidades_embeddings[colecao_id] = (
                quantidades_embeddings.get(colecao_id, 0)
                + quantidade
            )
            
    colecoes = []

    for colecao, modelo in linhas_colecoes:
        colecoes.append({
            "id": colecao.id,
            "nome": colecao.nome,
            "tipo_armazenamento": colecao.tipo_armazenamento.value,
            "publica": colecao.publica,
            "criado_em": colecao.criado_em,
            "quantidade_embeddings": quantidades_embeddings.get(
                colecao.id, 0
            ),
            "modelo": {
                "id": modelo.id,
                "nome": modelo.nome,
                "provedor": modelo.provedor,
                "dimensoes": modelo.dimensoes,
                "metrica_distancia": modelo.metrica_distancia.value,
                "ativo": modelo.ativo,
            },
        })
        
    resultado_chaves = await sessao.execute(
        select(ChaveAPI)
        .where(ChaveAPI.aplicacao_id == aplicacao_id)
        .order_by(ChaveAPI.criado_em.desc())
    )

    chaves = resultado_chaves.scalars().all()

    chaves_api = [
        {
            "id": chave.id,
            "nome": chave.nome,
            "revogada": chave.revogada,
            "criado_em": chave.criado_em,
        }
        for chave in chaves
    ]
    
    total_embeddings = sum(
        quantidades_embeddings.values()
    )

    total_chaves_ativas = sum(
        1 for chave in chaves if not chave.revogada
    )

    # Métricas de utilização da aplicação
    inicio = datetime.now(timezone.utc) - timedelta(days=dias)

    filtro_auditoria = (
        AuditoriaRequisicao.aplicacao_id == aplicacao_id,
        AuditoriaRequisicao.criado_em >= inicio,
    )

    resultado_utilizacao = await sessao.execute(
        select(
            func.count(AuditoriaRequisicao.id),
            func.avg(AuditoriaRequisicao.tempo_execucao_ms),
            func.percentile_cont(0.95).within_group(
                AuditoriaRequisicao.tempo_execucao_ms
            ),
            func.coalesce(
                func.sum(AuditoriaRequisicao.quantidade_resultados),
                0,
            ),
        ).where(*filtro_auditoria)
    )

    (
        total_requisicoes,
        latencia_media,
        latencia_p95,
        total_resultados,
    ) = resultado_utilizacao.one()

    # Série diária de requisições e latência média
    dia_utc = func.date_trunc(
        "day",
        func.timezone("UTC", AuditoriaRequisicao.criado_em),
    )

    resultado_serie_diaria = await sessao.execute(
        select(
            dia_utc.label("dia"),
            func.count(AuditoriaRequisicao.id).label("requisicoes"),
            func.avg(
                AuditoriaRequisicao.tempo_execucao_ms
            ).label("latencia_media_ms"),
        )
        .where(*filtro_auditoria)
        .group_by(dia_utc)
        .order_by(dia_utc)
    )

    serie_diaria = [
        {
            "dia": linha.dia,
            "requisicoes": linha.requisicoes,
            "latencia_media_ms": float(
                linha.latencia_media_ms or 0
            ),
        }
        for linha in resultado_serie_diaria.all()
    ]

    # Distribuição por operação
    resultado_operacoes = await sessao.execute(
        select(
            AuditoriaRequisicao.operacao,
            func.count(AuditoriaRequisicao.id).label("quantidade"),
        )
        .where(*filtro_auditoria)
        .group_by(AuditoriaRequisicao.operacao)
        .order_by(func.count(AuditoriaRequisicao.id).desc())
    )

    operacoes = [
        {
            "operacao": linha.operacao,
            "quantidade": linha.quantidade,
        }
        for linha in resultado_operacoes.all()
    ]

    # Requisições recentes
    resultado_recentes = await sessao.execute(
        select(AuditoriaRequisicao, Colecao.nome)
        .outerjoin(
            Colecao,
            Colecao.id == AuditoriaRequisicao.colecao_id,
        )
        .where(
            AuditoriaRequisicao.aplicacao_id == aplicacao_id
        )
        .order_by(AuditoriaRequisicao.criado_em.desc())
        .limit(15)
    )

    requisicoes_recentes = [
        {
            "id": auditoria.id,
            "operacao": auditoria.operacao,
            "tempo_execucao_ms": float(
                auditoria.tempo_execucao_ms or 0
            ),
            "quantidade_resultados": auditoria.quantidade_resultados,
            "colecao": nome_colecao,
            "criado_em": auditoria.criado_em,
        }
        for auditoria, nome_colecao in resultado_recentes.all()
    ]

    utilizacao = {
        "periodo_dias": dias,
        "requisicoes": total_requisicoes or 0,
        "latencia_media_ms": float(latencia_media or 0),
        "latencia_p95_ms": float(latencia_p95 or 0),
        "resultados": int(total_resultados or 0),
        "serie_diaria": serie_diaria,
        "operacoes": operacoes,
        "requisicoes_recentes": requisicoes_recentes,
    }

    return {
        "aplicacao": {
            "id": aplicacao.id,
            "nome": aplicacao.nome,
            "ativa": aplicacao.ativa,
            "criado_em": aplicacao.criado_em,
        },
        "resumo": {
            "total_colecoes": len(colecoes),
            "total_embeddings": total_embeddings,
            "total_chaves": len(chaves_api),
            "chaves_ativas": total_chaves_ativas,
            "chaves_revogadas": len(chaves_api) - total_chaves_ativas,
        },
        "colecoes": colecoes,
        "chaves_api": chaves_api,
        "utilizacao": utilizacao,
    }


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
            ChaveAPI.revogada == False,
            Aplicacao.ativa.is_(True),
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


async def atualizar_status_aplicacao(
    sessao: AsyncSession,
    aplicacao_id: uuid.UUID,
    ativa: bool,
) -> bool:
    resultado = await sessao.execute(
        update(Aplicacao)
        .where(Aplicacao.id == aplicacao_id)
        .values(ativa=ativa)
    )

    await sessao.commit()

    return resultado.rowcount > 0


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
