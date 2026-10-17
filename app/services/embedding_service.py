import uuid
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, update
from sqlalchemy.dialects.postgresql import insert as inserir_postgresql
from app.models.modelos import (
    Colecao,
    ModeloEmbedding,
    MetricaDistancia,
    EmbeddingBase,
    Embedding512,
    Embedding768,
    Embedding1024,
    Embedding1536,
    EmbeddingHalfVec3072,
)
from app.schemas.schemas import InserirEmbeddingSchema, ResultadoBuscaSchema
from app.models.tipos import MetadataDict


def obter_classe_embedding(dimensoes: int):
    """Seleciona dinamicamente a tabela física correta com base nas dimensões do modelo."""
    mapeamento = {
        512: Embedding512,
        768: Embedding768,
        1024: Embedding1024,
        1536: Embedding1536,
        3072: EmbeddingHalfVec3072,
    }
    classe_modelo = mapeamento.get(dimensoes)
    if not classe_modelo:
        raise ValueError(
            f"Não há tabela de vetores mapeada para o modelo com {dimensoes} dimensões."
        )
    return classe_modelo


async def _obter_modelo_e_classe_por_colecao(sessao: AsyncSession, colecao_id: uuid.UUID):
    """Método auxiliar para recuperar a coleção, o modelo e a classe da tabela correta."""
    consulta = (
        select(Colecao, ModeloEmbedding)
        .join(ModeloEmbedding, Colecao.modelo_embedding_id == ModeloEmbedding.id)
        .where(Colecao.id == colecao_id)
    )
    resultado = await sessao.execute(consulta)
    linha = resultado.first()
    
    if not linha:
        raise ValueError("Coleção informada não foi encontrada.")
    
    colecao, modelo = linha
    classe_embedding = obter_classe_embedding(modelo.dimensoes)
    return colecao, modelo, classe_embedding


async def inserir_embedding(sessao: AsyncSession, dados: InserirEmbeddingSchema) -> EmbeddingBase:
    """Insere um embedding individual ou retorna o existente (Get-or-Create por hash)."""

    _, modelo, classe_embedding = await _obter_modelo_e_classe_por_colecao(sessao, dados.colecao_id)
    
    # Valida se o vetor gerado possui o tamanho correto exigido pelo modelo
    if len(dados.vetor) != modelo.dimensoes:
        raise ValueError(
            f"O vetor possui {len(dados.vetor)} dimensões, mas o modelo '{modelo.id}' exige exatamente {modelo.dimensoes}."
        )

    conteudo_hash = EmbeddingBase.gerar_hash(dados.texto_referencia)

    tabela = classe_embedding.__table__
    instrucao = (
        inserir_postgresql(tabela)
        .values(
            colecao_id=dados.colecao_id,
            conteudo_hash=conteudo_hash,
            embedding=dados.vetor,
            metadados=dados.metadados or {},
        )
        .on_conflict_do_nothing(
            index_elements=[tabela.c.colecao_id, tabela.c.conteudo_hash]
        )
        .returning(tabela.c.id)
    )
    resultado = await sessao.execute(instrucao)
    embedding_id = resultado.scalar_one_or_none()

    consulta_embedding = select(classe_embedding).where(
        tabela.c.colecao_id == dados.colecao_id,
        tabela.c.conteudo_hash == conteudo_hash,
    )
    if embedding_id is not None:
        consulta_embedding = select(classe_embedding).where(
            classe_embedding.id == embedding_id
        )

    resultado_embedding = await sessao.execute(consulta_embedding)
    await sessao.commit()
    return resultado_embedding.scalar_one()


async def inserir_embeddings_lote(
    sessao: AsyncSession, colecao_id: uuid.UUID, lista_dados: List[InserirEmbeddingSchema]
) -> List[EmbeddingBase]:
    """
    Insere múltiplos embeddings em lote, filtrando duplicados na mesma requisição
    e usando conflito atômico para não duplicar registros em requisições concorrentes.
    """
    if not lista_dados:
        return []

    _, modelo, classe_embedding = await _obter_modelo_e_classe_por_colecao(sessao, colecao_id)
    dimensoes = modelo.dimensoes

    # Mapeia hashes gerados para evitar duplicidade interna no próprio lote
    registros_para_inserir = []
    hashes_processados = set()

    for item in lista_dados:
        if len(item.vetor) != dimensoes:
            raise ValueError(f"Um dos vetores possui tamanho incompatível com o modelo ({dimensoes} dimensões).")
        
        conteudo_hash = EmbeddingBase.gerar_hash(item.texto_referencia)
        
        if conteudo_hash in hashes_processados:
            continue
        hashes_processados.add(conteudo_hash)

        registros_para_inserir.append({
            "colecao_id": colecao_id,
            "conteudo_hash": conteudo_hash,
            "vetor": item.vetor,
            "metadados": item.metadados or {}
        })

    hashes_lista = list(hashes_processados)
    if registros_para_inserir:
        tabela = classe_embedding.__table__
        instrucao = inserir_postgresql(tabela).on_conflict_do_nothing(
            index_elements=[tabela.c.colecao_id, tabela.c.conteudo_hash]
        )
        valores_insercao = [
            {
                "colecao_id": registro["colecao_id"],
                "conteudo_hash": registro["conteudo_hash"],
                "embedding": registro["vetor"],
                "metadados": registro["metadados"],
            }
            for registro in registros_para_inserir
        ]
        await sessao.execute(instrucao, valores_insercao)

    # Retorna todos os registros correspondentes aos hashes solicitados (novos e já existentes)
    stmt_final = select(classe_embedding).where(
        classe_embedding.colecao_id == colecao_id,
        classe_embedding.conteudo_hash.in_(hashes_lista)
    )
    resultado_final = await sessao.execute(stmt_final)
    registros_finais = list(resultado_final.scalars().all())
    if registros_para_inserir:
        await sessao.commit()
    return registros_finais


