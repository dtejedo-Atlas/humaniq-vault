"""Shared notes: authenticated creation; author-ID/admin mutation, including safe legacy references."""
import hashlib
import json
from datetime import datetime, timezone
from uuid import uuid4
from fastapi import HTTPException
from pydantic import BaseModel, Field, ConfigDict, field_validator
from models import RecruiterNote, UserRole


class NoteEdit(BaseModel):
    model_config = ConfigDict(extra='forbid')
    note_text: str = Field(min_length=1, max_length=10000)

    @field_validator('note_text')
    @classmethod
    def nonempty(cls, value):
        if not value.strip():
            raise ValueError('La nota no puede estar vacía')
        return value.strip()


class NoteMutation(BaseModel):
    message: str
    note: RecruiterNote | None = None


def expose_note(note, index):
    result = dict(note)
    if not result.get('id'):
        fingerprint = hashlib.sha256(json.dumps(note, sort_keys=True, default=str, ensure_ascii=False).encode()).hexdigest()[:20]
        result['id'] = f'legacy-{index}-{fingerprint}'
    return result


async def mutate_note(db, candidate_id, note_id, user, new_text=None):
    candidate = await db.candidates.find_one({'id': candidate_id, 'is_deleted': {'$ne': True}}, {'_id': 0, 'notes': 1})
    if not candidate:
        raise HTTPException(404, 'Candidato no encontrado')
    notes = candidate.get('notes', [])
    index = next((i for i, note in enumerate(notes) if expose_note(note, i)['id'] == note_id), None)
    if index is None:
        raise HTTPException(404, 'Nota no encontrada o modificada; actualiza la ficha')
    original = notes[index]
    admin = user.role in (UserRole.ADMIN, UserRole.SUPER_ADMIN)
    if not admin and (not original.get('created_by_id') or original['created_by_id'] != user.id):
        raise HTTPException(403, 'Solo el autor identificado de la nota o un administrador puede modificarla')
    now = datetime.now(timezone.utc).isoformat()
    updated = None
    if new_text is None:
        replacement = notes[:index] + notes[index + 1:]
    else:
        updated = {**original, 'id': original.get('id') or str(uuid4()), 'note': new_text, 'updated_at': now, 'updated_by_id': user.id}
        replacement = notes[:index] + [updated] + notes[index + 1:]
    # Compare the exact array read above: another author's note/addition cannot be lost in a race.
    result = await db.candidates.update_one(
        {'id': candidate_id, 'is_deleted': {'$ne': True}, 'notes': notes},
        {'$set': {'notes': replacement, 'updated_at': now}},
    )
    if result.matched_count != 1:
        raise HTTPException(409, 'Las notas cambiaron mientras editabas. Actualiza e inténtalo de nuevo.')
    await db.candidate_note_history.insert_one({'candidate_id': candidate_id, 'note_reference': note_id,
        'action': 'deleted' if new_text is None else 'edited', 'actor_id': user.id, 'at': now, 'before': original, 'after': updated})
    return NoteMutation(message='Nota eliminada' if new_text is None else 'Nota actualizada',
                        note=RecruiterNote.model_validate(updated) if updated else None)