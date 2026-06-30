import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { taxonomyAPI } from '../api';

const TaxonomyContext = createContext(null);

export const TaxonomyProvider = ({ children }) => {
  const [industries, setIndustries] = useState([]);
  const [functionalAreas, setFunctionalAreas] = useState([]);
  const [seniorityLevels, setSeniorityLevels] = useState([]);
  const [lookup, setLookup] = useState({ industries: {}, functional_areas: {} });
  const [loading, setLoading] = useState(true);

  const fetchTaxonomy = useCallback(async () => {
    try {
      const [industriesRes, areasRes, lookupRes, seniorityRes] = await Promise.all([
        taxonomyAPI.getIndustries(),
        taxonomyAPI.getFunctionalAreas(),
        taxonomyAPI.getLookup(),
        taxonomyAPI.getSeniorityLevels()
      ]);
      
      setIndustries(industriesRes.data);
      setFunctionalAreas(areasRes.data);
      setLookup(lookupRes.data);
      
      // Transform seniority levels from {key: {level, label}} to [{key, label}]
      const seniorityData = seniorityRes.data?.levels || {};
      const seniorityArray = Object.entries(seniorityData).map(([key, config]) => ({
        key,
        label: config.label,
        level: config.level
      })).sort((a, b) => a.level - b.level);
      setSeniorityLevels(seniorityArray);
    } catch (error) {
      console.error('Error fetching taxonomy:', error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchTaxonomy();
  }, [fetchTaxonomy]);

  // Obtener nombre de industria a partir de key (retorna español por defecto)
  const getIndustryName = useCallback((key, lang = 'es') => {
    if (!key) return '';
    const industry = lookup.industries[key];
    if (industry) {
      return lang === 'en' ? industry.name_en : industry.name_es;
    }
    // Si no se encuentra en lookup, devolver la key (podría ser un valor legacy)
    return key;
  }, [lookup]);

  // Obtener nombre de área funcional a partir de key (retorna español por defecto)
  const getFunctionalAreaName = useCallback((key, lang = 'es') => {
    if (!key) return '';
    const area = lookup.functional_areas[key];
    if (area) {
      return lang === 'en' ? area.name_en : area.name_es;
    }
    return key;
  }, [lookup]);

  // Obtener nombre de seniority a partir de key
  const getSeniorityName = useCallback((key) => {
    if (!key) return '';
    const level = seniorityLevels.find(s => s.key === key);
    return level?.label || key;
  }, [seniorityLevels]);

  // Obtener opciones formateadas para dropdowns (value=key, label=name_es)
  const getIndustryOptions = useCallback(() => {
    return industries.map(ind => ({
      value: ind.key,
      label: ind.name_es,
      labelEn: ind.name_en
    }));
  }, [industries]);

  const getFunctionalAreaOptions = useCallback(() => {
    return functionalAreas.map(area => ({
      value: area.key,
      label: area.name_es,
      labelEn: area.name_en
    }));
  }, [functionalAreas]);

  const getSeniorityOptions = useCallback(() => {
    return seniorityLevels.map(level => ({
      value: level.key,
      label: level.label
    }));
  }, [seniorityLevels]);

  const value = {
    industries,
    functionalAreas,
    seniorityLevels,
    lookup,
    loading,
    getIndustryName,
    getFunctionalAreaName,
    getSeniorityName,
    getIndustryOptions,
    getFunctionalAreaOptions,
    getSeniorityOptions,
    refetch: fetchTaxonomy
  };

  return (
    <TaxonomyContext.Provider value={value}>
      {children}
    </TaxonomyContext.Provider>
  );
};

export const useTaxonomy = () => {
  const context = useContext(TaxonomyContext);
  if (!context) {
    throw new Error('useTaxonomy must be used within a TaxonomyProvider');
  }
  return context;
};

export default TaxonomyContext;
