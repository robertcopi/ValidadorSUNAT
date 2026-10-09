import React, { useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import axiosClient from '../api/axiosClient';
import {
  UploadCloud,
  FileSpreadsheet,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  AlertCircle,
  Search,
  CheckSquare,
  Square,
  Info,
  Loader2,
  Trash2,
  Layers,
  ArrowRight,
} from 'lucide-react';

export const CargaMasiva = () => {
  const navigate = useNavigate();
  const [dragActive, setDragActive] = useState(false);
  const [archivo, setArchivo] = useState(null);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState(null);
  const [previewData, setPreviewData] = useState(null);

  // Filtros y búsqueda
  const [filtroEstado, setFiltroEstado] = useState('TODOS'); // TODOS | LISTO | ERROR | DUPLICADO | NO_SOPORTADO
  const [busqueda, setBusqueda] = useState('');

  // Selección de filas LISTO
  const [seleccionados, setSeleccionados] = useState(new Set());

  // Proceso Masivo de Validación SUNAT
  const [validandoMasivo, setValidandoMasivo] = useState(false);
  const [procesoMasivo, setProcesoMasivo] = useState(null);
  const [errorValidacionMasiva, setErrorValidacionMasiva] = useState(null);

  const fileInputRef = useRef(null);

  // Manejadores de Drag & Drop
  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      procesarArchivo(e.dataTransfer.files[0]);
    }
  };

  const handleFileInput = (e) => {
    if (e.target.files && e.target.files[0]) {
      procesarArchivo(e.target.files[0]);
    }
  };

  const procesarArchivo = async (file) => {
    if (!file.name.toLowerCase().endsWith('.xlsx')) {
      setErrorMsg('Formato inválido. Por favor seleccione un archivo Excel (.xlsx).');
      return;
    }

    setArchivo(file);
    setErrorMsg(null);
    setLoading(true);
    setPreviewData(null);
    setSeleccionados(new Set());

    const formData = new FormData();
    formData.append('archivo', file);

    try {
      const response = await axiosClient.post('/importaciones/preview', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      setPreviewData(response.data);

      // Preseleccionar todas las filas que están en estado LISTO
      const listos = new Set(
        response.data.filas
          .filter((f) => f.estado_archivo === 'LISTO')
          .map((f) => f.fila_excel)
      );
      setSeleccionados(listos);
    } catch (err) {
      console.error('Error al procesar el archivo Excel:', err);
      const msg = err.response?.data?.detail || 'Ocurrió un error al analizar el archivo Excel.';
      setErrorMsg(msg);
    } finally {
      setLoading(false);
    }
  };

  const handleReset = () => {
    setArchivo(null);
    setPreviewData(null);
    setErrorMsg(null);
    setSeleccionados(new Set());
    setBusqueda('');
    setFiltroEstado('TODOS');
    setValidandoMasivo(false);
    setProcesoMasivo(null);
    setErrorValidacionMasiva(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const pollingRef = useRef(null);

  const detenerPolling = () => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
  };

  const handleValidarMasivo = async () => {
    if (seleccionados.size === 0 || validandoMasivo) return;
    setErrorValidacionMasiva(null);
    setValidandoMasivo(true);
    detenerPolling();

    const itemsAValidar = (previewData?.filas || [])
      .filter((f) => f.estado_archivo === 'LISTO' && seleccionados.has(f.fila_excel))
      .map((f) => ({
        fila_excel: f.fila_excel,
        num_ruc: f.num_ruc,
        cod_comp: f.cod_comp,
        numero_serie: f.numero_serie,
        numero: f.numero,
        fecha_emision: f.fecha_emision,
        monto_original: f.monto_original !== undefined ? f.monto_original : f.monto,
        monto: f.monto,
        razon_social: f.razon_social_emisor,
        base_imponible: f.base_imponible,
        igv: f.igv,
        monto_base_igv: f.monto_base_igv,
        valor_adquisiciones_no_gravadas: f.valor_adquisiciones_no_gravadas,
        monto_calculado_original: f.monto_calculado_original,
        tipo_cambio: f.tipo_cambio,
        monto_convertido: f.monto_convertido,
        importe_total_excel: f.importe_total_excel,
        otros_tributos: f.otros_tributos,
      }));

    try {
      const idempotencyKey = typeof crypto !== 'undefined' && crypto.randomUUID ? crypto.randomUUID() : `batch-${Date.now()}`;
      const response = await axiosClient.post('/procesos-masivos', {
        nombre_archivo: previewData.nombre_archivo,
        idempotency_key: idempotencyKey,
        items: itemsAValidar,
      }, {
        headers: { 'Idempotency-Key': idempotencyKey }
      });

      const nuevoProceso = response.data;
      setProcesoMasivo(nuevoProceso);

      // Iniciar polling para consultar progreso en segundo plano
      iniciarPollingProceso(nuevoProceso.id);
    } catch (err) {
      console.error('Error al iniciar validación masiva en SUNAT:', err);
      const msg = err.response?.data?.detail || 'Ocurrió un error al procesar la validación masiva en SUNAT.';
      setErrorValidacionMasiva(msg);
      setValidandoMasivo(false);
    }
  };

  const iniciarPollingProceso = (procesoId) => {
    detenerPolling();

    pollingRef.current = setInterval(async () => {
      try {
        const res = await axiosClient.get(`/procesos-masivos/${procesoId}`);
        const proc = res.data;
        setProcesoMasivo(proc);

        if (proc.estado === 'COMPLETADO' || proc.estado === 'COMPLETADO_CON_ERRORES' || proc.estado === 'ERROR') {
          detenerPolling();
          setValidandoMasivo(false);
          await cargarResultadosItems(procesoId);
        }
      } catch (err) {
        console.error('Error en polling de proceso masivo:', err);
      }
    }, 1500);
  };

  const cargarResultadosItems = async (procesoId) => {
    try {
      const res = await axiosClient.get(`/procesos-masivos/${procesoId}/items?page=1&page_size=200`);
      const mapaResultados = new Map();
      res.data.items.forEach((r) => {
        if (r.fila_excel) {
          mapaResultados.set(r.fila_excel, r);
        }
      });

      setPreviewData((prev) => {
        if (!prev) return prev;
        const filasActualizadas = prev.filas.map((f) => {
          if (mapaResultados.has(f.fila_excel)) {
            const r = mapaResultados.get(f.fila_excel);
            return {
              ...f,
              estado_sunat: r.estado,
              codigo_sunat: r.codigo_sunat,
              mensaje_sunat: r.mensaje_sunat,
            };
          }
          return f;
        });
        return { ...prev, filas: filasActualizadas };
      });
    } catch (err) {
      console.error('Error al cargar items finales del proceso:', err);
    }
  };

  const handleReintentarErrores = async () => {
    if (!procesoMasivo || validandoMasivo) return;
    setErrorValidacionMasiva(null);
    setValidandoMasivo(true);

    try {
      await axiosClient.post(`/procesos-masivos/${procesoMasivo.id}/reintentar-errores`);
      iniciarPollingProceso(procesoMasivo.id);
    } catch (err) {
      console.error('Error al reintentar comprobantes:', err);
      const msg = err.response?.data?.detail || 'No fue posible reintentar los comprobantes con error.';
      setErrorValidacionMasiva(msg);
      setValidandoMasivo(false);
    }
  };

  // Filtrado de filas
  const filasFiltradas = previewData?.filas.filter((fila) => {
    // Filtro por estado
    if (filtroEstado !== 'TODOS' && fila.estado_archivo !== filtroEstado) {
      return false;
    }
    // Búsqueda por texto libre
    if (busqueda.trim()) {
      const q = busqueda.toLowerCase().trim();
      const ruc = fila.num_ruc?.toLowerCase() || '';
      const serie = fila.numero_serie?.toLowerCase() || '';
      const num = fila.numero?.toLowerCase() || '';
      const razon = fila.razon_social_emisor?.toLowerCase() || '';
      const tipo = fila.tipo_descripcion?.toLowerCase() || '';
      return (
        ruc.includes(q) ||
        serie.includes(q) ||
        num.includes(q) ||
        razon.includes(q) ||
        tipo.includes(q)
      );
    }
    return true;
  }) || [];

  // Filas en estado LISTO dentro del dataset
  const filasTotalesListas = previewData?.filas.filter((f) => f.estado_archivo === 'LISTO') || [];
  const todasListasSeleccionadas =
    filasTotalesListas.length > 0 &&
    filasTotalesListas.every((f) => seleccionados.has(f.fila_excel));

  const toggleSeleccionarTodas = () => {
    if (todasListasSeleccionadas) {
      setSeleccionados(new Set());
    } else {
      const nuevoSet = new Set(filasTotalesListas.map((f) => f.fila_excel));
      setSeleccionados(nuevoSet);
    }
  };

  const toggleFila = (filaExcel) => {
    const nuevoSet = new Set(seleccionados);
    if (nuevoSet.has(filaExcel)) {
      nuevoSet.delete(filaExcel);
    } else {
      nuevoSet.add(filaExcel);
    }
    setSeleccionados(nuevoSet);
  };

  return (
    <div className="dashboard-content" style={{ maxWidth: '1440px', margin: '0 auto', padding: '1.5rem' }}>
      {/* Encabezado */}
      <div style={{ marginBottom: '1.5rem' }}>
        <h2 style={{ fontSize: '1.5rem', fontWeight: '700', color: 'var(--color-text-main)', margin: '0 0 0.25rem 0' }}>
          Carga Masiva de Registro de Compras
        </h2>
        <p style={{ color: 'var(--color-text-muted)', fontSize: '0.875rem', margin: 0 }}>
          Lectura, normalización y detección estructural de comprobantes desde el Formato 8.1 de Excel (.xlsx)
        </p>
      </div>

      {/* Zona de Carga / Drag & Drop */}
      {!previewData && (
        <div
          onDragEnter={handleDrag}
          onDragLeave={handleDrag}
          onDragOver={handleDrag}
          onDrop={handleDrop}
          onClick={() => !loading && fileInputRef.current?.click()}
          style={{
            border: `2px dashed ${dragActive ? 'var(--color-primary)' : '#cbd5e1'}`,
            borderRadius: '12px',
            backgroundColor: dragActive ? '#eff6ff' : '#f8fafc',
            padding: '3rem 2rem',
            textAlign: 'center',
            cursor: loading ? 'wait' : 'pointer',
            transition: 'all 0.2s ease',
            marginBottom: '1.5rem',
          }}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".xlsx"
            style={{ display: 'none' }}
            onChange={handleFileInput}
            disabled={loading}
          />
          {loading ? (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '1rem' }}>
              <Loader2 size={48} className="spin" style={{ color: 'var(--color-primary)' }} />
              <div>
                <p style={{ fontWeight: '600', fontSize: '1.1rem', color: 'var(--color-text-main)', margin: 0 }}>
                  Analizando y estructurando libro contable...
                </p>
                <p style={{ fontSize: '0.85rem', color: 'var(--color-text-muted)', marginTop: '0.25rem' }}>
                  Resolviendo celdas combinadas y detectando encabezados del Formato 8.1
                </p>
              </div>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.75rem' }}>
              <div
                style={{
                  width: '64px',
                  height: '64px',
                  borderRadius: '50%',
                  backgroundColor: '#e0f2fe',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: '#0284c7',
                }}
              >
                <UploadCloud size={32} />
              </div>
              <h3 style={{ fontSize: '1.125rem', fontWeight: '600', color: 'var(--color-text-main)', margin: 0 }}>
                Arrastra tu archivo Excel aquí o haz clic para examinar
              </h3>
              <p style={{ fontSize: '0.875rem', color: 'var(--color-text-muted)', margin: 0 }}>
                Soporta archivos de Registro de Compras Formato 8.1 (.xlsx) hasta 10MB
              </p>
              <div
                style={{
                  marginTop: '0.5rem',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                  padding: '0.4rem 0.85rem',
                  backgroundColor: '#ffffff',
                  border: '1px solid #e2e8f0',
                  borderRadius: '6px',
                  fontSize: '0.75rem',
                  color: '#475569',
                }}
              >
                <FileSpreadsheet size={14} color="#16a34a" />
                <span>Compatible con sistemas Concar, Siscont, StarSoft y formato SUNAT oficial</span>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Alerta de Error */}
      {errorMsg && (
        <div
          style={{
            backgroundColor: '#fef2f2',
            border: '1px solid #fecaca',
            color: '#991b1b',
            padding: '1rem',
            borderRadius: '8px',
            marginBottom: '1.5rem',
            display: 'flex',
            alignItems: 'center',
            gap: '0.75rem',
          }}
        >
          <AlertCircle size={20} />
          <div>
            <strong style={{ display: 'block', fontSize: '0.875rem' }}>Error al procesar archivo</strong>
            <span style={{ fontSize: '0.825rem' }}>{errorMsg}</span>
          </div>
        </div>
      )}

      {/* Vista de Previsualización y Diagnóstico */}
      {previewData && (
        <div>
          {/* Barra de Archivo Activo y Diagnóstico */}
          <div
            style={{
              backgroundColor: '#ffffff',
              border: '1px solid var(--color-border)',
              borderRadius: '10px',
              padding: '1rem 1.25rem',
              marginBottom: '1.5rem',
              display: 'flex',
              flexWrap: 'wrap',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: '1rem',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              <div
                style={{
                  width: '40px',
                  height: '40px',
                  borderRadius: '8px',
                  backgroundColor: '#ecfdf5',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: '#059669',
                }}
              >
                <FileSpreadsheet size={22} />
              </div>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <span style={{ fontWeight: '600', color: 'var(--color-text-main)', fontSize: '0.95rem' }}>
                    {previewData.nombre_archivo}
                  </span>
                  <span
                    style={{
                      fontSize: '0.7rem',
                      padding: '0.15rem 0.5rem',
                      borderRadius: '4px',
                      backgroundColor: '#e2e8f0',
                      color: '#334155',
                      fontWeight: '600',
                    }}
                  >
                    Hoja: {previewData.diagnostico.hoja_detectada}
                  </span>
                </div>
                <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', marginTop: '0.15rem' }}>
                  Encabezados detectados entre filas {previewData.diagnostico.fila_inicio_encabezado} y{' '}
                  {previewData.diagnostico.fila_fin_encabezado} • {previewData.total_filas_detectadas} filas operativas
                </div>
              </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <button
                onClick={handleReset}
                className="btn-secondary"
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '0.4rem',
                  padding: '0.5rem 0.85rem',
                  fontSize: '0.8rem',
                  backgroundColor: '#ffffff',
                  border: '1px solid #cbd5e1',
                  borderRadius: '6px',
                  cursor: 'pointer',
                  color: '#475569',
                }}
              >
                <Trash2 size={15} />
                <span>Cargar otro archivo</span>
              </button>
            </div>
          </div>

          {/* Tarjetas de Resumen KPI */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
              gap: '1rem',
              marginBottom: '1.5rem',
            }}
          >
            {/* Total Filas */}
            <div
              style={{
                backgroundColor: '#ffffff',
                border: '1px solid var(--color-border)',
                borderRadius: '8px',
                padding: '1rem',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', color: '#64748b' }}>
                <span style={{ fontSize: '0.8rem', fontWeight: '500' }}>TOTAL COMPROBANTES</span>
                <Layers size={18} />
              </div>
              <div style={{ fontSize: '1.75rem', fontWeight: '700', color: 'var(--color-text-main)', marginTop: '0.35rem' }}>
                {previewData.total_filas_detectadas}
              </div>
              <div style={{ fontSize: '0.725rem', color: 'var(--color-text-muted)' }}>Filas contables detectadas</div>
            </div>

            {/* Listos */}
            <div
              style={{
                backgroundColor: '#ffffff',
                border: '1px solid #bbf7d0',
                borderRadius: '8px',
                padding: '1rem',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', color: '#16a34a' }}>
                <span style={{ fontSize: '0.8rem', fontWeight: '500' }}>LISTOS PARA VALIDAR</span>
                <CheckCircle2 size={18} />
              </div>
              <div style={{ fontSize: '1.75rem', fontWeight: '700', color: '#15803d', marginTop: '0.35rem' }}>
                {previewData.total_listos}
              </div>
              <div style={{ fontSize: '0.725rem', color: '#16a34a' }}>Formato local válido</div>
            </div>

            {/* Errores */}
            <div
              style={{
                backgroundColor: '#ffffff',
                border: '1px solid #fecaca',
                borderRadius: '8px',
                padding: '1rem',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', color: '#dc2626' }}>
                <span style={{ fontSize: '0.8rem', fontWeight: '500' }}>ERRORES DE FORMATO</span>
                <XCircle size={18} />
              </div>
              <div style={{ fontSize: '1.75rem', fontWeight: '700', color: '#b91c1c', marginTop: '0.35rem' }}>
                {previewData.total_errores}
              </div>
              <div style={{ fontSize: '0.725rem', color: '#dc2626' }}>Datos incompletos o inválidos</div>
            </div>

            {/* Duplicados */}
            <div
              style={{
                backgroundColor: '#ffffff',
                border: '1px solid #fed7aa',
                borderRadius: '8px',
                padding: '1rem',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', color: '#ea580c' }}>
                <span style={{ fontSize: '0.8rem', fontWeight: '500' }}>DUPLICADOS</span>
                <AlertTriangle size={18} />
              </div>
              <div style={{ fontSize: '1.75rem', fontWeight: '700', color: '#c2410c', marginTop: '0.35rem' }}>
                {previewData.total_duplicados}
              </div>
              <div style={{ fontSize: '0.725rem', color: '#ea580c' }}>Mismo comprobante repetido</div>
            </div>

            {/* No Soportados */}
            <div
              style={{
                backgroundColor: '#ffffff',
                border: '1px solid #e2e8f0',
                borderRadius: '8px',
                padding: '1rem',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', color: '#64748b' }}>
                <span style={{ fontSize: '0.8rem', fontWeight: '500' }}>NO SOPORTADOS</span>
                <Info size={18} />
              </div>
              <div style={{ fontSize: '1.75rem', fontWeight: '700', color: '#475569', marginTop: '0.35rem' }}>
                {previewData.total_no_soportados}
              </div>
              <div style={{ fontSize: '0.725rem', color: '#64748b' }}>Doc/Tipo fuera de alcance</div>
            </div>
          </div>

          {/* Barra de Acciones y Filtros */}
          <div
            style={{
              backgroundColor: '#ffffff',
              border: '1px solid var(--color-border)',
              borderRadius: '8px 8px 0 0',
              padding: '0.85rem 1.25rem',
              display: 'flex',
              flexWrap: 'wrap',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: '1rem',
            }}
          >
            {/* Pestañas de Filtro */}
            <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap' }}>
              {[
                { id: 'TODOS', label: `Todos (${previewData.total_filas_detectadas})` },
                { id: 'LISTO', label: `Listos (${previewData.total_listos})`, color: '#16a34a' },
                { id: 'ERROR', label: `Errores (${previewData.total_errores})`, color: '#dc2626' },
                { id: 'DUPLICADO', label: `Duplicados (${previewData.total_duplicados})`, color: '#ea580c' },
                { id: 'NO_SOPORTADO', label: `No Soportados (${previewData.total_no_soportados})`, color: '#64748b' },
              ].map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setFiltroEstado(tab.id)}
                  style={{
                    padding: '0.4rem 0.75rem',
                    borderRadius: '6px',
                    fontSize: '0.785rem',
                    fontWeight: '600',
                    border: 'none',
                    cursor: 'pointer',
                    backgroundColor: filtroEstado === tab.id ? 'var(--color-primary)' : '#f1f5f9',
                    color: filtroEstado === tab.id ? '#ffffff' : tab.color || 'var(--color-text-main)',
                    transition: 'all 0.15s ease',
                  }}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            {/* Búsqueda rápida */}
            <div style={{ position: 'relative', width: '280px' }}>
              <Search
                size={16}
                style={{ position: 'absolute', left: '0.75rem', top: '50%', transform: 'translateY(-50%)', color: '#94a3b8' }}
              />
              <input
                type="text"
                placeholder="Buscar RUC, serie, correlativo..."
                value={busqueda}
                onChange={(e) => setBusqueda(e.target.value)}
                style={{
                  width: '100%',
                  padding: '0.45rem 0.75rem 0.45rem 2.25rem',
                  fontSize: '0.8rem',
                  border: '1px solid #cbd5e1',
                  borderRadius: '6px',
                  outline: 'none',
                }}
              />
            </div>
          </div>

          {/* Subbarra de Selección y Acción Masiva (Precisión 11) */}
          <div
            style={{
              backgroundColor: '#f8fafc',
              borderLeft: '1px solid var(--color-border)',
              borderRight: '1px solid var(--color-border)',
              borderBottom: '1px solid var(--color-border)',
              padding: '0.75rem 1.25rem',
              display: 'flex',
              flexWrap: 'wrap',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: '1rem',
            }}
          >
            {/* Control Seleccionar Todos los LISTO */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
              <button
                onClick={toggleSeleccionarTodas}
                disabled={filasTotalesListas.length === 0}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '0.4rem',
                  backgroundColor: 'transparent',
                  border: 'none',
                  fontSize: '0.8rem',
                  fontWeight: '600',
                  color: 'var(--color-text-main)',
                  cursor: filasTotalesListas.length > 0 ? 'pointer' : 'default',
                  opacity: filasTotalesListas.length > 0 ? 1 : 0.5,
                }}
              >
                {todasListasSeleccionadas ? (
                  <CheckSquare size={18} color="var(--color-primary)" />
                ) : (
                  <Square size={18} color="#94a3b8" />
                )}
                <span>Seleccionar todos los LISTO</span>
              </button>

              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
                <span
                  style={{
                    fontSize: '0.75rem',
                    backgroundColor: '#dcfce7',
                    color: '#15803d',
                    padding: '0.2rem 0.6rem',
                    borderRadius: '4px',
                    fontWeight: '600',
                  }}
                >
                  {previewData.total_listos} comprobantes listos
                </span>
                <span style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)' }}>
                  <strong>{seleccionados.size}</strong> de {previewData.total_listos} seleccionados
                </span>
              </div>
            </div>

            {/* Botón Dinámico VALIDAR SELECCIONADOS EN SUNAT */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              <button
                onClick={handleValidarMasivo}
                disabled={seleccionados.size === 0 || validandoMasivo}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                  padding: '0.55rem 1.25rem',
                  backgroundColor: seleccionados.size > 0 && !validandoMasivo ? 'var(--color-primary)' : '#94a3b8',
                  color: '#ffffff',
                  border: 'none',
                  borderRadius: '6px',
                  fontWeight: '600',
                  fontSize: '0.825rem',
                  cursor: seleccionados.size > 0 && !validandoMasivo ? 'pointer' : 'not-allowed',
                  opacity: seleccionados.size > 0 && !validandoMasivo ? 1 : 0.7,
                  transition: 'background-color 0.2s ease',
                }}
              >
                {validandoMasivo ? (
                  <>
                    <Loader2 size={16} className="spin" />
                    <span>Procesando {seleccionados.size} comprobantes...</span>
                  </>
                ) : (
                  <>
                    <span>VALIDAR {seleccionados.size} SELECCIONADOS EN SUNAT</span>
                    <ArrowRight size={16} />
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Alerta de Límite de Seguridad o Error Masivo */}
          {errorValidacionMasiva && (
            <div
              style={{
                backgroundColor: '#fef2f2',
                border: '1px solid #fecaca',
                color: '#991b1b',
                padding: '1rem',
                borderRadius: '8px',
                marginBottom: '1.5rem',
                display: 'flex',
                alignItems: 'center',
                gap: '0.75rem',
              }}
            >
              <AlertCircle size={20} />
              <div>
                <strong style={{ display: 'block', fontSize: '0.875rem' }}>Aviso de Validación Masiva</strong>
                <span style={{ fontSize: '0.825rem' }}>{errorValidacionMasiva}</span>
              </div>
            </div>
          )}

          {/* Panel de Progreso Dinámico y Resumen de Proceso Masivo */}
          {(validandoMasivo || procesoMasivo) && (
            <div
              style={{
                backgroundColor: '#ffffff',
                border: '1px solid #bfdbfe',
                borderRadius: '8px',
                padding: '1.25rem',
                marginBottom: '1.5rem',
                boxShadow: '0 1px 3px rgba(0, 0, 0, 0.05)',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
                <div>
                  <h4 style={{ margin: 0, fontSize: '1rem', fontWeight: '700', color: 'var(--color-text-main)' }}>
                    {validandoMasivo ? 'Procesando validación masiva en SUNAT...' : 'Proceso Masivo Completado'}
                  </h4>
                  <div style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)', marginTop: '0.25rem' }}>
                    Número total de comprobantes: <strong>{procesoMasivo ? procesoMasivo.total_registros : seleccionados.size}</strong>
                    {' • '}
                    {validandoMasivo
                      ? `Procesando comprobantes seleccionados...`
                      : `Procesados ${procesoMasivo?.total_procesados || 0} de ${procesoMasivo?.total_registros || 0}`}
                  </div>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <span style={{ fontSize: '1.35rem', fontWeight: '700', color: 'var(--color-primary)' }}>
                    {procesoMasivo ? `${procesoMasivo.porcentaje}%` : '0%'}
                  </span>
                </div>
              </div>

              {/* Barra de Progreso Dinámica */}
              <div
                style={{
                  width: '100%',
                  height: '10px',
                  backgroundColor: '#e2e8f0',
                  borderRadius: '5px',
                  overflow: 'hidden',
                  marginBottom: '1rem',
                }}
              >
                <div
                  style={{
                    width: `${procesoMasivo ? procesoMasivo.porcentaje : (validandoMasivo ? 20 : 0)}%`,
                    height: '100%',
                    backgroundColor: procesoMasivo?.estado === 'COMPLETADO' ? '#16a34a' : 'var(--color-primary)',
                    transition: 'width 0.4s ease',
                  }}
                />
              </div>

              {/* Contadores dinámicos del proceso masivo */}
              {procesoMasivo && (
                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))',
                    gap: '0.75rem',
                    paddingTop: '0.5rem',
                    borderTop: '1px solid #f1f5f9',
                  }}
                >
                  <div style={{ backgroundColor: '#f8fafc', padding: '0.6rem 0.75rem', borderRadius: '6px' }}>
                    <div style={{ fontSize: '0.7rem', color: '#64748b' }}>TOTAL PROCESO</div>
                    <div style={{ fontSize: '1.15rem', fontWeight: '700', color: 'var(--color-text-main)' }}>
                      {procesoMasivo.total_registros}
                    </div>
                  </div>
                  <div style={{ backgroundColor: '#ecfdf5', padding: '0.6rem 0.75rem', borderRadius: '6px' }}>
                    <div style={{ fontSize: '0.7rem', color: '#059669' }}>VÁLIDOS (SUNAT)</div>
                    <div style={{ fontSize: '1.15rem', fontWeight: '700', color: '#059669' }}>
                      {procesoMasivo.total_validos}
                    </div>
                  </div>
                  <div style={{ backgroundColor: '#fef2f2', padding: '0.6rem 0.75rem', borderRadius: '6px' }}>
                    <div style={{ fontSize: '0.7rem', color: '#dc2626' }}>NO VÁLIDOS</div>
                    <div style={{ fontSize: '1.15rem', fontWeight: '700', color: '#dc2626' }}>
                      {procesoMasivo.total_no_validos}
                    </div>
                  </div>
                  <div style={{ backgroundColor: '#fefce8', padding: '0.6rem 0.75rem', borderRadius: '6px' }}>
                    <div style={{ fontSize: '0.7rem', color: '#a16207' }}>OBSERVADOS</div>
                    <div style={{ fontSize: '1.15rem', fontWeight: '700', color: '#a16207' }}>
                      {procesoMasivo.total_observados}
                    </div>
                  </div>
                  <div style={{ backgroundColor: '#fef2f2', padding: '0.6rem 0.75rem', borderRadius: '6px' }}>
                    <div style={{ fontSize: '0.7rem', color: '#991b1b' }}>ERRORES / RED</div>
                    <div style={{ fontSize: '1.15rem', fontWeight: '700', color: '#991b1b' }}>
                      {procesoMasivo.total_errores}
                    </div>
                  </div>
                </div>
              )}

              {/* Botón para Reintentar Errores Técnicos y Ver Detalle Completo */}
              {procesoMasivo && !validandoMasivo && (
                <div style={{ marginTop: '1rem', display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', flexWrap: 'wrap' }}>
                  {procesoMasivo.total_errores > 0 && (
                    <button
                      onClick={handleReintentarErrores}
                      style={{
                        padding: '0.45rem 1rem',
                        fontSize: '0.8rem',
                        fontWeight: '600',
                        backgroundColor: '#dc2626',
                        color: '#ffffff',
                        border: 'none',
                        borderRadius: '6px',
                        cursor: 'pointer',
                      }}
                    >
                      Reintentar {procesoMasivo.total_errores} comprobantes con error técnico
                    </button>
                  )}
                  <button
                    onClick={() => navigate(`/historial/${procesoMasivo.id}`)}
                    style={{
                      padding: '0.45rem 1rem',
                      fontSize: '0.8rem',
                      fontWeight: '600',
                      backgroundColor: 'var(--color-primary, #1e40af)',
                      color: '#ffffff',
                      border: 'none',
                      borderRadius: '6px',
                      cursor: 'pointer',
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '0.4rem',
                    }}
                  >
                    <span>Ver resultados completos en Historial</span>
                    <ArrowRight size={14} />
                  </button>
                </div>
              )}
            </div>
          )}

          {/* Tabla Preview */}
          <div
            style={{
              backgroundColor: '#ffffff',
              borderLeft: '1px solid var(--color-border)',
              borderRight: '1px solid var(--color-border)',
              borderBottom: '1px solid var(--color-border)',
              borderRadius: '0 0 8px 8px',
              overflowX: 'auto',
            }}
          >
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem', textAlign: 'left' }}>
              <thead>
                <tr style={{ backgroundColor: '#f1f5f9', color: '#475569', borderBottom: '1px solid #e2e8f0' }}>
                  <th style={{ padding: '0.65rem 0.85rem', width: '40px', textAlign: 'center' }}>
                    <span style={{ fontSize: '0.7rem' }}>SEL</span>
                  </th>
                  <th style={{ padding: '0.65rem 0.85rem' }}>FILA</th>
                  <th style={{ padding: '0.65rem 0.85rem' }}>ESTADO ARCHIVO</th>
                  <th style={{ padding: '0.65rem 0.85rem' }}>ESTADO SUNAT</th>
                  <th style={{ padding: '0.65rem 0.85rem' }}>RUC EMISOR</th>
                  <th style={{ padding: '0.65rem 0.85rem' }}>DOC. TIPO</th>
                  <th style={{ padding: '0.65rem 0.85rem' }}>COMPROBANTE</th>
                  <th style={{ padding: '0.65rem 0.85rem' }}>SERIE</th>
                  <th style={{ padding: '0.65rem 0.85rem' }}>NÚMERO</th>
                  <th style={{ padding: '0.65rem 0.85rem' }}>FECHA EMISIÓN</th>
                  <th style={{ padding: '0.65rem 0.85rem', textAlign: 'right' }}>BASE IMPONIBLE</th>
                  <th style={{ padding: '0.65rem 0.85rem', textAlign: 'right' }}>IGV</th>
                  <th style={{ padding: '0.65rem 0.85rem', textAlign: 'right' }}>BASE + IGV</th>
                  <th style={{ padding: '0.65rem 0.85rem', textAlign: 'right' }}>NO GRAVADAS</th>
                  <th style={{ padding: '0.65rem 0.85rem', textAlign: 'right' }}>MONTO CALCULADO</th>
                  <th style={{ padding: '0.65rem 0.85rem', textAlign: 'right' }}>TIPO CAMBIO</th>
                  <th style={{ padding: '0.65rem 0.85rem', textAlign: 'right' }}>CONVERTIDO</th>
                  <th style={{ padding: '0.65rem 0.85rem', textAlign: 'right' }}>MONTO SUNAT</th>
                  <th style={{ padding: '0.65rem 0.85rem', textAlign: 'right' }}>TOTAL EXCEL</th>
                  <th style={{ padding: '0.65rem 0.85rem' }}>RAZÓN SOCIAL</th>
                  <th style={{ padding: '0.65rem 0.85rem' }}>OBSERVACIONES</th>
                </tr>
              </thead>
              <tbody>
                {filasFiltradas.length === 0 ? (
                  <tr>
                    <td colSpan={21} style={{ padding: '2rem', textAlign: 'center', color: '#94a3b8' }}>
                      No se encontraron comprobantes que coincidan con el filtro seleccionado.
                    </td>
                  </tr>
                ) : (
                  filasFiltradas.map((fila) => {
                    const esListo = fila.estado_archivo === 'LISTO';
                    const isChecked = seleccionados.has(fila.fila_excel);

                    // Badge de Estado Archivo (Precisión 8: nunca estado SUNAT en Fase 3)
                    let badgeBg = '#f1f5f9';
                    let badgeColor = '#475569';
                    if (fila.estado_archivo === 'LISTO') {
                      badgeBg = '#dcfce7';
                      badgeColor = '#15803d';
                    } else if (fila.estado_archivo === 'ERROR') {
                      badgeBg = '#fee2e2';
                      badgeColor = '#b91c1c';
                    } else if (fila.estado_archivo === 'DUPLICADO') {
                      badgeBg = '#ffedd5';
                      badgeColor = '#c2410c';
                    } else if (fila.estado_archivo === 'NO_SOPORTADO') {
                      badgeBg = '#f1f5f9';
                      badgeColor = '#64748b';
                    }

                    const esMontoNegativo = fila.monto_original && parseFloat(fila.monto_original) < 0;

                    return (
                      <tr
                        key={fila.fila_excel}
                        style={{
                          borderBottom: '1px solid #f1f5f9',
                          backgroundColor: isChecked ? '#f0fdf4' : 'transparent',
                          transition: 'background-color 0.1s ease',
                        }}
                      >
                        {/* Checkbox solo para LISTO (Precisión 11) */}
                        <td style={{ padding: '0.6rem 0.85rem', textAlign: 'center' }}>
                          {esListo ? (
                            <button
                              type="button"
                              onClick={() => toggleFila(fila.fila_excel)}
                              style={{
                                background: 'none',
                                border: 'none',
                                cursor: 'pointer',
                                padding: 0,
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                              }}
                            >
                              {isChecked ? (
                                <CheckSquare size={16} color="var(--color-primary)" />
                              ) : (
                                <Square size={16} color="#94a3b8" />
                              )}
                            </button>
                          ) : (
                            <span style={{ color: '#cbd5e1', fontSize: '0.7rem' }}>—</span>
                          )}
                        </td>

                        {/* Fila Excel */}
                        <td style={{ padding: '0.6rem 0.85rem', color: '#64748b', fontWeight: '500' }}>
                          {fila.fila_excel}
                        </td>

                        {/* Estado Archivo */}
                        <td style={{ padding: '0.6rem 0.85rem' }}>
                          <span
                            style={{
                              display: 'inline-block',
                              padding: '0.2rem 0.55rem',
                              borderRadius: '4px',
                              fontSize: '0.7rem',
                              fontWeight: '700',
                              backgroundColor: badgeBg,
                              color: badgeColor,
                            }}
                          >
                            {fila.estado_archivo}
                          </span>
                        </td>

                        {/* Estado SUNAT */}
                        <td style={{ padding: '0.6rem 0.85rem' }}>
                          {fila.estado_sunat ? (
                            <span
                              style={{
                                display: 'inline-block',
                                padding: '0.2rem 0.55rem',
                                borderRadius: '4px',
                                fontSize: '0.7rem',
                                fontWeight: '700',
                                backgroundColor:
                                  fila.estado_sunat === 'VALIDO'
                                    ? '#dcfce7'
                                    : fila.estado_sunat === 'NO_VALIDO'
                                    ? '#fee2e2'
                                    : fila.estado_sunat === 'ANULADO'
                                    ? '#ffedd5'
                                    : fila.estado_sunat === 'OBSERVADO'
                                    ? '#fef9c3'
                                    : '#fee2e2',
                                color:
                                  fila.estado_sunat === 'VALIDO'
                                    ? '#15803d'
                                    : fila.estado_sunat === 'NO_VALIDO'
                                    ? '#b91c1c'
                                    : fila.estado_sunat === 'ANULADO'
                                    ? '#c2410c'
                                    : fila.estado_sunat === 'OBSERVADO'
                                    ? '#a16207'
                                    : '#991b1b',
                              }}
                            >
                              {fila.estado_sunat}
                            </span>
                          ) : (
                            <span style={{ color: '#94a3b8', fontSize: '0.725rem' }}>Pendiente</span>
                          )}
                        </td>

                        {/* RUC Emisor */}
                        <td style={{ padding: '0.6rem 0.85rem', fontFamily: 'monospace', fontWeight: '600' }}>
                          {fila.num_ruc || <span style={{ color: '#dc2626' }}>Faltante</span>}
                        </td>

                        {/* Tipo Doc Identidad */}
                        <td style={{ padding: '0.6rem 0.85rem', color: '#475569' }}>
                          {fila.tipo_doc_identidad ? `Tipo ${fila.tipo_doc_identidad}` : '—'}
                        </td>

                        {/* Comprobante Tipo */}
                        <td style={{ padding: '0.6rem 0.85rem' }}>
                          <span style={{ fontWeight: '500' }}>{fila.cod_comp}</span> -{' '}
                          <span style={{ color: '#64748b', fontSize: '0.75rem' }}>{fila.tipo_descripcion}</span>
                        </td>

                        {/* Serie */}
                        <td style={{ padding: '0.6rem 0.85rem', fontFamily: 'monospace', fontWeight: '600' }}>
                          {fila.numero_serie || '—'}
                        </td>

                        {/* Número */}
                        <td style={{ padding: '0.6rem 0.85rem', fontFamily: 'monospace', fontWeight: '600' }}>
                          {fila.numero || '—'}
                        </td>

                        {/* Fecha Emisión */}
                        <td style={{ padding: '0.6rem 0.85rem', color: '#334155' }}>
                          {fila.fecha_emision || '—'}
                        </td>

                        {/* Base Imponible */}
                        <td
                          style={{
                            padding: '0.6rem 0.85rem',
                            textAlign: 'right',
                            fontFamily: 'monospace',
                            color: esMontoNegativo ? '#dc2626' : '#0f172a',
                            fontWeight: esMontoNegativo ? '600' : '400',
                          }}
                        >
                          {fila.base_imponible !== null && fila.base_imponible !== undefined
                            ? Number(fila.base_imponible).toLocaleString('es-PE', { minimumFractionDigits: 2 })
                            : '—'}
                        </td>

                        {/* IGV */}
                        <td
                          style={{
                            padding: '0.6rem 0.85rem',
                            textAlign: 'right',
                            fontFamily: 'monospace',
                            color: esMontoNegativo ? '#dc2626' : '#0f172a',
                          }}
                        >
                          {fila.igv !== null && fila.igv !== undefined
                            ? Number(fila.igv).toLocaleString('es-PE', { minimumFractionDigits: 2 })
                            : '—'}
                        </td>

                        {/* Base + IGV */}
                        <td
                          style={{
                            padding: '0.6rem 0.85rem',
                            textAlign: 'right',
                            fontFamily: 'monospace',
                            fontWeight: '600',
                            color: esMontoNegativo ? '#dc2626' : '#334155',
                          }}
                        >
                          {fila.monto_base_igv !== null && fila.monto_base_igv !== undefined
                            ? Number(fila.monto_base_igv).toLocaleString('es-PE', { minimumFractionDigits: 2 })
                            : '—'}
                        </td>

                        {/* No Gravadas */}
                        <td
                          style={{
                            padding: '0.6rem 0.85rem',
                            textAlign: 'right',
                            fontFamily: 'monospace',
                            color: esMontoNegativo ? '#dc2626' : '#0f172a',
                          }}
                        >
                          {fila.valor_adquisiciones_no_gravadas !== null && fila.valor_adquisiciones_no_gravadas !== undefined
                            ? Number(fila.valor_adquisiciones_no_gravadas).toLocaleString('es-PE', { minimumFractionDigits: 2 })
                            : '—'}
                        </td>

                        {/* Monto Calculado Original (Base + IGV + No Gravadas) */}
                        <td
                          style={{
                            padding: '0.6rem 0.85rem',
                            textAlign: 'right',
                            fontFamily: 'monospace',
                            fontWeight: '600',
                            color: esMontoNegativo ? '#dc2626' : '#0f172a',
                          }}
                        >
                          {fila.monto_calculado_original !== null && fila.monto_calculado_original !== undefined
                            ? Number(fila.monto_calculado_original).toLocaleString('es-PE', { minimumFractionDigits: 2 })
                            : '—'}
                        </td>

                        {/* Tipo de Cambio */}
                        <td
                          style={{
                            padding: '0.6rem 0.85rem',
                            textAlign: 'right',
                            fontFamily: 'monospace',
                            fontWeight: fila.tipo_cambio ? '600' : '400',
                            color: fila.tipo_cambio ? '#2563eb' : '#94a3b8',
                          }}
                        >
                          {fila.tipo_cambio !== null && fila.tipo_cambio !== undefined
                            ? Number(fila.tipo_cambio).toFixed(3)
                            : '—'}
                        </td>

                        {/* Monto Convertido */}
                        <td
                          style={{
                            padding: '0.6rem 0.85rem',
                            textAlign: 'right',
                            fontFamily: 'monospace',
                            fontWeight: fila.monto_convertido ? '600' : '400',
                            color: fila.monto_convertido ? (esMontoNegativo ? '#dc2626' : '#7c3aed') : '#94a3b8',
                          }}
                        >
                          {fila.monto_convertido !== null && fila.monto_convertido !== undefined
                            ? Number(fila.monto_convertido).toLocaleString('es-PE', { minimumFractionDigits: 2 })
                            : '—'}
                        </td>

                        {/* Monto SUNAT (Positivo) */}
                        <td
                          style={{
                            padding: '0.6rem 0.85rem',
                            textAlign: 'right',
                            fontFamily: 'monospace',
                            fontWeight: '700',
                            color: '#16a34a',
                          }}
                        >
                          {fila.monto !== null && fila.monto !== undefined
                            ? Number(fila.monto).toLocaleString('es-PE', { minimumFractionDigits: 2 })
                            : '—'}
                        </td>

                        {/* Total Excel */}
                        <td
                          style={{
                            padding: '0.6rem 0.85rem',
                            textAlign: 'right',
                            fontFamily: 'monospace',
                            color: '#64748b',
                            fontSize: '0.75rem',
                          }}
                        >
                          {fila.importe_total_excel !== null && fila.importe_total_excel !== undefined
                            ? Number(fila.importe_total_excel).toLocaleString('es-PE', { minimumFractionDigits: 2 })
                            : '—'}
                        </td>

                        {/* Razón Social */}
                        <td
                          style={{
                            padding: '0.6rem 0.85rem',
                            maxWidth: '180px',
                            whiteSpace: 'nowrap',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            color: '#334155',
                          }}
                          title={fila.razon_social_emisor || ''}
                        >
                          {fila.razon_social_emisor || '—'}
                        </td>

                        {/* Observaciones / Errores */}
                        <td style={{ padding: '0.6rem 0.85rem' }}>
                          {fila.errores.length > 0 ? (
                            <ul style={{ margin: 0, paddingLeft: '1rem', color: '#b91c1c', fontSize: '0.725rem' }}>
                              {fila.errores.map((err, idx) => (
                                <li key={idx}>{err}</li>
                              ))}
                            </ul>
                          ) : (
                            <span style={{ color: '#16a34a', fontSize: '0.75rem' }}>Correcto</span>
                          )}
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};