async def buscar_similaridade(
    sessao: AsyncSession,
    colecao_ids: List[uuid.UUID],
    vetor_consulta: List[float],
    limite: int = 10,
    filtro_metadados: Optional[MetadataDict] = None,
    aplicacao_id: Optional[uuid.UUID] = None,
) -> List[ResultadoBuscaSchema]:
    """
    Realiza busca por similaridade de cosseno com suporte a filtro estrito por metadados JSONB.
    """

    if not colecao_ids:
        return []
    
    # Valida coleção/aplicação e descobre a tabela
    consulta_colecoes = (
        select(Colecao, ModeloEmbedding)
        .join(ModeloEmbedding, Colecao.modelo_embedding_id == ModeloEmbedding.id)
        .where(Colecao.id.in_(colecao_ids))
    )

    if aplicacao_id:
        consulta_colecoes = consulta_colecoes.where(Colecao.aplicacao_id == aplicacao_id)

    resultado_colecoes = await sessao.execute(consulta_colecoes)
    linhas_colecoes = resultado_colecoes.all()

    if not linhas_colecoes:
        raise ValueError("Coleção não encontrada ou acesso negado.")

    for linha in linhas_colecoes:
        if linha.ModeloEmbedding.metrica_distancia != MetricaDistancia.COSINE:
            raise ValueError(
                f"O modelo '{linha.ModeloEmbedding.id}' está configurado com uma métrica "
                "não suportada pela busca. Configure a métrica cosine."
            )

    # Valida se há mistura de dimensões incompatíveis na mesma busca
    dimensoes = linhas_colecoes[0].ModeloEmbedding.dimensoes

    for linha in linhas_colecoes:
        if linha.ModeloEmbedding.dimensoes != dimensoes:
            raise ValueError(
                "Não é permitido buscar simultaneamente em coleções com modelos de dimensões diferentes."
            )
        
    if len(vetor_consulta) != dimensoes:
        raise ValueError(f"Dimensões do vetor de consulta ({len(vetor_consulta)}) incompatíveis com o modelo ({dimensoes}).")

    classe_embedding = obter_classe_embedding(dimensoes)
    distancia = classe_embedding.vetor.cosine_distance(vetor_consulta).label("distancia")

    consulta_busca = (
        select(classe_embedding, distancia)
        .where(classe_embedding.colecao_id.in_(colecao_ids))
    )

    # Aplica filtro JSONB se fornecido (aproveita o índice GIN criado no model)
    if filtro_metadados:
        consulta_busca = consulta_busca.where(classe_embedding.metadados.contains(filtro_metadados))

    consulta_busca = consulta_busca.order_by(distancia).limit(limite)

    resultado = await sessao.execute(consulta_busca)
    linhas = resultado.all()

    resultados: List[ResultadoBuscaSchema] = []
    for registro, dist in linhas:
        resultados.append({
            "id": str(registro.id),
            "colecao_id": str(registro.colecao_id),
            "conteudo_hash": registro.conteudo_hash,
            "distancia": float(dist),
            "metadados": registro.metadados,
            "criado_em": registro.criado_em,
        })
    return resultados


async def atualizar_embedding_metadados(
    sessao: AsyncSession, embedding_id: uuid.UUID, colecao_id: uuid.UUID, novos_metadados: MetadataDict
) -> Optional[EmbeddingBase]:
    """Atualiza os metadados de um embedding específico."""
    colecao, _, classe_embedding = await _obter_modelo_e_classe_por_colecao(sessao, colecao_id)
    
    instrucao = (
        update(classe_embedding)
        .where(classe_embedding.id == embedding_id, classe_embedding.colecao_id == colecao_id)
        .values(metadados=novos_metadados)
        .returning(classe_embedding)
    )
    resultado = await sessao.execute(instrucao)
    await sessao.commit()
    return resultado.scalar_one_or_none()


async def remover_embedding(
    sessao: AsyncSession, embedding_id: uuid.UUID, colecao_id: uuid.UUID
) -> bool:
    """Remove um embedding pelo seu ID e Coleção."""
    _, _, classe_embedding = await _obter_modelo_e_classe_por_colecao(sessao, colecao_id)
    
    instrucao = delete(classe_embedding).where(
        classe_embedding.id == embedding_id,
        classe_embedding.colecao_id == colecao_id
    )
    resultado = await sessao.execute(instrucao)
    await sessao.commit()
    return resultado.rowcount > 0