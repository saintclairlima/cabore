from fastapi import APIRouter

from app.rotas import admin_ui, aplicacoes, colecoes, embeddings, modelos

router = APIRouter(prefix="/v1", tags=["Caboré API v1"])

router.include_router(admin_ui.router)
router.include_router(aplicacoes.router)
router.include_router(modelos.router)
router.include_router(colecoes.router)
router.include_router(embeddings.router)