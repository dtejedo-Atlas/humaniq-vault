import React from 'react';
import Layout from '../components/Layout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { FolderOpen } from 'lucide-react';

const FoldersPage = () => {
  return (
    <Layout title="Carpetas Inteligentes" subtitle="Organiza candidatos con carpetas dinámicas">
      <Card>
        <CardHeader>
          <CardTitle>Carpetas Inteligentes</CardTitle>
          <CardDescription>Esta funcionalidad estará disponible en la Fase 2</CardDescription>
        </CardHeader>
        <CardContent className="h-64 flex items-center justify-center">
          <div className="text-center">
            <FolderOpen className="w-16 h-16 text-slate-300 mx-auto mb-4" />
            <p className="text-slate-600">Sistema de carpetas inteligentes en desarrollo</p>
          </div>
        </CardContent>
      </Card>
    </Layout>
  );
};

export default FoldersPage;