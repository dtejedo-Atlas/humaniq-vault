"""
User Service
============
Gestión de usuarios y roles para sistema multi-usuario.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
import uuid
import logging

from models import User, UserRole, UserCreate, UserUpdate, UserWithStats
from auth import get_password_hash

logger = logging.getLogger(__name__)


class UserService:
    """Servicio de gestión de usuarios"""
    
    def __init__(self, db):
        self.db = db
    
    # ========== VERIFICACIÓN DE PERMISOS ==========
    
    def can_manage_users(self, user: User) -> bool:
        """Verifica si el usuario puede gestionar otros usuarios"""
        return user.role in [UserRole.SUPER_ADMIN, UserRole.ADMIN]
    
    def can_create_role(self, current_user: User, target_role: UserRole) -> bool:
        """Verifica si el usuario puede crear un usuario con el rol especificado"""
        if current_user.role == UserRole.SUPER_ADMIN:
            return True  # Super admin puede crear cualquier rol
        
        if current_user.role == UserRole.ADMIN:
            # Admin puede crear recruiters y researchers, pero no otros admins
            return target_role in [UserRole.RECRUITER, UserRole.RESEARCHER]
        
        return False
    
    def can_edit_user(self, current_user: User, target_user_id: str) -> bool:
        """Verifica si el usuario puede editar otro usuario"""
        if current_user.role == UserRole.SUPER_ADMIN:
            return True
        
        if current_user.role == UserRole.ADMIN:
            # Admin no puede editar super_admins
            # Necesitamos verificar el rol del target
            return True  # La verificación completa se hace en el endpoint
        
        # Usuarios pueden editar su propio perfil (nombre solamente)
        return current_user.id == target_user_id
    
    # ========== CRUD DE USUARIOS ==========
    
    async def create_user(
        self, 
        user_data: UserCreate, 
        created_by: User
    ) -> Dict[str, Any]:
        """Crea un nuevo usuario"""
        
        # Verificar permisos
        if not self.can_manage_users(created_by):
            raise PermissionError("No tienes permisos para crear usuarios")
        
        if not self.can_create_role(created_by, user_data.role):
            raise PermissionError(f"No puedes crear usuarios con rol {user_data.role}")
        
        # Verificar que el email no existe
        existing = await self.db.users.find_one({"email": user_data.email.lower()})
        if existing:
            raise ValueError("Ya existe un usuario con ese email")
        
        # Crear usuario
        user_id = str(uuid.uuid4())
        user_doc = {
            "id": user_id,
            "email": user_data.email.lower(),
            "name": user_data.name,
            "hashed_password": get_password_hash(user_data.password),
            "role": user_data.role.value,
            "is_active": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": created_by.id,
            "last_login": None
        }
        
        await self.db.users.insert_one(user_doc)
        
        logger.info(f"User {user_data.email} created by {created_by.email}")
        
        # Retornar sin password
        user_doc.pop("hashed_password", None)
        user_doc.pop("_id", None)
        
        return user_doc
    
    async def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Obtiene un usuario por ID"""
        user = await self.db.users.find_one({"id": user_id}, {"_id": 0, "hashed_password": 0})
        return user
    
    async def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Obtiene un usuario por email"""
        user = await self.db.users.find_one(
            {"email": email.lower()}, 
            {"_id": 0, "hashed_password": 0}
        )
        return user
    
    async def list_users(
        self, 
        current_user: User,
        include_inactive: bool = False
    ) -> List[Dict[str, Any]]:
        """Lista todos los usuarios"""
        
        if not self.can_manage_users(current_user):
            raise PermissionError("No tienes permisos para ver usuarios")
        
        query = {}
        if not include_inactive:
            query["is_active"] = True
        
        users = await self.db.users.find(
            query, 
            {"_id": 0, "hashed_password": 0}
        ).sort("created_at", -1).to_list(100)
        
        return users
    
    async def list_users_with_stats(self, current_user: User) -> List[Dict[str, Any]]:
        """Lista usuarios con estadísticas de uso"""
        
        users = await self.list_users(current_user, include_inactive=True)
        
        for user in users:
            # Contar candidatos asignados
            assigned_count = await self.db.assignments.count_documents({
                "recruiter_id": user["id"],
                "status": "active"
            })
            user["candidates_assigned"] = assigned_count
            
            # Contar vacantes creadas
            jobs_count = await self.db.jobs.count_documents({
                "created_by": user["id"]
            })
            user["jobs_created"] = jobs_count
        
        return users
    
    async def update_user(
        self, 
        user_id: str, 
        update_data: UserUpdate, 
        current_user: User
    ) -> Dict[str, Any]:
        """Actualiza un usuario"""
        
        # Obtener usuario objetivo
        target_user = await self.db.users.find_one({"id": user_id})
        if not target_user:
            raise ValueError("Usuario no encontrado")
        
        # Verificar permisos
        is_self_edit = current_user.id == user_id
        
        if not is_self_edit and not self.can_manage_users(current_user):
            raise PermissionError("No tienes permisos para editar usuarios")
        
        # Super admins no pueden ser editados por admins
        if target_user.get("role") == "super_admin" and current_user.role != UserRole.SUPER_ADMIN:
            raise PermissionError("No puedes editar un super admin")
        
        # Construir actualización
        update_fields = {}
        
        if update_data.name is not None:
            update_fields["name"] = update_data.name
        
        # Solo admins pueden cambiar roles y estado activo
        if self.can_manage_users(current_user) and not is_self_edit:
            if update_data.role is not None:
                # Verificar que puede asignar ese rol
                if not self.can_create_role(current_user, update_data.role):
                    raise PermissionError(f"No puedes asignar el rol {update_data.role}")
                update_fields["role"] = update_data.role.value
            
            if update_data.is_active is not None:
                update_fields["is_active"] = update_data.is_active
        
        if not update_fields:
            raise ValueError("No hay campos para actualizar")
        
        update_fields["updated_at"] = datetime.now(timezone.utc).isoformat()
        
        await self.db.users.update_one(
            {"id": user_id},
            {"$set": update_fields}
        )
        
        logger.info(f"User {user_id} updated by {current_user.email}")
        
        updated_user = await self.get_user_by_id(user_id)
        return updated_user
    
    async def deactivate_user(self, user_id: str, current_user: User) -> Dict[str, Any]:
        """Desactiva un usuario (soft delete)"""
        
        if not self.can_manage_users(current_user):
            raise PermissionError("No tienes permisos para desactivar usuarios")
        
        # No puede desactivarse a sí mismo
        if current_user.id == user_id:
            raise ValueError("No puedes desactivarte a ti mismo")
        
        target_user = await self.db.users.find_one({"id": user_id})
        if not target_user:
            raise ValueError("Usuario no encontrado")
        
        # Super admins no pueden ser desactivados por admins
        if target_user.get("role") == "super_admin" and current_user.role != UserRole.SUPER_ADMIN:
            raise PermissionError("No puedes desactivar un super admin")
        
        await self.db.users.update_one(
            {"id": user_id},
            {"$set": {"is_active": False, "updated_at": datetime.now(timezone.utc).isoformat()}}
        )
        
        logger.info(f"User {user_id} deactivated by {current_user.email}")
        
        return {"message": "Usuario desactivado correctamente"}
    
    async def get_recruiters(self) -> List[Dict[str, Any]]:
        """Obtiene lista de reclutadores activos (para asignación)"""
        recruiters = await self.db.users.find(
            {
                "role": {"$in": ["recruiter", "admin", "super_admin"]},
                "is_active": True
            },
            {"_id": 0, "hashed_password": 0}
        ).to_list(100)
        
        return recruiters


def create_user_service(db):
    """Factory function"""
    return UserService(db)
