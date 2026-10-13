import React from 'react';

export default function Avatar({
  name = 'Ansh',
  src,
  size = 'md', // sm | md | lg
  className = '',
}) {
  const sizeStyles = {
    sm: 'w-7 h-7 text-xs',
    md: 'w-8 h-8 text-xs',
    lg: 'w-10 h-10 text-sm font-medium',
  };

  const initials = (name || 'A')
    .split(' ')
    .map((n) => n[0])
    .join('')
    .slice(0, 2)
    .toUpperCase();

  if (src) {
    return (
      <img
        src={src}
        alt={name}
        className={`rounded-full object-cover border border-[#E2E8F0] ${
          sizeStyles[size] || sizeStyles.md
        } ${className}`}
      />
    );
  }

  return (
    <div
      className={`rounded-full bg-[#EFF6FF] border border-[#BFDBFE] text-[#2563EB] font-semibold flex items-center justify-center select-none ${
        sizeStyles[size] || sizeStyles.md
      } ${className}`}
    >
      {initials}
    </div>
  );
}
