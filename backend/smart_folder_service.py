"""
Smart Folder Service
====================
Gestión de Smart Folders - Vistas dinámicas de candidatos.
Los folders actúan como filtros predefinidos que se ejecutan en tiempo real.
"""

import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional

from models import (
    User, UserRole, SmartFolder, SmartFolderCreate, SmartFolderUpdate,
    FolderType, FolderCategory, FolderCriteria, SeniorityFilter, FolderAnalytics
)

logger = logging.getLogger(__name__)

# Jerarquía de seniority (índice = nivel)
SENIORITY_HIERARCHY = [
    "intern", "junior", "mid", "senior", "manager",
    "senior_manager", "director", "vp", "c_level", "ceo"
]

# Folders del sistema predefinidos
SYSTEM_FOLDERS = [
    # === VERTICALES ESTRATÉGICOS ===
    {
        "id": "sys_cfo_finance",
        "name": "CFO & Finanzas",
        "description": "Directivos y ejecutivos del área financiera",
        "icon": "landmark",
        "color": "emerald",
        "folder_category": "vertical",
        "criteria": {
            "functional_area": ["finance", "accounting"],
            "seniority": {"mode": "range", "min_level": "director", "max_level": "ceo"}
        },
        "sort_order": 1
    },
    {
        "id": "sys_operations",
        "name": "Operaciones",
        "description": "Líderes de operaciones y supply chain",
        "icon": "settings",
        "color": "blue",
        "folder_category": "vertical",
        "criteria": {
            "functional_area": ["operations", "supply_chain"],
            "seniority": {"mode": "range", "min_level": "manager", "max_level": "ceo"}
        },
        "sort_order": 2
    },
    {
        "id": "sys_commercial",
        "name": "Comercial & Ventas",
        "description": "Ejecutivos comerciales y de ventas",
        "icon": "trending-up",
        "color": "orange",
        "folder_category": "vertical",
        "criteria": {
            "functional_area": ["sales", "business_development"],
            "seniority": {"mode": "range", "min_level": "manager", "max_level": "ceo"}
        },
        "sort_order": 3
    },
    {
        "id": "sys_marketing",
        "name": "Marketing",
        "description": "Líderes de marketing y comunicación",
        "icon": "megaphone",
        "color": "pink",
        "folder_category": "vertical",
        "criteria": {
            "functional_area": ["marketing"],
            "seniority": {"mode": "range", "min_level": "senior", "max_level": "ceo"}
        },
        "sort_order": 4
    },
    {
        "id": "sys_hr",
        "name": "Recursos Humanos",
        "description": "Ejecutivos de capital humano",
        "icon": "users",
        "color": "purple",
        "folder_category": "vertical",
        "criteria": {
            "functional_area": ["hr"],
            "seniority": {"mode": "range", "min_level": "manager", "max_level": "ceo"}
        },
        "sort_order": 5
    },
    {
        "id": "sys_it",
        "name": "IT & Tecnología",
        "description": "Líderes tecnológicos y digitales",
        "icon": "cpu",
        "color": "cyan",
        "folder_category": "vertical",
        "criteria": {
            "functional_area": ["it_technology"],
            "seniority": {"mode": "range", "min_level": "senior", "max_level": "ceo"}
        },
        "sort_order": 6
    },
    {
        "id": "sys_legal",
        "name": "Legal",
        "description": "Directivos legales y de cumplimiento",
        "icon": "scale",
        "color": "slate",
        "folder_category": "vertical",
        "criteria": {
            "functional_area": ["legal"],
            "seniority": {"mode": "range", "min_level": "manager", "max_level": "ceo"}
        },
        "sort_order": 7
    },
    {
        "id": "sys_supply_chain",
        "name": "Supply Chain",
        "description": "Líderes de cadena de suministro y logística",
        "icon": "truck",
        "color": "amber",
        "folder_category": "vertical",
        "criteria": {
            "functional_area": ["supply_chain", "logistics"],
            "seniority": {"mode": "range", "min_level": "manager", "max_level": "ceo"}
        },
        "sort_order": 8
    },
    {
        "id": "sys_general_management",
        "name": "General Management",
        "description": "CEOs, Country Managers y Directores Generales",
        "icon": "briefcase",
        "color": "indigo",
        "folder_category": "vertical",
        "criteria": {
            "functional_area": ["general_management"],
            "seniority": {"mode": "range", "min_level": "director", "max_level": "ceo"}
        },
        "sort_order": 9
    },
    
    # === FOLDERS DE PROCESO ===
    {
        "id": "sys_ready_to_send",
        "name": "Listos para Enviar",
        "description": "Candidatos validados y listos para presentar a cliente",
        "icon": "send",
        "color": "green",
        "folder_category": "process",
        "criteria": {
            "candidate_status": ["ready_to_send"]
        },
        "sort_order": 101
    },
    {
        "id": "sys_top_active",
        "name": "Top Candidatos Activos",
        "description": "Candidatos calificados con alta compatibilidad",
        "icon": "star",
        "color": "yellow",
        "folder_category": "process",
        "criteria": {
            "candidate_status": ["qualified", "ready_to_send"],
            "min_match_score": 75
        },
        "sort_order": 102
    },
    {
        "id": "sys_in_evaluation",
        "name": "En Evaluación",
        "description": "Candidatos en revisión o calificados pendientes",
        "icon": "clipboard-check",
        "color": "blue",
        "folder_category": "process",
        "criteria": {
            "candidate_status": ["reviewing", "qualified"]
        },
        "sort_order": 103
    },
    {
        "id": "sys_recently_added",
        "name": "Recién Ingresados",
        "description": "CVs nuevos sin revisar",
        "icon": "plus-circle",
        "color": "teal",
        "folder_category": "process",
        "criteria": {
            "candidate_status": ["new"]
        },
        "sort_order": 104
    }
]


