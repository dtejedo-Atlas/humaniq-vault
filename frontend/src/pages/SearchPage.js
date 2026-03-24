import React from 'react';
import Layout from '../components/Layout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Search, Filter } from 'lucide-react';

const SearchPage = () => {
  return (
    <Layout title="Búsqueda Avanzada" subtitle="Encuentra candidatos con filtros avanzados y búsqueda semántica">
      <Card>
        <CardHeader>
          <CardTitle>Búsqueda Avanzada</CardTitle>
          <CardDescription>Esta funcionalidad estará disponible próximamente</CardDescription>
        </CardHeader>
        <CardContent className="h-64 flex items-center justify-center">
          <div className="text-center">
            <Search className="w-16 h-16 text-slate-300 mx-auto mb-4" />
            <p className="text-slate-600">Sistema de búsqueda avanzada en desarrollo</p>
          </div>
        </CardContent>
      </Card>
    </Layout>
  );
};

export default SearchPage;