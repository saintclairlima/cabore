import hashlib
import uuid
from enum import Enum
from datetime import datetime
from typing import Optional, Dict, Any, List
from sqlalchemy import (
    Enum as SQLEnum,
    String,
    BigInteger,
    ForeignKey,
    UniqueConstraint,
    func,
    Index,
    Boolean,
    Integer,
    Numeric,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship
from pgvector.sqlalchemy import Vector, HALFVEC
from app.database import Base
from app.models.tipos import ConfigEmbeddingDict, MetadataDict

# Definição dos Enums
class TipoArmazenamento(str, Enum):
    VECTOR = "vector"
    HALFVEC = "halfvec"


class MetricaDistancia(str, Enum):
    COSINE = "cosine"
    L2 = "l2"
    IP = "ip"


# Aplicações (Tenants)
class Aplicacao(Base):
    __tablename__ = "aplicacoes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    nome: Mapped[str] = mapped_column(String(100), nullable=False)
    ativa: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    criado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )

    chaves_api: Mapped[List["ChaveAPI"]] = relationship(
        back_populates="aplicacao", cascade="all, delete-orphan", lazy="selectin"
    )
    colecoes: Mapped[List["Colecao"]] = relationship(
        back_populates="aplicacao", cascade="all, delete-orphan", lazy="selectin"
    )

    __table_args__ = (
        Index(
            "uq_aplicacao_nome_ativo",
            func.lower(nome),
            unique=True,
            postgresql_where=(ativa == True),
        ),
    )


# Autenticação (Chaves de API)
class ChaveAPI(Base):
    __tablename__ = "chaves_api"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    aplicacao_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("aplicacoes.id", ondelete="CASCADE"),
        nullable=False,
    )
    chave_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    nome: Mapped[str] = mapped_column(String(100), nullable=False)
    revogada: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    criado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )

    aplicacao: Mapped["Aplicacao"] = relationship(back_populates="chaves_api")

    __table_args__ = (
        Index(
            "uq_chave_nome_por_app",
            aplicacao_id,
            func.lower(nome),
            unique=True,
        ),
    )


# Modelos de Embedding Supostos
class ModeloEmbedding(Base):
    __tablename__ = "modelos_embedding"

    # identificador do modelo ('text-embedding-3-small', 'bge-m3', etc)
    id: Mapped[str] = mapped_column(
        String(50), primary_key=True
    )

    # nome mais user-friendly (pode ser uam variação do id: BGE m3, Embedding 3 - OpenAi, etc...)
    nome: Mapped[str] = mapped_column(String(100), nullable=False)
    
    # nome da origem do modelo (Google, OpenAi, BAAI, etc...)
    provedor: Mapped[str] = mapped_column(String(50), nullable=False)
    dimensoes: Mapped[int] = mapped_column(Integer, nullable=False)

    # identificador do repositório no Hugging Face
    identificador_repositorio: Mapped[str] = mapped_column(String(255), nullable=True)
    metrica_distancia: Mapped[MetricaDistancia] = mapped_column(
        SQLEnum(MetricaDistancia, native_enum=False),
        nullable=False,
        default=MetricaDistancia.COSINE,
        server_default="COSINE",
    )
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    criado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )

    # Relacionamento reverso opcional se quiser acessar os embeddings de um modelo diretamente
    colecoes: Mapped[List["Colecao"]] = relationship(back_populates="modelo_embedding")


# Coleções Lógicas
class Colecao(Base):
    __tablename__ = "colecoes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    nome: Mapped[str] = mapped_column(String(100), nullable=False)
    aplicacao_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("aplicacoes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    modelo_embedding_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("modelos_embedding.id"), nullable=False
    )
    tipo_armazenamento: Mapped[TipoArmazenamento] = mapped_column(
        SQLEnum(TipoArmazenamento, native_enum=False),
        default=TipoArmazenamento.VECTOR,
        nullable=False,
    )

    # Configurações utilizadas na geração/processamento dos embeddings.
    # A aplicação deve validar a estrutura deste JSON (por exemplo, com Pydantic).
    configuracao_embedding: Mapped[ConfigEmbeddingDict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )

    metadados: Mapped[MetadataDict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )
    publica: Mapped[bool] = mapped_column(Boolean, default=False)
    criado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )

    aplicacao: Mapped["Aplicacao"] = relationship(back_populates="colecoes")
    modelo_embedding: Mapped["ModeloEmbedding"] = relationship(
        back_populates="colecoes"
    )

    __table_args__ = (
        # Permite que tabelas filhas façam Foreign Key referenciando (id, modelo_embedding_id)
        UniqueConstraint("id", "modelo_embedding_id", name="uq_colecao_id_modelo"),
        # Garante que só haja uma coleção com o mesmo nome por aplicação
        Index(
            "uq_colecao_nome_por_aplicacao",
            aplicacao_id,
            func.lower(nome),
            unique=True,
        ),
    )


