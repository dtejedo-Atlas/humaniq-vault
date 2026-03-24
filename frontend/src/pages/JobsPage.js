import React from 'react';
import Layout from '../components/Layout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Briefcase } from 'lucide-react';

const JobsPage = () => {
  return (
    <Layout title="Vacantes" subtitle="Gestiona vacantes y encuentra candidatos compatibles">
      <Card>
        <CardHeader>
          <CardTitle>Gestión de Vacantes</CardTitle>
          <CardDescription>Esta funcionalidad estará disponible en la Fase 2</CardDescription>
        </CardHeader>
        <CardContent className="h-64 flex items-center justify-center">
          <div className="text-center">
            <Briefcase className="w-16 h-16 text-slate-300 mx-auto mb-4" />
            <p className="text-slate-600">Sistema de matching de vacantes en desarrollo</p>
          </div>
        </CardContent>
      </Card>
    </Layout>
  );
};

export default JobsPage;