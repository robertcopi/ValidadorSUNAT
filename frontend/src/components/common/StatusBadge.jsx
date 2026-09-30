import React from 'react';
import { CheckCircle2, XCircle, AlertTriangle, AlertOctagon, Clock, Loader2 } from 'lucide-react';

/**
 * Componente unificado para los estados oficiales del validador SUNAT.
 * Estados internos estrictos: VALIDO, NO_VALIDO, OBSERVADO, ERROR.
 */
export const StatusBadge = ({ estado, showIcon = true, size = 'md' }) => {
  const normalized = (estado || '').toUpperCase().trim();

  let className = 'badge';
  let label = normalized;
  let Icon = null;
  let style = {};

  switch (normalized) {
    case 'VALIDO':
      className += ' badge-success';
      label = 'VÁLIDO';
      Icon = CheckCircle2;
      break;
    case 'NO_VALIDO':
      className += ' badge-danger';
      label = 'NO VÁLIDO';
      Icon = XCircle;
      break;
    case 'OBSERVADO':
      className += ' badge-warning';
      label = 'OBSERVADO';
      Icon = AlertTriangle;
      break;
    case 'ERROR':
      className += ' badge-danger';
      label = 'ERROR';
      Icon = AlertOctagon;
      style = { backgroundColor: '#fee2e2', color: '#991b1b', border: '1px solid #fecaca' };
      break;
    case 'PROCESANDO':
      className += ' badge-info';
      label = 'PROCESANDO';
      Icon = Loader2;
      break;
    case 'PENDIENTE':
      className += ' badge-secondary';
      label = 'PENDIENTE';
      Icon = Clock;
      style = { backgroundColor: '#f1f5f9', color: '#475569', border: '1px solid #cbd5e1' };
      break;
    case 'COMPLETADO':
      className += ' badge-success';
      label = 'COMPLETADO';
      Icon = CheckCircle2;
      break;
    case 'COMPLETADO_CON_ERRORES':
      className += ' badge-warning';
      label = 'CON ERRORES';
      Icon = AlertTriangle;
      break;
    case 'CANCELADO':
      className += ' badge-secondary';
      label = 'CANCELADO';
      Icon = XCircle;
      break;
    default:
      className += ' badge-secondary';
      label = normalized || 'DESCONOCIDO';
      Icon = AlertTriangle;
  }

  const iconSize = size === 'sm' ? 13 : size === 'lg' ? 18 : 15;
  const paddingStyle = size === 'sm' ? { padding: '0.2rem 0.5rem', fontSize: '0.72rem' } : size === 'lg' ? { padding: '0.45rem 1rem', fontSize: '0.9rem' } : { padding: '0.3rem 0.75rem', fontSize: '0.8rem' };

  return (
    <span
      className={className}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '0.35rem',
        fontWeight: '600',
        borderRadius: '6px',
        letterSpacing: '0.02em',
        ...paddingStyle,
        ...style,
      }}
    >
      {showIcon && Icon && <Icon size={iconSize} className={normalized === 'PROCESANDO' ? 'spin' : ''} />}
      <span>{label}</span>
    </span>
  );
};
