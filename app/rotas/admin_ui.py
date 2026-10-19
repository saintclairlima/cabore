import os
from fastapi import APIRouter
from fastapi.responses import FileResponse

router = APIRouter(prefix="/admin", tags=["Painel Administrativo"])

# Define o caminho absoluto para o arquivo HTML com base na localização deste arquivo Python
CAMINHO_TEMPLATE = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "templates", "admin.html")
)

@router.get("/", response_class=FileResponse)
async def painel_admin():
    """Retorna o arquivo HTML estático do painel administrativo."""
    if not os.path.exists(CAMINHO_TEMPLATE):
        return {"erro": "Arquivo de template admin.html não encontrado."}, 404
        
    return FileResponse(CAMINHO_TEMPLATE)