class SmartFolderService:
    """Servicio de gestión de Smart Folders"""
    
    def __init__(self, db):
        self.db = db
    
    # ========== INITIALIZATION ==========
    
    async def initialize_system_folders(self):
        """Inicializa los folders del sistema si no existen"""
        for folder_data in SYSTEM_FOLDERS:
            existing = await self.db.smart_folders.find_one({"id": folder_data["id"]})
            if not existing:
                folder_doc = {
                    "id": folder_data["id"],
                    "name": folder_data["name"],
                    "description": folder_data["description"],
                    "icon": folder_data["icon"],
                    "color": folder_data["color"],
                    "folder_type": FolderType.SYSTEM.value,
                    "folder_category": folder_data["folder_category"],
                    "criteria": folder_data["criteria"],
                    "created_by": None,
                    "sort_order": folder_data["sort_order"],
                    "is_pinned": False,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }
                await self.db.smart_folders.insert_one(folder_doc)
                logger.info(f"Created system folder: {folder_data['name']}")
        
        logger.info(f"System folders initialized: {len(SYSTEM_FOLDERS)} folders")
    
    # ========== CRUD OPERATIONS ==========
    
    async def list_folders(self, user: User, include_counts: bool = True) -> List[Dict[str, Any]]:
        """Lista todos los folders visibles para el usuario"""
        
        # Folders del sistema + folders del usuario
        query = {
            "$or": [
                {"folder_type": FolderType.SYSTEM.value},
                {"created_by": user.id}
            ]
        }
        
        folders = await self.db.smart_folders.find(
            query, {"_id": 0}
        ).sort("sort_order", 1).to_list(100)
        
        # Agregar conteos si se solicita
        if include_counts:
            for folder in folders:
                folder["candidate_count"] = await self._count_candidates(folder, user)
                
                # Agregar analytics básicas
                analytics = await self.db.folder_analytics.find_one(
                    {"folder_id": folder["id"]}, {"_id": 0}
                )
                folder["analytics"] = analytics
        
        return folders
    
    async def get_folder(self, folder_id: str, user: User) -> Optional[Dict[str, Any]]:
        """Obtiene un folder por ID"""
        folder = await self.db.smart_folders.find_one(
            {"id": folder_id}, {"_id": 0}
        )
        
        if not folder:
            return None
        
        # Verificar acceso
        if folder["folder_type"] == FolderType.USER.value:
            if folder.get("created_by") != user.id:
                return None  # No tiene acceso
        
        return folder
    
    async def create_folder(self, data: SmartFolderCreate, user: User) -> Dict[str, Any]:
        """Crea un nuevo folder de usuario"""
        
        folder_id = str(uuid.uuid4())
        
        folder_doc = {
            "id": folder_id,
            "name": data.name,
            "description": data.description,
            "icon": data.icon,
            "color": data.color,
            "folder_type": FolderType.USER.value,
            "folder_category": data.folder_category.value,
            "criteria": data.criteria.model_dump(),
            "created_by": user.id,
            "sort_order": 200,  # Folders de usuario después de sistema
            "is_pinned": data.is_pinned,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
        await self.db.smart_folders.insert_one(folder_doc)
        
        # Inicializar analytics
        await self.db.folder_analytics.insert_one({
            "folder_id": folder_id,
            "total_views": 0,
            "views_last_30_days": 0,
            "total_exports": 0,
            "candidates_selected": 0,
            "last_accessed": None
        })
        
        logger.info(f"Created user folder: {data.name} by {user.email}")
        
        folder_doc.pop("_id", None)
        return folder_doc
    
    async def update_folder(
        self, 
        folder_id: str, 
        data: SmartFolderUpdate, 
        user: User
    ) -> Dict[str, Any]:
        """Actualiza un folder de usuario"""
        
        folder = await self.get_folder(folder_id, user)
        if not folder:
            raise ValueError("Folder no encontrado")
        
        if folder["folder_type"] == FolderType.SYSTEM.value:
            raise PermissionError("No se pueden modificar folders del sistema")
        
        if folder.get("created_by") != user.id:
            raise PermissionError("No tienes permisos para editar este folder")
        
        update_data = {}
        if data.name is not None:
            update_data["name"] = data.name
        if data.description is not None:
            update_data["description"] = data.description
        if data.icon is not None:
            update_data["icon"] = data.icon
        if data.color is not None:
            update_data["color"] = data.color
        if data.criteria is not None:
            update_data["criteria"] = data.criteria.model_dump()
        if data.is_pinned is not None:
            update_data["is_pinned"] = data.is_pinned
        if data.sort_order is not None:
            update_data["sort_order"] = data.sort_order
        
        update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
        
        await self.db.smart_folders.update_one(
            {"id": folder_id},
            {"$set": update_data}
        )
        
        return await self.get_folder(folder_id, user)
    
    async def delete_folder(self, folder_id: str, user: User) -> bool:
        """Elimina un folder de usuario"""
        
        folder = await self.get_folder(folder_id, user)
        if not folder:
            raise ValueError("Folder no encontrado")
        
        if folder["folder_type"] == FolderType.SYSTEM.value:
            raise PermissionError("No se pueden eliminar folders del sistema")
        
        if folder.get("created_by") != user.id:
            raise PermissionError("No tienes permisos para eliminar este folder")
        
        await self.db.smart_folders.delete_one({"id": folder_id})
        await self.db.folder_analytics.delete_one({"folder_id": folder_id})
        
        logger.info(f"Deleted folder: {folder['name']} by {user.email}")
        return True
    
    # ========== FOLDER CANDIDATES ==========
    
    async def get_folder_candidates(
        self, 
        folder_id: str, 
        user: User,
        skip: int = 0,
        limit: int = 50,
        sort_by: str = "match_score"
    ) -> Dict[str, Any]:
        """Obtiene los candidatos que matchean los criterios del folder"""
        
        folder = await self.get_folder(folder_id, user)
        if not folder:
            raise ValueError("Folder no encontrado")
        
        # Construir query desde criterios
        query = self._build_query(folder.get("criteria", {}), user)
        
        # Campos a retornar
        projection = {
            "_id": 0,
            "embedding": 0
        }
        
        # Determinar ordenamiento
        sort_field = "created_at"
        sort_order = -1
        if sort_by == "match_score":
            sort_field = "match_score"
        elif sort_by == "name":
            sort_field = "full_name"
            sort_order = 1
        elif sort_by == "updated":
            sort_field = "updated_at"
        
        # Ejecutar query
        candidates = await self.db.candidates.find(
            query, projection
        ).sort(sort_field, sort_order).skip(skip).limit(limit).to_list(limit)
        
        total = await self.db.candidates.count_documents(query)
        
        # Registrar acceso
        await self._record_access(folder_id, user.id, "view")
        
        return {
            "folder": folder,
            "candidates": candidates,
            "total": total,
            "skip": skip,
            "limit": limit
        }
    
    async def _count_candidates(self, folder: Dict, user: User) -> int:
        """Cuenta candidatos que matchean el folder"""
        query = self._build_query(folder.get("criteria", {}), user)
        return await self.db.candidates.count_documents(query)
    
    def _build_query(self, criteria: Dict, user: User) -> Dict:
        """Construye MongoDB query desde criterios del folder"""
        
        query = {}
        conditions = []
        
        # Área funcional
        if criteria.get("functional_area"):
            conditions.append({
                "functional_area": {"$in": criteria["functional_area"]}
            })
        
        # Industria
        if criteria.get("industry"):
            conditions.append({
                "industry": {"$in": criteria["industry"]}
            })
        
        # Seniority
        seniority = criteria.get("seniority")
        if seniority:
            if isinstance(seniority, dict):
                mode = seniority.get("mode", "range")
                if mode == "exact" and seniority.get("exact_levels"):
                    conditions.append({
                        "seniority": {"$in": seniority["exact_levels"]}
                    })
                elif mode == "range":
                    min_level = seniority.get("min_level")
                    max_level = seniority.get("max_level")
                    
                    if min_level or max_level:
                        min_idx = SENIORITY_HIERARCHY.index(min_level) if min_level else 0
                        max_idx = SENIORITY_HIERARCHY.index(max_level) if max_level else len(SENIORITY_HIERARCHY) - 1
                        
                        valid_levels = SENIORITY_HIERARCHY[min_idx:max_idx + 1]
                        conditions.append({
                            "seniority": {"$in": valid_levels}
                        })
        
        # Estado del candidato
        if criteria.get("candidate_status"):
            conditions.append({
                "status": {"$in": criteria["candidate_status"]}
            })
        
        # Actividad reciente
        if criteria.get("last_activity_days"):
            days = criteria["last_activity_days"]
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            conditions.append({
                "$or": [
                    {"updated_at": {"$gte": cutoff.isoformat()}},
                    {"last_activity": {"$gte": cutoff.isoformat()}}
                ]
            })
        
        # Score mínimo
        if criteria.get("min_match_score"):
            conditions.append({
                "match_score": {"$gte": criteria["min_match_score"]}
            })
        
        # Creados recientemente
        if criteria.get("created_last_days"):
            days = criteria["created_last_days"]
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            conditions.append({
                "created_at": {"$gte": cutoff.isoformat()}
            })
        
        # Filtro de asignación
        assignment_filter = criteria.get("assignment_filter", "all")
        if assignment_filter == "mine":
            # Solo candidatos asignados al usuario actual
            # Esto requiere hacer join con assignments
            pass  # Se implementará con pipeline de agregación
        elif assignment_filter == "unassigned":
            # Solo candidatos sin asignar
            pass
        
        # Combinar condiciones
        if conditions:
            query["$and"] = conditions
        
        return query
    
    # ========== ANALYTICS ==========
    
    async def _record_access(self, folder_id: str, user_id: str, action: str):
        """Registra un acceso al folder"""
        now = datetime.now(timezone.utc)
        
        # Actualizar contadores
        update = {
            "$inc": {"total_views": 1},
            "$set": {"last_accessed": now.isoformat()}
        }
        
        if action == "export":
            update["$inc"]["total_exports"] = 1
        
        await self.db.folder_analytics.update_one(
            {"folder_id": folder_id},
            update,
            upsert=True
        )
        
        # Log de acceso (opcional, para historial detallado)
        await self.db.folder_access_log.insert_one({
            "folder_id": folder_id,
            "user_id": user_id,
            "action": action,
            "timestamp": now.isoformat()
        })
    
    async def record_export(self, folder_id: str, user_id: str):
        """Registra una exportación desde el folder"""
        await self._record_access(folder_id, user_id, "export")
    
    async def get_folder_analytics(self, folder_id: str) -> Optional[Dict]:
        """Obtiene analytics de un folder"""
        analytics = await self.db.folder_analytics.find_one(
            {"folder_id": folder_id}, {"_id": 0}
        )
        
        if analytics:
            # Calcular vistas últimos 30 días
            cutoff = datetime.now(timezone.utc) - timedelta(days=30)
            views_30d = await self.db.folder_access_log.count_documents({
                "folder_id": folder_id,
                "action": "view",
                "timestamp": {"$gte": cutoff.isoformat()}
            })
            analytics["views_last_30_days"] = views_30d
        
        return analytics


def create_smart_folder_service(db):
    """Factory function"""
    return SmartFolderService(db)
