import axiosClient from './axiosClient';

/**
 * Consulta si un RUC específico figura en el padrón local de SSCO.
 * @param {string} ruc - RUC de 11 dígitos
 */
export const consultarSSCO = async (ruc) => {
  const response = await axiosClient.get(`/ssco/consultar/${ruc}`);
  return response.data;
};

/**
 * Obtiene el estado actual del padrón SSCO (disponibilidad, total registros, fecha de corte).
 */
export const obtenerEstadoSSCO = async () => {
  const response = await axiosClient.get('/ssco/estado');
  return response.data;
};

/**
 * Ejecuta la sincronización automática descargando el padrón oficial de SUNAT (Solo ADMIN).
 */
export const sincronizarSSCO = async () => {
  const response = await axiosClient.post('/ssco/sincronizar');
  return response.data;
};

/**
 * Carga manualmente un archivo Excel oficial del padrón SSCO como contingencia (Solo ADMIN).
 * @param {File} file - Archivo .xlsx oficial
 */
export const cargarExcelSSCO = async (file) => {
  const formData = new FormData();
  formData.append('file', file);
  const response = await axiosClient.post('/ssco/cargar-excel', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
  return response.data;
};
