from datetime import datetime
import uuid
from typing import  Any, Dict, List, Literal, Optional, TypedDict
from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.limites import (
    LIMITE_MAXIMO_COLECOES_BUSCA,
    LIMITE_MAXIMO_DIMENSAO_VETOR,
    LIMITE_MAXIMO_TEXTO,
)
from app.models.modelos import MetricaDistancia, TipoArmazenamento
from app.models.tipos import ConfigEmbeddingDict, IdentificadorColecao, MetadataDict, ValorVetor

MetricaDistanciaSuportada = Literal[MetricaDistancia.COSINE]


class CriarAplicacaoSchema(BaseModel):
    nome: str = Field(..., max_length=100)
    
class AtualizarAplicacaoSchema(BaseModel):
    nome: Optional[str] = Field(None, max_length=100)

class RespostaAplicacaoSchema(BaseModel):
    id: uuid.UUID
    nome: str
    criado_em: Any

    model_config = ConfigDict(from_attributes=True)
    
class CriarChaveAPISchema(BaseModel):
    aplicacao_id: uuid.UUID
    nome: str = Field(..., max_length=100, description="Nome identificador da chave de API (ex: Produção, Teste)")

class RespostaChaveAPISchema(BaseModel):
    id: uuid.UUID
    aplicacao_id: uuid.UUID
    nome: str
    revogada: bool
    criado_em: Any

    model_config = ConfigDict(from_attributes=True)

class RespostaCriacaoChaveSchema(RespostaChaveAPISchema):
    """Schema específico para a criação que inclui a chave plana (exibida apenas uma vez)."""
    chave_api: str
    mensagem: str = "Guarde esta chave em local seguro. Ela não será exibida novamente."

class CriarModeloEmbeddingSchema(BaseModel):
    id: str = Field(..., max_length=50, description="Identificador único (ex: bge-m3, text-embedding-3-small)")
    nome: str = Field(..., max_length=100, description="Nome amigável do modelo")
    provedor: str = Field(..., max_length=50, description="Provedor (ex: OpenAI, BAAI, Google)")
    dimensoes: Literal[512, 768, 1024, 1536, 3072] = Field(
        ..., description="Dimensão suportada pelo armazenamento vetorial"
    )
    identificador_repositorio: Optional[str] = Field(None, max_length=255, description="Repositório Hugging Face opcional")
    metrica_distancia: MetricaDistanciaSuportada = MetricaDistancia.COSINE

class RespostaModeloEmbeddingSchema(BaseModel):
    id: str
    nome: str
    provedor: str
    dimensoes: int
    identificador_repositorio: Optional[str] = None
    metrica_distancia: MetricaDistancia
    ativo: bool
    criado_em: Any

    model_config = ConfigDict(from_attributes=True)
    
class AtualizarModeloEmbeddingSchema(BaseModel):
    nome: Optional[str] = Field(None, max_length=100, description="Novo nome amigável do modelo")
    provedor: Optional[str] = Field(None, max_length=50, description="Novo provedor")
    identificador_repositorio: Optional[str] = Field(None, max_length=255, description="Novo repositório Hugging Face")
    metrica_distancia: Optional[MetricaDistanciaSuportada] = Field(
        None, description="Métrica de distância suportada: cosine"
    )
    ativo: Optional[bool] = Field(None, description="Situação do modelo (ativo ou não)")







class CriarColecaoPayloadSchema(BaseModel):
    modelo_embedding_id: str = Field(..., description="ID do modelo de embedding (ex: bge-m3)")
    nome: str = Field(..., max_length=100)
    tipo_armazenamento: TipoArmazenamento = TipoArmazenamento.VECTOR
    configuracao_embedding: Optional[ConfigEmbeddingDict] = Field(default_factory=dict)
    metadados: Optional[MetadataDict] = Field(default_factory=dict)
    publica: bool = False

class CriarColecaoSchema(CriarColecaoPayloadSchema):
    aplicacao_id: uuid.UUID

class AtualizarColecaoSchema(BaseModel):
    """Schema para atualização parcial (PATCH). Todos os campos são opcionais."""
    nome: Optional[str] = Field(None, max_length=100)
    configuracao_embedding: Optional[ConfigEmbeddingDict] = None
    metadados: Optional[MetadataDict] = None
    publica: Optional[bool] = None

class RespostaColecaoSchema(BaseModel):
    id: uuid.UUID
    aplicacao_id: uuid.UUID
    modelo_embedding_id: str
    nome: str
    tipo_armazenamento: TipoArmazenamento
    configuracao_embedding: MetadataDict
    metadados: MetadataDict
    publica: bool
    criado_em: Any

    model_config = ConfigDict(from_attributes=True)

class InserirEmbeddingSchema(BaseModel):
    colecao_id: uuid.UUID
    texto_referencia: str = Field(
        ...,
        min_length=1,
        max_length=LIMITE_MAXIMO_TEXTO,
        description="Texto original usado para gerar o hash de deduplicação",
    )
    vetor: List[ValorVetor] = Field(
        ...,
        min_length=1,
        max_length=LIMITE_MAXIMO_DIMENSAO_VETOR,
    )
    metadados: Optional[MetadataDict] = Field(default_factory=dict)

    @field_validator("texto_referencia")
    @classmethod
    def validar_texto_referencia(cls, texto: str) -> str:
        if not texto.strip():
            raise ValueError("texto_referencia não pode conter apenas espaços.")
        return texto

class RemoverEmbeddingSchema(BaseModel):
    colecao_id: uuid.UUID

class RequisicaoBuscaSchema(BaseModel):
    colecoes_nomes_ou_ids: List[IdentificadorColecao] = Field(
        ..., min_length=1, max_length=LIMITE_MAXIMO_COLECOES_BUSCA
    )
    texto_consulta: str = Field(
        ..., min_length=1, max_length=LIMITE_MAXIMO_TEXTO
    )
    limite: int = Field(default=10, ge=1, le=100)
    filtro_metadados: Optional[Dict[str, Any]] = None

    @field_validator("texto_consulta")
    @classmethod
    def validar_texto_consulta(cls, texto: str) -> str:
        if not texto.strip():
            raise ValueError("texto_consulta não pode conter apenas espaços.")
        return texto

    @field_validator("colecoes_nomes_ou_ids")
    @classmethod
    def validar_identificadores_colecoes(
        cls, colecoes: List[str]
    ) -> List[str]:
        if any(not colecao.strip() for colecao in colecoes):
            raise ValueError("Os nomes ou IDs das coleções não podem ser vazios.")
        return colecoes

class ResultadoBuscaSchema(TypedDict):
    id: str
    colecao_id: str
    conteudo_hash: str
    distancia: float
    metadados: Dict[str, Any]
    criado_em: datetime