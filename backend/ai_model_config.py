"""Modelo de Claude configurable por tarea, editable desde el panel de admin."""
import logging
import time
from datetime import datetime, timezone
from typing import Dict, Optional

logger = logging.getLogger(__name__)

PROVIDER = "anthropic"
CACHE_TTL_SECONDS = 60

# Modelos de Claude disponibles (de más potente a más económico)
AVAILABLE_MODELS = [
    {"id": "claude-opus-5-5", "label": "Claude Opus 5.5", "tier": "máxima calidad"},
    {"id": "claude-sonnet-5-5", "label": "Claude Sonnet 5.5", "tier": "recomendado"},
    {"id": "claude-sonnet-5", "label": "Claude Sonnet 5", "tier": "equilibrado"},
    {"id": "claude-sonnet-4-6", "label": "Claude Sonnet 4.6", "tier": "equilibrado"},
    {"id": "claude-sonnet-4-5-20250929", "label": "Claude Sonnet 4.5", "tier": "anterior"},
    {"id": "claude-haiku-4-5-20251001", "label": "Claude Haiku 4.5", "tier": "rápido y económico"},
]
MODEL_IDS = {m["id"] for m in AVAILABLE_MODELS}

# Reparto equilibrado: potencia donde se nota, economía en volumen
TASKS = {
    "cv_parsing": {
        "label": "Parseo de CV",
        "description": "Extrae datos estructurados de cada CV que se carga",
        "default": "claude-sonnet-5-5",
    },
    "classification": {
        "label": "Clasificación de candidatos",
        "description": "Industria, área/subárea y seniority",
        "default": "claude-sonnet-5-5",
    },
    "summary": {
        "label": "Resumen ejecutivo",
        "description": "Resumen corto del perfil (alto volumen)",
        "default": "claude-haiku-4-5-20251001",
    },
    "job_parsing": {
        "label": "Parseo de vacante",
        "description": "Lectura de la descripción de puesto",
        "default": "claude-sonnet-5-5",
    },
    "text_matching": {
        "label": "Match textual candidato-vacante",
        "description": "Comparación cualitativa de un perfil contra una vacante",
        "default": "claude-sonnet-5-5",
    },
    "match_review": {
        "label": "Análisis IA del match",
        "description": "Revisión experta del ranking del motor para una vacante",
        "default": "claude-opus-5-5",
    },
}


class AIModelConfig:
    """Lee y guarda el modelo por tarea. Si no hay base ligada, usa los valores por defecto."""

    def __init__(self):
        self._db = None
        self._cache: Dict[str, str] = {}
        self._cached_at = 0.0

    def bind(self, db):
        self._db = db

    def defaults(self) -> Dict[str, str]:
        return {task: meta["default"] for task, meta in TASKS.items()}

    async def _load(self) -> Dict[str, str]:
        if self._cache and (time.time() - self._cached_at) < CACHE_TTL_SECONDS:
            return self._cache
        models = self.defaults()
        if self._db is not None:
            try:
                doc = await self._db.ai_model_config.find_one({"id": "claude"}, {"_id": 0, "models": 1})
                for task, model in ((doc or {}).get("models") or {}).items():
                    if task in TASKS and model in MODEL_IDS:
                        models[task] = model
            except Exception as e:
                logger.warning("No se pudo leer ai_model_config: %s", e)
        self._cache = models
        self._cached_at = time.time()
        return models

    async def get_model(self, task: str) -> str:
        models = await self._load()
        return models.get(task) or TASKS[task]["default"]

    async def get_all(self) -> Dict[str, str]:
        return dict(await self._load())

    async def set_models(self, models: Dict[str, str], actor: Optional[str] = None) -> Dict[str, str]:
        invalid = {task: model for task, model in models.items()
                   if task not in TASKS or model not in MODEL_IDS}
        if invalid:
            raise ValueError(f"Tarea o modelo no válido: {invalid}")
        current = await self.get_all()
        current.update(models)
        await self._db.ai_model_config.update_one(
            {"id": "claude"},
            {"$set": {"models": current, "updated_at": datetime.now(timezone.utc).isoformat(),
                      "updated_by": actor}},
            upsert=True,
        )
        self._cache = {}
        self._cached_at = 0.0
        return current


ai_model_config = AIModelConfig()
