from typing import Any, Callable, Dict, List, Optional, TypedDict
import uuid

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.modelos import Aplicacao, Colecao, EmbeddingBase, MetricaDistancia, ModeloEmbedding
from app.models.tipos import EstrategiaCombinacao, MetadataDict
from app.schemas.schemas import ResultadoBuscaSchema
from app.services import embedding_service, modelo_service
from app.services.inferencia_service import motor_inferencia

class GrupoModeloBusca(TypedDict):
    modelo: ModeloEmbedding
    ids_colecoes: List[uuid.UUID]


def obter_funcao_distancia(
    classe_embedding: type[EmbeddingBase],
    metrica_distancia: MetricaDistancia
) -> Callable:
    
    if metrica_distancia == MetricaDistancia.COSINE:
        return classe_embedding.vetor.cosine_distance

    elif metrica_distancia == MetricaDistancia.L2:
        return classe_embedding.vetor.l2_distance

    elif metrica_distancia == MetricaDistancia.IP:
        return classe_embedding.vetor.max_inner_product

    raise ValueError(f'Métrica de distância não suportada: {metrica_distancia}')


def reciprocal_rank_fusion(
    resultados: List[ResultadoBuscaSchema],
    k: int = 60,
    top_k_global: Optional[int] = None
) -> List[ResultadoBuscaSchema]:
    '''
    Aplica o algoritmo Reciprocal Rank Fusion (RRF) em resultados de várias coleções.
    Combina rankings independentes por coleção utilizando RRF.

    - Calcula a pontuação por conteudo_hash.
    - Cada conteúdo contribui apenas uma vez por coleção, considerando sua melhor posição.
    - Preserva todas as ocorrências dos documentos.
    - Mantém juntas as ocorrências de um mesmo conteúdo.
    - Aplica top_k_global sobre a quantidade de conteúdos distintos.

    Nota: o valor de 60 para k é justificado no paper que introduziu o RRF
        ('Reciprocal Rank Fusion Outperforms Condorcet and Individual Rank Learning Methods',
        por Gordon V. Cormack, Charles L. A. Clarke e Stefan Buettcher).
        Nos testes deles com grandes volumes de dados de recuperação de informação, o valor 60 provou
        ser o sweet spot mais estável para diferentes tipos de motores de busca e conjuntos de dados
    '''

    if k <= 0:
        raise ValueError('O parâmetro k deve ser maior que zero.')

    if top_k_global is not None and top_k_global < 1:
        raise ValueError('top_k_global deve ser maior que zero.')

    rankings_por_colecao: Dict[str, List[ResultadoBuscaSchema]] = {}

    # Agrupa os documentos por coleção
    for doc in resultados:
        colecao_id = doc['colecao_id']
        rankings_por_colecao.setdefault(colecao_id, []).append(doc)

    scores_por_conteudo: Dict[str, float] = {}
    documentos_por_conteudo: Dict[str, List[ResultadoBuscaSchema]] = {}

    # Processa cada ranking independentemente
    for ranking in rankings_por_colecao.values():
        ranking.sort(key=lambda doc: (doc['distancia'], doc['id']))
        hashes_processados = set()

        for rank, doc in enumerate(ranking, start=1):
            conteudo_hash = doc['conteudo_hash']
            # Preserva todas as ocorrências
            documentos_por_conteudo.setdefault(conteudo_hash, []).append(doc)
            # Cada conteúdo contribui apenas uma vez por coleção, considerando sua melhor posição
            if conteudo_hash in hashes_processados:
                continue

            hashes_processados.add(conteudo_hash)
            scores_por_conteudo[conteudo_hash] = (scores_por_conteudo.get(conteudo_hash, 0.0) + 1.0 / (k + rank))

    # Ordena os conteúdos pela pontuação RRF
    conteudos_ordenados = sorted(
        scores_por_conteudo,
        key=lambda conteudo_hash: (-scores_por_conteudo[conteudo_hash], conteudo_hash)
    )

    # Aplica o limite sobre conteúdos distintos, preservando integralmente os grupos selecionados
    if top_k_global is not None:
        conteudos_ordenados = conteudos_ordenados[:top_k_global]

    resultados_finais = []

    # Recupera todas as ocorrências de cada conteúdo
    for conteudo_hash in conteudos_ordenados:

        score = float(scores_por_conteudo[conteudo_hash])

        ocorrencias = sorted(
            documentos_por_conteudo[conteudo_hash],
            key=lambda doc: (doc['colecao_id'], doc['id'])
        )

        for doc in ocorrencias:
            resultado = doc.copy()
            #resultado['distancia'] = None
            #resultado['metrica_distancia'] = MetricaDistancia.RRF
            resultado['score_relevancia'] = score
            resultados_finais.append(resultado)

    return resultados_finais


