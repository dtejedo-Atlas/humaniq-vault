import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';
import axios from 'axios';
import { taxonomyAPI } from '../api';
import { useAuth } from './AuthContext';

const TaxonomyContext = createContext(null);

export const TaxonomyProvider = ({ children }) => {
  const { token } = useAuth();
  const [industries, setIndustries] = useState([]);
  const [functionalAreas, setFunctionalAreas] = useState([]);
  const [seniorityLevels, setSeniorityLevels] = useState([]);
  const [humaniqAreas, setHumaniqAreas] = useState([]);
  const [humaniqSeniorities, setHumaniqSeniorities] = useState([]);
  const [lookup, setLookup] = useState({ industries: {}, functional_areas: {} });
  const [loading, setLoading] = useState(false);
  const lastTokenRef = useRef(null);

  const fetchTaxonomy = useCallback(async () => {
    if (!token) {
      return;
    }
    
    setLoading(true);
    try {
      // El provider hijo monta antes que AuthContext fije la cabecera: la aseguramos aquí.
      axios.defaults.headers.common['Authorization'] = `Bearer ${token}`;
      const [industriesRes, areasRes, lookupRes, seniorityRes, humaniqRes] = await Promise.all([
        taxonomyAPI.getIndustries(),
        taxonomyAPI.getFunctionalAreas(),
        taxonomyAPI.getLookup(),
        taxonomyAPI.getSeniorityLevels(),
        taxonomyAPI.getHumaniqCatalog()
      ]);
      
      setIndustries(industriesRes.data || []);
      setFunctionalAreas(areasRes.data || []);
      setLookup(lookupRes.data || { industries: {}, functional_areas: {} });
      setHumaniqAreas(humaniqRes.data?.areas || []);
      setHumaniqSeniorities(humaniqRes.data?.seniority_levels || []);
      
      // Transform seniority levels from {key: {level, label}} to [{key, label}]
      const seniorityData = seniorityRes.data?.levels || {};
      const seniorityArray = Object.entries(seniorityData).map(([key, config]) => ({
        key,
        label: config.label,
        level: config.level
      })).sort((a, b) => a.level - b.level);
      setSeniorityLevels(seniorityArray);
      
      console.log('Taxonomy loaded:', {
        industries: industriesRes.data?.length,
        functionalAreas: areasRes.data?.length,
        seniorityLevels: seniorityArray.length
      });
    } catch (error) {
      console.error('Error fetching taxonomy:', error);
    } finally {
      setLoading(false);
    }
  }, [token]);

  // Fetch taxonomy when token changes (user logs in or token refreshes)
  useEffect(() => {
    if (token && token !== lastTokenRef.current) {
      lastTokenRef.current = token;
      fetchTaxonomy();
    } else if (!token && lastTokenRef.current) {
      // User logged out - reset state
      lastTokenRef.current = null;
      setIndustries([]);
      setFunctionalAreas([]);
      setSeniorityLevels([]);
      setHumaniqAreas([]);
      setHumaniqSeniorities([]);
      setLookup({ industries: {}, functional_areas: {} });
    }
  }, [token, fetchTaxonomy]);

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

  // Nombre del área/subárea/seniority del catálogo Humaniq (capa de presentación)
  const getPresentationAreaName = useCallback((key) => {
    if (!key) return '';
    return humaniqAreas.find(area => area.key === key)?.label || key;
  }, [humaniqAreas]);

  const getPresentationSubareaName = useCallback((areaKey, subareaKey) => {
    if (!subareaKey) return '';
    const area = humaniqAreas.find(item => item.key === areaKey);
    return area?.subareas?.find(sub => sub.key === subareaKey)?.label || subareaKey;
  }, [humaniqAreas]);

  const getPresentationSeniorityName = useCallback((key) => {
    if (!key) return '';
    return humaniqSeniorities.find(level => level.key === key)?.label || key;
  }, [humaniqSeniorities]);

  // Campos de clasificación (dropdowns) según el catálogo Humaniq
  const getClassificationFields = useCallback((values) => {
    const area = humaniqAreas.find(item => item.key === values?.presentation_area);
    return [
      ['industry', 'Industria', industries],
      ['presentation_area', 'Área funcional', humaniqAreas.map(item => ({ key: item.key, label: item.label }))],
      ['presentation_subarea', 'Subárea', (area?.subareas || []).map(sub => ({ key: sub.key, label: sub.label }))],
      ['presentation_seniority', 'Seniority', humaniqSeniorities.map(level => ({ key: level.key, label: level.label }))],
    ];
  }, [industries, humaniqAreas, humaniqSeniorities]);

  const value = {
    industries,
    functionalAreas,
    seniorityLevels,
    humaniqAreas,
    humaniqSeniorities,
    lookup,
    loading,
    getIndustryName,
    getFunctionalAreaName,
    getSeniorityName,
    getPresentationAreaName,
    getPresentationSubareaName,
    getPresentationSeniorityName,
    getClassificationFields,
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
