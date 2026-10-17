import asyncio
import logging
from typing import Dict, Any, List, Optional
import numpy as np
from sentence_transformers import SentenceTransformer
from app.config import configuracoes

logger = logging.getLogger("caboré.motor_inferencia")

class MotorInferenciaService:
    def __init__(self):
        # Cache para armazenar os modelos carregados em memória
        self._cache_modelos: Dict[str, SentenceTransformer] = {}
        # Lock global/por modelo para evitar carregamento duplicado simultâneo (Race Condition)
        self._lock_carregamento = asyncio.Lock()
        # dispositivo em que será feita a inferência (cpu ou cuda), definido no .env/config.py
        self._dispositivo = configuracoes.DISPOSITIVO

    async def _carregar_modelo(self, modelo_id: str, repositorio: Optional[str] = None) -> SentenceTransformer:
        """
        Faz o lazy load seguro de um modelo de embedding com proteção contra concorrência.
        """
        # Verificação rápida em memória sem bloquear
        if modelo_id in self._cache_modelos:
            return self._cache_modelos[modelo_id]

        async with self._lock_carregamento:
            # Dupla verificação após adquirir o lock
            if modelo_id in self._cache_modelos:
                return self._cache_modelos[modelo_id]

            logger.info(f"Carregando modelo de embedding '{modelo_id}' (Repositório: {repositorio or modelo_id})...")
            
            caminho_ou_repo = repositorio if repositorio else modelo_id
            
            # O carregamento do modelo é bloqueante (disco/rede/IO), executado em thread separada
            def _load():
                return SentenceTransformer(caminho_ou_repo, device=self._dispositivo)

            modelo = await asyncio.to_thread(_load)
            
            self._cache_modelos[modelo_id] = modelo
            logger.info(f"Modelo '{modelo_id}' carregado com sucesso para a memória.")
            return modelo

    async def gerar_vetor(
        matriz_self,
        texto: str, 
        modelo_id: str, 
        repositorio: Optional[str] = None
    ) -> List[float]:
        """
        Gera a representação vetorial para um único texto de forma assíncrona.
        """
        # Para referenciar a instância corretamente dentro do método:
        # (caso prefira instanciar como objeto global)
        resultado = await motor_inferencia.gerar_vetores_lote([texto], modelo_id, repositorio)
        return resultado[0] if resultado else []

    async def gerar_vetores_lote(
        self, 
        textos: List[str], 
        modelo_id: str, 
        repositorio: Optional[str] = None
    ) -> List[List[float]]:
        """
        Gera vetores para um lote de textos de forma concorrente e otimizada.
        Ideal para inserções em massa e buscas.
        """
        if not textos:
            return []

        modelo = await self._carregar_modelo(modelo_id, repositorio)

        def _encode():
            # encode do sentence-transformers aceita listas nativas e otimiza lotes internamente
            # normalize_embeddings=True é excelente para métrica de Cosseno
            embeddings = modelo.encode(
                textos, 
                normalize_embeddings=True, 
                show_progress_bar=False,
                convert_to_numpy=True
            )
            return embeddings.tolist()

        # Executa a inferência pesada em uma thread separada para não travar o event loop do FastAPI
        vetores = await asyncio.to_thread(_encode)
        return vetores

    def limpar_cache(self, modelo_id: Optional[str] = None):
        """Libera modelos da memória RAM/VRAM caso necessário."""
        if modelo_id:
            if modelo_id in self._cache_modelos:
                del self._cache_modelos[modelo_id]
                logger.info(f"Modelo '{modelo_id}' removido do cache de memória.")
        else:
            self._cache_modelos.clear()
            logger.info("Cache de modelos limpo completamente.")

# Instância singleton global pronta para injeção ou importação direta
motor_inferencia = MotorInferenciaService()