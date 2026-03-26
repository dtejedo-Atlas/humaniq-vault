"""
Assignment Service
==================
Gestión de asignación de candidatos a reclutadores.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
import uuid
import logging

from models import User, UserRole, CandidateAssignment, AssignmentStatus

logger = logging.getLogger(__name__)


class AssignmentService:
    """Servicio de asignación de candidatos"""
    
    def __init__(self, db):
        self.db = db
    
    # ========== VERIFICACIÓN DE PERMISOS ==========
    
    def can_assign(self, user: User) -> bool:
        """Verifica si el usuario puede asignar candidatos"""
        return user.role in [UserRole.SUPER_ADMIN, UserRole.ADMIN]
    
    def can_edit_candidate(self, user: User, candidate_id: str, assignments: List[dict]) -> bool:
        """
        Verifica si el usuario puede editar un candidato.
        - Admin/Super Admin: puede editar cualquiera
        - Recruiter: solo puede editar si está asignado a él
        """
        if user.role in [UserRole.SUPER_ADMIN, UserRole.ADMIN]:
            return True
        
        # Verificar si el candidato está asignado a este reclutador
        for assignment in assignments:
            if (assignment.get("recruiter_id") == user.id and 
                assignment.get("status") == "active"):
                return True
        
        return False
    
    # ========== CRUD DE ASIGNACIONES ==========
    
    async def assign_candidate(
        self,
        candidate_id: str,
        recruiter_id: str,
        assigned_by: User,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """Asigna un candidato a un reclutador"""
        
        if not self.can_assign(assigned_by):
            raise PermissionError("No tienes permisos para asignar candidatos")
        
        # Verificar que el candidato existe
        candidate = await self.db.candidates.find_one({"id": candidate_id})
        if not candidate:
            raise ValueError("Candidato no encontrado")
        
        # Verificar que el reclutador existe y está activo
        # Nota: algunos usuarios legacy no tienen is_active, asumimos True
        recruiter = await self.db.users.find_one({
            "id": recruiter_id,
            "$or": [{"is_active": True}, {"is_active": {"$exists": False}}]
        })
        if not recruiter:
            raise ValueError("Reclutador no encontrado o inactivo")
        
        # Verificar que no existe ya una asignación activa
        existing = await self.db.assignments.find_one({
            "candidate_id": candidate_id,
            "recruiter_id": recruiter_id,
            "status": "active"
        })
        if existing:
            raise ValueError("El candidato ya está asignado a este reclutador")
        
        # Crear asignación
        assignment_id = str(uuid.uuid4())
        assignment_doc = {
            "id": assignment_id,
            "candidate_id": candidate_id,
            "candidate_name": candidate.get("full_name", ""),
            "recruiter_id": recruiter_id,
            "recruiter_name": recruiter.get("name", ""),
            "assigned_by": assigned_by.id,
            "assigned_by_name": assigned_by.name,
            "assigned_at": datetime.now(timezone.utc).isoformat(),
            "notes": notes,
            "status": "active"
        }
        
        await self.db.assignments.insert_one(assignment_doc)
        
        logger.info(f"Candidate {candidate_id} assigned to {recruiter_id} by {assigned_by.email}")
        
        assignment_doc.pop("_id", None)
        return assignment_doc
    
    async def unassign_candidate(
        self,
        candidate_id: str,
        recruiter_id: str,
        current_user: User
    ) -> Dict[str, Any]:
        """Elimina la asignación de un candidato"""
        
        if not self.can_assign(current_user):
            raise PermissionError("No tienes permisos para desasignar candidatos")
        
        result = await self.db.assignments.update_one(
            {
                "candidate_id": candidate_id,
                "recruiter_id": recruiter_id,
                "status": "active"
            },
            {
                "$set": {
                    "status": "completed",
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }
            }
        )
        
        if result.modified_count == 0:
            raise ValueError("Asignación no encontrada")
        
        logger.info(f"Candidate {candidate_id} unassigned from {recruiter_id}")
        
        return {"message": "Asignación eliminada correctamente"}
    
    async def get_candidate_assignments(self, candidate_id: str) -> List[Dict[str, Any]]:
        """Obtiene todas las asignaciones de un candidato"""
        assignments = await self.db.assignments.find(
            {"candidate_id": candidate_id, "status": "active"},
            {"_id": 0}
        ).to_list(50)
        
        return assignments
    
    async def get_my_assignments(self, user: User) -> List[Dict[str, Any]]:
        """Obtiene los candidatos asignados al usuario actual"""
        assignments = await self.db.assignments.find(
            {"recruiter_id": user.id, "status": "active"},
            {"_id": 0}
        ).sort("assigned_at", -1).to_list(500)
        
        # Enriquecer con datos del candidato
        for assignment in assignments:
            candidate = await self.db.candidates.find_one(
                {"id": assignment["candidate_id"]},
                {"_id": 0, "full_name": 1, "current_title": 1, "current_company": 1, 
                 "industry": 1, "functional_area": 1}
            )
            if candidate:
                assignment["candidate"] = candidate
        
        return assignments
    
    async def get_all_assignments(self, current_user: User) -> List[Dict[str, Any]]:
        """Obtiene todas las asignaciones (solo admin)"""
        if not self.can_assign(current_user):
            raise PermissionError("No tienes permisos para ver todas las asignaciones")
        
        assignments = await self.db.assignments.find(
            {"status": "active"},
            {"_id": 0}
        ).sort("assigned_at", -1).to_list(1000)
        
        return assignments
    
    async def get_assignments_by_recruiter(self, recruiter_id: str) -> List[Dict[str, Any]]:
        """Obtiene asignaciones de un reclutador específico"""
        assignments = await self.db.assignments.find(
            {"recruiter_id": recruiter_id, "status": "active"},
            {"_id": 0}
        ).to_list(500)
        
        return assignments
    
    async def transfer_assignment(
        self,
        candidate_id: str,
        from_recruiter_id: str,
        to_recruiter_id: str,
        current_user: User,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """Transfiere un candidato de un reclutador a otro"""
        
        if not self.can_assign(current_user):
            raise PermissionError("No tienes permisos para transferir candidatos")
        
        # Marcar asignación anterior como transferida
        await self.db.assignments.update_one(
            {
                "candidate_id": candidate_id,
                "recruiter_id": from_recruiter_id,
                "status": "active"
            },
            {
                "$set": {
                    "status": "transferred",
                    "transferred_to": to_recruiter_id,
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }
            }
        )
        
        # Crear nueva asignación
        return await self.assign_candidate(
            candidate_id=candidate_id,
            recruiter_id=to_recruiter_id,
            assigned_by=current_user,
            notes=notes or "Transferido"
        )
    
    async def get_unassigned_candidates_count(self) -> int:
        """Cuenta candidatos sin asignación activa"""
        # Obtener IDs de candidatos con asignación activa
        assigned_ids = await self.db.assignments.distinct(
            "candidate_id",
            {"status": "active"}
        )
        
        # Contar candidatos no asignados
        count = await self.db.candidates.count_documents({
            "id": {"$nin": assigned_ids}
        })
        
        return count


def create_assignment_service(db):
    """Factory function"""
    return AssignmentService(db)
