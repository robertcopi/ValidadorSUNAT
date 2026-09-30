import React, { useState } from 'react';
import { Eye, EyeOff } from 'lucide-react';

export const PasswordInput = ({
  id,
  name,
  value,
  onChange,
  placeholder = '••••••••',
  required = false,
  minLength,
  maxLength,
  autoComplete = 'current-password',
  disabled = false,
  className = '',
  style = {},
  ...rest
}) => {
  const [showPassword, setShowPassword] = useState(false);

  return (
    <div className="password-input-wrapper" style={{ position: 'relative', width: '100%' }}>
      <input
        id={id}
        name={name}
        type={showPassword ? 'text' : 'password'}
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        required={required}
        minLength={minLength}
        maxLength={maxLength}
        autoComplete={autoComplete}
        disabled={disabled}
        className={`form-input ${className}`}
        style={{
          paddingRight: '2.5rem',
          ...style,
        }}
        {...rest}
      />
      <button
        type="button"
        className="password-toggle-btn"
        onClick={() => setShowPassword((prev) => !prev)}
        disabled={disabled}
        title={showPassword ? 'Ocultar contraseña' : 'Ver contraseña'}
        aria-label={showPassword ? 'Ocultar contraseña' : 'Ver contraseña'}
        tabIndex={-1}
      >
        {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
      </button>
    </div>
  );
};

export default PasswordInput;