async def gerar_vetor_consulta_por_modelo(
    sessao: AsyncSession, texto: str, modelo_id: str) -> List[float]:
    '''
    Gera um vetor de embeddings a partir do texto, usando o modelo de embeddings com id igual a modelo_id.
    '''
    modelo: ModeloEmbedding = await modelo_service.obter_modelo_por_id(sessao, modelo_id)
    vetor_embedding = await motor_inferencia.gerar_vetor(texto, modelo.id, modelo.identificador_repositorio)
    
    return vetor_embedding


async def buscar_similaridade(
    sessao: AsyncSession,
    aplicacao_cliente: Aplicacao,
    texto_consulta: str,
    ids_colecoes: Optional[List[str]] = None,
    ids_aplicacoes: Optional[List[str]] = None,
    filtro_metadados: Optional[Dict[str, Any]] = None,
    top_k_colecao: int = 10,
    top_k_global: Optional[int] = None,
    estrategia_combinacao: EstrategiaCombinacao = EstrategiaCombinacao.NONE,
) -> List[ResultadoBuscaSchema]:
    '''
    Orquestra a busca global em múltiplas coleções que podem pertencer a modelos/dimensões diferentes.
    '''

    if top_k_colecao < 1:
        raise ValueError(f'O valor do parâmetro top_k_colecao fornecido ({top_k_colecao}) é inválido. Deve ser maior que zero.')

    if top_k_global is not None and top_k_global < 1:
        raise ValueError(f'O valor do parâmetro top_k_global fornecido ({top_k_global}) é inválido. Deve ser maior que zero.')

    # Identifica e mapeia quais coleções foram solicitadas e quais modelos elas usam
    consulta_colecoes_modelos = (
        select(Colecao, ModeloEmbedding)
        .join(ModeloEmbedding, Colecao.modelo_embedding_id == ModeloEmbedding.id)
    )

    if ids_colecoes:
        try:
            ids_convertidos = [uuid.UUID(str(c)) for c in ids_colecoes]
        except ValueError:
            raise ValueError('Contém ID de coleção com formato inválido.')

        consulta_colecoes_modelos = consulta_colecoes_modelos.where(
            and_(
                Colecao.id.in_(ids_convertidos),
                or_(
                    Colecao.aplicacao_id == aplicacao_cliente.id,
                    Colecao.publica.is_(True)
                )
            )
        )
    elif ids_aplicacoes:
        try:
            apps_convertidos = [uuid.UUID(str(a)) for a in ids_aplicacoes]
        except ValueError:
            raise ValueError('Contém ID de aplicação com formato inválido.')

        propria_app_inclusa = aplicacao_cliente.id in apps_convertidos

        if propria_app_inclusa:
            consulta_colecoes_modelos = consulta_colecoes_modelos.where(
                or_(
                    Colecao.aplicacao_id == aplicacao_cliente.id,
                    and_(
                        Colecao.aplicacao_id.in_(apps_convertidos),
                        Colecao.publica.is_(True)
                    )
                )
            )
        else:
            consulta_colecoes_modelos = consulta_colecoes_modelos.where(
                and_(
                    Colecao.aplicacao_id.in_(apps_convertidos),
                    Colecao.publica == True
                )
            )
    else:
        consulta_colecoes_modelos = consulta_colecoes_modelos.where(
            or_(
                Colecao.aplicacao_id == aplicacao_cliente.id,
                Colecao.publica.is_(True)
            )
        )

    resultado_colecoes_modelos = await sessao.execute(consulta_colecoes_modelos)
    lista_colecoes_modelos = resultado_colecoes_modelos.all()

    if not lista_colecoes_modelos:
        raise ValueError('Nenhuma das coleções especificadas foi encontrada.')

    # Agrupa as coleções por modelo/dimensão
    # Exemplo: { 'bge-m3': [col_id_1, col_id_2], 'text-embedding-3-small': [col_id_3] }
    # AFAZER: caberia tipar aqui?
    grupos_por_modelo: Dict[str, GrupoModeloBusca] = {}
    
    for colecao_modelo in lista_colecoes_modelos:
        modelo: ModeloEmbedding = colecao_modelo.ModeloEmbedding
        colecao: Colecao = colecao_modelo.Colecao
        if modelo.id not in grupos_por_modelo:
            grupos_por_modelo[modelo.id] = {
                'modelo': modelo,
                'ids_colecoes': []
            }
        grupos_por_modelo[modelo.id]['ids_colecoes'].append(colecao.id)
        
    # Executa as buscas sequencialmente para reutilizar a sessão com segurança
    resultados_recuperados: List[ResultadoBuscaSchema] = []

    for modelo_id, grupo_modelo in grupos_por_modelo.items():
        # Gera o vetor de consulta específico para este modelo usando o texto
        vetor_consulta = await gerar_vetor_consulta_por_modelo(sessao, texto_consulta, modelo_id)
        
        # Cada consulta usa a mesma sessão assíncrona, portanto não deve concorrer com outra
        resultados_grupo = await buscar_multicolecoes(
            sessao=sessao,
            vetor_consulta=vetor_consulta,
            grupo_modelo=grupo_modelo,
            top_k_colecao=top_k_colecao,
            filtro_metadados=filtro_metadados
        )

        resultados_recuperados.extend(resultados_grupo)
        
    if estrategia_combinacao == EstrategiaCombinacao.RRF:
        resultados_finais = reciprocal_rank_fusion(resultados=resultados_recuperados, k=60, top_k_global=top_k_global)
    else:
        resultados_finais = resultados_recuperados
        
        if top_k_global is not None:
            resultados_finais = resultados_finais[:top_k_global]

    return resultados_finais


