import React from 'react';

export default function UnderlineTextarea({
  label,
  value,
  onChange,
  placeholder,
  rows = 4,
  required = false,
  disabled = false,
  className = '',
  id,
  name,
  error,
}) {
  const textareaId = id || name || (label ? label.toLowerCase().replace(/\s+/g, '-') : undefined);

  return (
    <div className={`w-full flex flex-col ${className}`}>
      {label && (
        <label
          htmlFor={textareaId}
          className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-[#0F172A] select-none flex items-center justify-between"
        >
          <span>{label}</span>
          {required && <span className="text-[#DC2626] font-normal text-xs">*Required</span>}
        </label>
      )}
      <textarea
        id={textareaId}
        name={name}
        rows={rows}
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        required={required}
        disabled={disabled}
        className={`w-full bg-white border ${
          error ? 'border-[#DC2626]' : 'border-[#E2E8F0]'
        } rounded-lg py-2.5 px-3.5 text-sm text-[#0F172A] placeholder:text-[#94A3B8] focus:outline-none focus:ring-2 focus:ring-[#2563EB]/20 focus:border-[#2563EB] transition-all disabled:bg-[#F8FAFC] disabled:opacity-50`}
      />
      {error && <p className="text-xs text-[#DC2626] mt-1">{error}</p>}
    </div>
  );
}
