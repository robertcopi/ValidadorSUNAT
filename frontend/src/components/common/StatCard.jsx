import React from 'react';

export const StatCard = ({ title, value, icon: Icon, color = '#3b82f6', subtitle }) => {
  return (
    <div className="stat-card">
      <div className="stat-header">
        <span className="stat-title">{title}</span>
        <div className="stat-icon-wrapper" style={{ backgroundColor: `${color}15`, color }}>
          {Icon && <Icon size={20} />}
        </div>
      </div>
      <div className="stat-value">{value}</div>
      {subtitle && <div className="stat-subtitle">{subtitle}</div>}
    </div>
  );
};