async def buscar_por_colecao(
    sessao: AsyncSession,
    colecao_id: uuid.UUID,
    vetor_consulta: List[float],
    limite: int = 10,
    filtro_metadados: Optional[MetadataDict] = None,
    metrica_distancia: MetricaDistancia = MetricaDistancia.COSINE
) -> List[ResultadoBuscaSchema]:
    '''
    Realiza busca por similaridade de cosseno com suporte a filtro estrito por metadados JSONB.
    '''
    
    # Valida coleção/aplicação e descobre a tabela
    consulta_colecao_modelo = (
        select(Colecao, ModeloEmbedding)
        .join(ModeloEmbedding, Colecao.modelo_embedding_id == ModeloEmbedding.id)
        .where(Colecao.id == colecao_id)
    )

    resultado_colecao_modelo = await sessao.execute(consulta_colecao_modelo)
    colecao_modelo = resultado_colecao_modelo.fetchone()

    if not colecao_modelo:
        raise ValueError('Coleção não encontrada.')
    
    # Valida se há mistura de dimensões incompatíveis na mesma busca
    dimensoes = colecao_modelo.ModeloEmbedding.dimensoes
        
    if len(vetor_consulta) != dimensoes:
        raise ValueError(f'Dimensões do vetor de consulta ({len(vetor_consulta)}) incompatíveis com as dimensões do modelo ({dimensoes}).')

    classe_embedding = embedding_service.obter_classe_embedding(dimensoes)
    funcao_distancia = obter_funcao_distancia(classe_embedding, metrica_distancia)
    distancia = funcao_distancia(vetor_consulta).label('distancia')

    consulta_busca = (
        select(classe_embedding, distancia)
        .where(classe_embedding.colecao_id == colecao_id)
    )

    # Aplica filtro JSONB se fornecido (aproveita o índice GIN criado no model)
    if filtro_metadados:
        consulta_busca = consulta_busca.where(classe_embedding.metadados.contains(filtro_metadados))

    consulta_busca = consulta_busca.order_by(distancia).limit(limite)
    resultado = await sessao.execute(consulta_busca)
    linhas = resultado.all()
    
    nome_modelo = colecao_modelo.ModeloEmbedding.id

    resultados: List[ResultadoBuscaSchema] = []
    for registro, dist in linhas:
        resultado: ResultadoBuscaSchema = {
            'id': str(registro.id),
            'colecao_id': str(registro.colecao_id),
            'conteudo_hash': registro.conteudo_hash,
            'distancia': float(dist),
            'rank_colecao': registro.num_linha,
            'metrica_distancia': metrica_distancia.value,
            'nome_modelo': nome_modelo,
            'modelo_dimensoes': dimensoes,
            'metadados': registro.metadados,
            'criado_em': registro.criado_em,
        }
        resultados.append(resultado)
    return resultados


