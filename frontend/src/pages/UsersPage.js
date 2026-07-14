import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { usersAPI } from '../api';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { 
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue 
} from '../components/ui/select';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../components/ui/dialog';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../components/ui/table';
import { Badge } from '../components/ui/badge';
import { 
  Users, 
  Plus, 
  Edit, 
  UserX, 
  Shield, 
  Briefcase,
  Mail,
  Calendar,
  Loader2,
  AlertCircle,
  UserCheck,
  Send,
  KeyRound
} from 'lucide-react';
import { toast } from 'sonner';

const ROLES = {
  super_admin: { label: 'Super Admin', color: 'bg-purple-100 text-purple-800 border-purple-300' },
  admin: { label: 'Admin', color: 'bg-blue-100 text-blue-800 border-blue-300' },
  recruiter: { label: 'Recruiter', color: 'bg-green-100 text-green-800 border-green-300' },
  researcher: { label: 'Researcher', color: 'bg-amber-100 text-amber-800 border-amber-300' }
};

export default function UsersPage() {
  const { user: currentUser } = useAuth();
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [showEditDialog, setShowEditDialog] = useState(false);
  const [selectedUser, setSelectedUser] = useState(null);
  const [includeInactive, setIncludeInactive] = useState(false);
  const [saving, setSaving] = useState(false);
  const [sendingEmailFor, setSendingEmailFor] = useState(null);

  // Form state
  const [formData, setFormData] = useState({
    email: '',
    name: '',
    role: 'recruiter'
  });

  const canManageUsers = currentUser?.role === 'admin' || currentUser?.role === 'super_admin';

  useEffect(() => {
    if (!canManageUsers) {
      setError('No tienes permisos para acceder a esta página');
      setLoading(false);
      return;
    }
    loadUsers();
  }, [canManageUsers, includeInactive]);

  const loadUsers = async () => {
    try {
      setLoading(true);
      const response = await usersAPI.getAll(includeInactive);
      setUsers(response.data.users || []);
      setError(null);
    } catch (err) {
      console.error('Error loading users:', err);
      setError(err.response?.data?.detail || 'Error al cargar usuarios');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateUser = async () => {
    if (!formData.email || !formData.name) {
      toast.error('Email y nombre son obligatorios');
      return;
    }

    try {
      setSaving(true);
      const response = await usersAPI.create({
        email: formData.email,
        name: formData.name,
        role: formData.role,
        origin: window.location.origin
      });
      if (response.data.email_sent === false) {
        toast.warning(
          `Usuario creado, pero el email de invitación NO se pudo enviar: ${response.data.email_error || 'error desconocido'}. Usa el botón "Reenviar invitación" para intentar de nuevo.`,
          { duration: 10000 }
        );
      } else {
        toast.success(`Usuario creado. Invitación enviada a ${formData.email}`);
      }
      setShowCreateDialog(false);
      setFormData({ email: '', name: '', role: 'recruiter' });
      loadUsers();
    } catch (err) {
      console.error('Error creating user:', err);
      toast.error(err.response?.data?.detail || 'Error al crear usuario');
    } finally {
      setSaving(false);
    }
  };

  const handleResendInvitation = async (user) => {
    if (!window.confirm(`¿Reenviar la invitación a ${user.email}? Se generará un enlace nuevo (el anterior quedará invalidado).`)) return;
    try {
      setSendingEmailFor(user.id);
      await usersAPI.resendInvitation(user.id, window.location.origin);
      toast.success(`Invitación reenviada a ${user.email}`);
    } catch (err) {
      console.error('Error resending invitation:', err);
      toast.error(err.response?.data?.detail || 'No se pudo enviar el email. Intenta de nuevo.');
    } finally {
      setSendingEmailFor(null);
    }
  };

  const handleSendPasswordReset = async (user) => {
    if (!window.confirm(`¿Enviar email de restablecimiento de contraseña a ${user.email}?`)) return;
    try {
      setSendingEmailFor(user.id);
      await usersAPI.sendPasswordReset(user.id, window.location.origin);
      toast.success(`Email de restablecimiento enviado a ${user.email}`);
    } catch (err) {
      console.error('Error sending password reset:', err);
      toast.error(err.response?.data?.detail || 'No se pudo enviar el email. Intenta de nuevo.');
    } finally {
      setSendingEmailFor(null);
    }
  };

  const handleEditUser = async () => {
    if (!selectedUser) return;

    try {
      setSaving(true);
      const updateData = {
        name: formData.name,
        role: formData.role,
        is_active: formData.is_active
      };
      await usersAPI.update(selectedUser.id, updateData);
      toast.success('Usuario actualizado');
      setShowEditDialog(false);
      setSelectedUser(null);
      loadUsers();
    } catch (err) {
      console.error('Error updating user:', err);
      toast.error(err.response?.data?.detail || 'Error al actualizar usuario');
    } finally {
      setSaving(false);
    }
  };

  const handleDeactivateUser = async (userId) => {
    if (userId === currentUser.id) {
      toast.error('No puedes desactivarte a ti mismo');
      return;
    }

    if (!window.confirm('¿Estás seguro de desactivar este usuario?')) return;

    try {
      await usersAPI.deactivate(userId);
      toast.success('Usuario desactivado');
      loadUsers();
    } catch (err) {
      console.error('Error deactivating user:', err);
      toast.error(err.response?.data?.detail || 'Error al desactivar usuario');
    }
  };

  const openEditDialog = (user) => {
    setSelectedUser(user);
    setFormData({
      name: user.name,
      role: user.role,
      is_active: user.is_active !== false
    });
    setShowEditDialog(true);
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return '-';
    return new Date(dateStr).toLocaleDateString('es-MX', {
      day: '2-digit',
      month: 'short',
      year: 'numeric'
    });
  };

  if (!canManageUsers) {
    return (
      <div className="p-8">
        <div className="bg-red-50 border border-red-200 rounded-lg p-6 text-center">
          <AlertCircle className="w-12 h-12 text-red-500 mx-auto mb-4" />
          <h2 className="text-xl font-semibold text-red-800 mb-2">Acceso Denegado</h2>
          <p className="text-red-600">No tienes permisos para gestionar usuarios.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Users className="w-7 h-7 text-indigo-600" />
            Gestión de Usuarios
          </h1>
          <p className="text-gray-500 mt-1">Administra el equipo de reclutamiento</p>
        </div>
        <Button 
          onClick={() => setShowCreateDialog(true)}
          className="bg-indigo-600 hover:bg-indigo-700"
        >
          <Plus className="w-4 h-4 mr-2" />
          Nuevo Usuario
        </Button>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-4">
        <label className="flex items-center gap-2 text-sm text-gray-600">
          <input
            type="checkbox"
            checked={includeInactive}
            onChange={(e) => setIncludeInactive(e.target.checked)}
            className="rounded border-gray-300"
          />
          Mostrar usuarios inactivos
        </label>
      </div>

      {/* Error State */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">
          {error}
        </div>
      )}

      {/* Loading State */}
      {loading && (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-8 h-8 animate-spin text-indigo-600" />
        </div>
      )}

      {/* Users Table */}
      {!loading && !error && (
        <div className="bg-white rounded-xl border shadow-sm overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow className="bg-gray-50">
                <TableHead>Usuario</TableHead>
                <TableHead>Rol</TableHead>
                <TableHead>Estado</TableHead>
                <TableHead className="text-center">Candidatos</TableHead>
                <TableHead className="text-center">Vacantes</TableHead>
                <TableHead>Último Login</TableHead>
                <TableHead className="text-right">Acciones</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {users.map((user) => (
                <TableRow 
                  key={user.id}
                  className={user.is_active === false ? 'bg-gray-50 opacity-60' : ''}
                >
                  <TableCell>
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-full bg-indigo-100 flex items-center justify-center">
                        <span className="text-indigo-700 font-medium">
                          {user.name?.charAt(0).toUpperCase() || '?'}
                        </span>
                      </div>
                      <div>
                        <p className="font-medium text-gray-900">{user.name}</p>
                        <p className="text-sm text-gray-500 flex items-center gap-1">
                          <Mail className="w-3 h-3" />
                          {user.email}
                        </p>
                      </div>
                    </div>
                  </TableCell>
                  <TableCell>
                    <Badge 
                      variant="outline" 
                      className={ROLES[user.role]?.color || 'bg-gray-100'}
                    >
                      {user.role === 'super_admin' && <Shield className="w-3 h-3 mr-1" />}
                      {ROLES[user.role]?.label || user.role}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    {user.is_active === false ? (
                      <Badge variant="outline" className="bg-gray-100 text-gray-600">
                        Inactivo
                      </Badge>
                    ) : user.invitation_pending ? (
                      <Badge variant="outline" className="bg-amber-50 text-amber-700 border-amber-200" data-testid={`invitation-pending-badge-${user.id}`}>
                        <Send className="w-3 h-3 mr-1" />
                        Invitación pendiente
                      </Badge>
                    ) : (
                      <Badge variant="outline" className="bg-green-50 text-green-700 border-green-200">
                        <UserCheck className="w-3 h-3 mr-1" />
                        Activo
                      </Badge>
                    )}
                  </TableCell>
                  <TableCell className="text-center">
                    <span className="font-medium text-gray-700">
                      {user.candidates_assigned || 0}
                    </span>
                  </TableCell>
                  <TableCell className="text-center">
                    <span className="font-medium text-gray-700">
                      {user.jobs_created || 0}
                    </span>
                  </TableCell>
                  <TableCell>
                    <span className="text-sm text-gray-500 flex items-center gap-1">
                      <Calendar className="w-3 h-3" />
                      {formatDate(user.last_login)}
                    </span>
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="flex items-center justify-end gap-2">
                      {user.is_active !== false && (
                        user.invitation_pending ? (
                          <Button
                            variant="ghost"
                            size="sm"
                            title="Reenviar invitación"
                            data-testid={`resend-invitation-${user.id}`}
                            onClick={() => handleResendInvitation(user)}
                            disabled={sendingEmailFor === user.id}
                            className="text-amber-600 hover:text-amber-700 hover:bg-amber-50"
                          >
                            {sendingEmailFor === user.id ? (
                              <Loader2 className="w-4 h-4 animate-spin" />
                            ) : (
                              <Send className="w-4 h-4" />
                            )}
                          </Button>
                        ) : (
                          <Button
                            variant="ghost"
                            size="sm"
                            title="Restablecer contraseña"
                            data-testid={`send-password-reset-${user.id}`}
                            onClick={() => handleSendPasswordReset(user)}
                            disabled={sendingEmailFor === user.id}
                            className="text-cyan-600 hover:text-cyan-700 hover:bg-cyan-50"
                          >
                            {sendingEmailFor === user.id ? (
                              <Loader2 className="w-4 h-4 animate-spin" />
                            ) : (
                              <KeyRound className="w-4 h-4" />
                            )}
                          </Button>
                        )
                      )}
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => openEditDialog(user)}
                        disabled={user.role === 'super_admin' && currentUser.role !== 'super_admin'}
                      >
                        <Edit className="w-4 h-4" />
                      </Button>
                      {user.id !== currentUser.id && user.is_active !== false && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleDeactivateUser(user.id)}
                          className="text-red-600 hover:text-red-700 hover:bg-red-50"
                          disabled={user.role === 'super_admin' && currentUser.role !== 'super_admin'}
                        >
                          <UserX className="w-4 h-4" />
                        </Button>
                      )}
                    </div>
                  </TableCell>
                </TableRow>
              ))}
              {users.length === 0 && (
                <TableRow>
                  <TableCell colSpan={7} className="text-center py-8 text-gray-500">
                    No hay usuarios registrados
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </div>
      )}

      {/* Create User Dialog */}
      <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Plus className="w-5 h-5 text-indigo-600" />
              Nuevo Usuario
            </DialogTitle>
            <DialogDescription>
              Se le enviará un email con un enlace para establecer su contraseña (expira en 48h)
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>Nombre completo</Label>
              <Input
                data-testid="create-user-name-input"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                placeholder="Juan Pérez"
              />
            </div>
            <div className="space-y-2">
              <Label>Email</Label>
              <Input
                data-testid="create-user-email-input"
                type="email"
                value={formData.email}
                onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                placeholder="juan@empresa.com"
              />
            </div>
            <div className="space-y-2">
              <Label>Rol</Label>
              <Select
                value={formData.role}
                onValueChange={(value) => setFormData({ ...formData, role: value })}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="recruiter">
                    <span className="flex items-center gap-2">
                      <Briefcase className="w-4 h-4" />
                      Recruiter
                    </span>
                  </SelectItem>
                  <SelectItem value="researcher">
                    <span className="flex items-center gap-2">
                      <Users className="w-4 h-4" />
                      Researcher
                    </span>
                  </SelectItem>
                  {currentUser?.role === 'super_admin' && (
                    <SelectItem value="admin">
                      <span className="flex items-center gap-2">
                        <Shield className="w-4 h-4" />
                        Admin
                      </span>
                    </SelectItem>
                  )}
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowCreateDialog(false)}>
              Cancelar
            </Button>
            <Button 
              onClick={handleCreateUser} 
              disabled={saving}
              data-testid="create-user-submit"
              className="bg-indigo-600 hover:bg-indigo-700"
            >
              {saving && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
              Crear y Enviar Invitación
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit User Dialog */}
      <Dialog open={showEditDialog} onOpenChange={setShowEditDialog}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Edit className="w-5 h-5 text-indigo-600" />
              Editar Usuario
            </DialogTitle>
            <DialogDescription>
              Modifica los datos del usuario {selectedUser?.email}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>Nombre</Label>
              <Input
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label>Rol</Label>
              <Select
                value={formData.role}
                onValueChange={(value) => setFormData({ ...formData, role: value })}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="recruiter">Recruiter</SelectItem>
                  <SelectItem value="researcher">Researcher</SelectItem>
                  {currentUser?.role === 'super_admin' && (
                    <>
                      <SelectItem value="admin">Admin</SelectItem>
                      <SelectItem value="super_admin">Super Admin</SelectItem>
                    </>
                  )}
                </SelectContent>
              </Select>
            </div>
            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="is_active"
                checked={formData.is_active}
                onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
                className="rounded border-gray-300"
              />
              <Label htmlFor="is_active">Usuario activo</Label>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowEditDialog(false)}>
              Cancelar
            </Button>
            <Button 
              onClick={handleEditUser} 
              disabled={saving}
              className="bg-indigo-600 hover:bg-indigo-700"
            >
              {saving && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
              Guardar Cambios
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
