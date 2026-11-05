from enum import Enum

from pydantic import Field
from typing import Annotated, Any, Dict, List, Union

JsonValue = Union[str, int, float, bool, None, Dict[str, Any], List[Any]]
MetadataDict = Dict[str, JsonValue]
ConfigEmbeddingDict = Dict[str, JsonValue]
ValorVetor = Annotated[float, Field(strict=True, allow_inf_nan=False)]
IdentificadorColecao = Annotated[str, Field(min_length=1, max_length=100)]

class EstrategiaCombinacao(str, Enum):
    NONE = "none"
    RRF = "rrf"