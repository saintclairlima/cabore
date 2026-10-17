import secrets

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import configuracoes
from app.database import obter_sessao_banco
from app.models.modelos import Aplicacao
from app.services import aplicacao_service

admin_key_scheme = APIKeyHeader(
    name="X-Admin-Key", 
    description="Chave Master de Administrador do Sistema",
    scheme_name="AdminKeyAuth"
)

api_key_scheme = APIKeyHeader(
    name="X-API-Key", 
    description="Chave de API do Tenant (formato: cb_...)",
    scheme_name="TenantKeyAuth"
)

async def verificar_admin_master(
    x_admin_key: str = Security(admin_key_scheme)
) -> bool:
    """
    Valida a chave master de admin enviada no header.
    """
    admin_key_sistema = configuracoes.ADMIN_KEY.get_secret_value()
    
    if not secrets.compare_digest(x_admin_key, admin_key_sistema):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso negado. Chave de Administrador inválida.",
        )
    return True

async def obter_aplicacao_atual(
    x_api_key: str = Security(api_key_scheme),
    sessao: AsyncSession = Depends(obter_sessao_banco),
) -> Aplicacao:
    """Valida a chave de API do tenant enviada no header."""
    aplicacao = await aplicacao_service.validar_chave_api(sessao, x_api_key)
    if not aplicacao:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Chave de API inválida, expirada ou revogada.",
        )
    return aplicacao