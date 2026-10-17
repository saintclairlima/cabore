import uuid
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.modelos import Colecao, ModeloEmbedding, MetricaDistancia
from app.services import embedding_service, modelo_service
from app.services.inferencia_service import motor_inferencia

# Mock ou import real do seu serviço gerador de embeddings por texto/modelo
async def gerar_vetor_consulta_por_modelo(
    sessao: AsyncSession, texto: str, modelo_id: str) -> List[float]:
    """
    Placeholder: Aqui você integraria com o seu cliente de embedding 
    (ex: OpenAI, BGE-M3 local, Gemini, etc.) com base no ID do modelo.
    """
    modelo: ModeloEmbedding = await modelo_service.obter_modelo_por_id(sessao, modelo_id)
    resultado = await motor_inferencia.gerar_vetor(texto, modelo.id, modelo.identificador_repositorio)
    
    return resultado


async def buscar_similaridade(
    sessao: AsyncSession,
    nomes_ou_ids_colecoes: List[str],
    texto_consulta: str,
    limite: int = 10,
    filtro_metadados: Optional[Dict[str, Any]] = None,
    aplicacao_id: Optional[uuid.UUID] = None,
) -> List[Dict[str, Any]]:
    """
    Orquestra a busca global em múltiplas coleções que podem pertencer a modelos/dimensões diferentes.
    """
    if not nomes_ou_ids_colecoes:
        return []

    # 1. Identifica e mapeia quais coleções foram solicitadas e quais modelos elas usam
    consulta = (
        select(Colecao, ModeloEmbedding)
        .join(ModeloEmbedding, Colecao.modelo_embedding_id == ModeloEmbedding.id)
    )

    # Permite buscar tanto por ID UUID quanto por Nome da coleção
    # Verificamos se o primeiro elemento parece um UUID ou uma string de nome
    try:
        uuid.UUID(str(nomes_ou_ids_colecoes[0]))
        consulta = consulta.where(Colecao.id.in_([uuid.UUID(str(c)) for c in nomes_ou_ids_colecoes]))
    except ValueError:
        consulta = consulta.where(Colecao.nome.in_(nomes_ou_ids_colecoes))

    if aplicacao_id:
        consulta = consulta.where(Colecao.aplicacao_id == aplicacao_id)

    resultado = await sessao.execute(consulta)
    linhas = resultado.all()

    if not linhas:
        raise ValueError("Nenhuma das coleções especificadas foi encontrada.")

    # 2. Agrupa as coleções por modelo/dimensão
    # Exemplo: { "bge-m3": [col_id_1, col_id_2], "text-embedding-3-small": [col_id_3] }
    grupos_por_modelo: Dict[str, Dict[str, Any]] = {}
    
    for linha in linhas:
        if linha.ModeloEmbedding.metrica_distancia != MetricaDistancia.COSINE:
            raise ValueError(
                f"O modelo '{linha.ModeloEmbedding.id}' está configurado com uma métrica "
                "não suportada pela busca. Configure a métrica cosine."
            )

        modelo_id = linha.ModeloEmbedding.id
        if modelo_id not in grupos_por_modelo:
            grupos_por_modelo[modelo_id] = {
                "dimensoes": linha.ModeloEmbedding.dimensoes,
                "colecao_ids": []
            }
        grupos_por_modelo[modelo_id]["colecao_ids"].append(linha.Colecao.id)
        
    # 3. Executa as buscas sequencialmente para reutilizar a sessão com segurança
    resultados_globais = []
    for modelo_id, dados_grupo in grupos_por_modelo.items():
        # Gera o vetor de consulta específico para este modelo usando o texto
        vetor_consulta = await gerar_vetor_consulta_por_modelo(sessao, texto_consulta, modelo_id)
        
        # Cada consulta usa a mesma sessão assíncrona, portanto não deve concorrer com outra
        resultados_grupo = await embedding_service.buscar_similaridade(
            sessao=sessao,
            colecao_ids=dados_grupo["colecao_ids"],
            vetor_consulta=vetor_consulta,
            limite=limite,
            filtro_metadados=filtro_metadados,
            aplicacao_id=aplicacao_id
        )
        resultados_globais.extend(resultados_grupo)

    # 4. Reordena globalmente por relevância (menor distância de cosseno primeiro)
    resultados_globais.sort(key=lambda x: x["distancia"])

    # 5. Retorna fatiado pelo limite global desejado pelo usuário
    return resultados_globais[:limite]