async def buscar_multicolecoes(
    sessao: AsyncSession,
    vetor_consulta: List[float],
    grupo_modelo: GrupoModeloBusca,
    top_k_colecao: int = 10,
    filtro_metadados: Optional[MetadataDict] = None
) -> List[ResultadoBuscaSchema]:
    '''
    Realiza busca por similaridade de cosseno com suporte a filtro estrito por metadados JSONB.
    '''

    ids_colecoes = grupo_modelo['ids_colecoes']
    modelo = grupo_modelo['modelo']

    if not ids_colecoes:
        return []
        
    if len(vetor_consulta) != modelo.dimensoes:
        raise ValueError(f'Dimensões do vetor de consulta ({len(vetor_consulta)}) incompatíveis com o modelo ({modelo.dimensoes}).')

    classe_embedding = embedding_service.obter_classe_embedding(modelo.dimensoes)
    funcao_distancia = obter_funcao_distancia(classe_embedding, modelo.metrica_distancia)
    distancia = funcao_distancia(vetor_consulta).label('distancia')

    num_linha = (
        func.row_number()
        .over(
            partition_by=classe_embedding.colecao_id,
            order_by=[
                distancia,
                classe_embedding.id
            ]
        )
        .label('num_linha')
    )

    subquery = (
        select(
            classe_embedding.id,
            classe_embedding.colecao_id,
            classe_embedding.conteudo_hash,
            classe_embedding.metadados,
            classe_embedding.criado_em,
            distancia.label('distancia'),
            num_linha
        )
        .where(
            classe_embedding.colecao_id.in_(ids_colecoes)
        )
    )

    if filtro_metadados:
        subquery = subquery.where(
            classe_embedding.metadados.contains(filtro_metadados)
        )

    subquery = subquery.subquery()

    # Consulta externa: aplica o limite individual por coleção
    consulta_busca = (
        select(subquery)
        .where(subquery.c.num_linha <= top_k_colecao)
        .order_by(
            subquery.c.distancia,
            subquery.c.colecao_id,
            subquery.c.num_linha
        )
    )

    resultado = await sessao.execute(consulta_busca)
    linhas = resultado.all()

    resultados: List[ResultadoBuscaSchema] = []

    for registro in linhas:

        resultados.append({
            'id': str(registro.id),
            'colecao_id': str(registro.colecao_id),
            'conteudo_hash': registro.conteudo_hash,
            'distancia': float(registro.distancia),
            'metrica_distancia': modelo.metrica_distancia.value,
            'score_relevancia': None,
            'nome_modelo': modelo.id,
            'modelo_dimensoes': modelo.dimensoes,
            'metadados': registro.metadados,
            'criado_em': registro.criado_em,
        })

    return resultados