class EmbeddingBase(Base):
    __abstract__ = (
        True  # Impede o SQLAlchemy de criar uma tabela física para esta classe
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    colecao_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("colecoes.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    conteudo_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    metadados: Mapped[Dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )
    criado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )

    @staticmethod
    def gerar_hash(texto: str) -> str:
        """Gera um hash SHA-256 do texto limpo/normalizado."""
        texto_normalizado = texto.strip().lower()
        return hashlib.sha256(texto_normalizado.encode("utf-8")).hexdigest()

    @classmethod
    def indices_padrao(cls, op_hnsw: str):
        prefixo = cls.__tablename__
        return (
            Index(f"idx_{prefixo}_colecao", "colecao_id"),
            Index(
                f"idx_{prefixo}_hnsw",
                "embedding",
                postgresql_using="hnsw",
                postgresql_ops={"embedding": op_hnsw},
            ),
            Index(
                f"idx_{prefixo}_metadados",
                "metadados",
                postgresql_using="gin",
                postgresql_ops={"metadados": "jsonb_path_ops"},
            ),
            UniqueConstraint(
                "colecao_id", "conteudo_hash", name=f"uq_{prefixo}_colecao_hash"
            ),
        )


# Obs: o tipo de coluna VECTOR (32-bit float / real) só aceita até 2.000 valores.
#      para valores maiores, deve ser usado HALFVEC (16-bit float / half)

# Intermediária para tipos Float32 (VECTOR)
class EmbeddingVectorBase(EmbeddingBase):
    __abstract__ = True

    @declared_attr.directive
    def __table_args__(cls):
        return cls.indices_padrao(op_hnsw="vector_cosine_ops")


# Intermediária para tipos Float16 (HALFVEC)
class EmbeddingHalfVectorBase(EmbeddingBase):
    __abstract__ = True

    @declared_attr.directive
    def __table_args__(cls):
        return cls.indices_padrao(op_hnsw="halfvec_cosine_ops")


class Embedding1024(EmbeddingVectorBase):
    __tablename__ = "embeddings_1024"

    vetor: Mapped[list[float]] = mapped_column(
        "embedding", Vector(1024), nullable=False
    )


# Tabela Vector de 1536 dimensões
class Embedding1536(EmbeddingVectorBase):
    __tablename__ = "embeddings_1536"

    vetor: Mapped[list[float]] = mapped_column(
        "embedding", Vector(1536), nullable=False
    )


# Tabela Vector de 512 dimensões
class Embedding512(EmbeddingVectorBase):
    __tablename__ = "embeddings_512"

    vetor: Mapped[list[float]] = mapped_column("embedding", Vector(512), nullable=False)


# Tabela Vector de 768 dimensões
class Embedding768(EmbeddingVectorBase):
    __tablename__ = "embeddings_768"

    vetor: Mapped[list[float]] = mapped_column("embedding", Vector(768), nullable=False)


# Tabela HalfVec de 3072 dimensões
class EmbeddingHalfVec3072(EmbeddingHalfVectorBase):
    __tablename__ = "embeddings_halfvec_3072"

    vetor: Mapped[list[float]] = mapped_column(
        "embedding", HALFVEC(3072), nullable=False
    )


# Auditoria de Recomendações e Requisições
class AuditoriaRequisicao(Base):
    __tablename__ = "auditoria_requisicoes"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    chave_api_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("chaves_api.id"), nullable=True
    )
    aplicacao_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        ForeignKey("aplicacoes.id", ondelete="SET NULL"), 
        nullable=True
    )
    colecao_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    operacao: Mapped[str] = mapped_column(
        String(30), nullable=False
    )  # 'gerar', 'buscar_filtrada', 'buscar_global'
    tempo_execucao_ms: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)
    quantidade_resultados: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    criado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )
