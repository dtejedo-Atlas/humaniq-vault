import React from 'react';
import Layout from '../components/Layout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Settings } from 'lucide-react';

const AdminPage = () => {
  return (
    <Layout title="Panel de Administración" subtitle="Gestiona usuarios, taxonomías y configuración del sistema">
      <Card>
        <CardHeader>
          <CardTitle>Panel de Administración</CardTitle>
          <CardDescription>Esta funcionalidad estará disponible en la Fase 3</CardDescription>
        </CardHeader>
        <CardContent className="h-64 flex items-center justify-center">
          <div className="text-center">
            <Settings className="w-16 h-16 text-slate-300 mx-auto mb-4" />
            <p className="text-slate-600">Panel administrativo en desarrollo</p>
          </div>
        </CardContent>
      </Card>
    </Layout>
  );
};

export default AdminPage;