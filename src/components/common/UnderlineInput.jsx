import React from 'react';

export default function UnderlineInput({
  label,
  type = 'text',
  placeholder,
  value,
  onChange,
  onSubmit,
  required = false,
  showArrow = false,
  name,
  disabled = false,
  className = '',
  id,
  error,
}) {
  const inputId = id || name || (label ? label.toLowerCase().replace(/\s+/g, '-') : undefined);

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && onSubmit) {
      e.preventDefault();
      onSubmit();
    }
  };

  return (
    <div className={`w-full flex flex-col ${className}`}>
      {label && (
        <label
          htmlFor={inputId}
          className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-[#0F172A] select-none flex items-center justify-between"
        >
          <span>{label}</span>
          {required && <span className="text-[#DC2626] font-normal text-xs">*Required</span>}
        </label>
      )}
      <div className="relative flex items-center">
        <input
          id={inputId}
          name={name}
          type={type}
          value={value}
          onChange={onChange}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          required={required}
          disabled={disabled}
          className={`w-full bg-white border ${
            error ? 'border-[#DC2626]' : 'border-[#E2E8F0]'
          } rounded-lg py-2.5 px-3.5 pr-10 text-sm text-[#0F172A] placeholder:text-[#94A3B8] focus:outline-none focus:ring-2 focus:ring-[#2563EB]/20 focus:border-[#2563EB] transition-all disabled:bg-[#F8FAFC] disabled:opacity-50`}
        />
        {showArrow && (
          <button
            type={onSubmit ? 'button' : 'submit'}
            onClick={onSubmit}
            className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-[#2563EB] font-sans text-sm px-2 py-1 rounded transition-colors"
            title="Submit"
          >
            →
          </button>
        )}
      </div>
      {error && <p className="text-xs text-[#DC2626] mt-1">{error}</p>}
    </div>
  );
}
