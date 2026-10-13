import React from 'react';

export default function Card({
  children,
  className = '',
  title,
  subtitle,
  action,
  footer,
  padding = 'normal', // none | sm | normal | lg
  hover = false,
  onClick,
  ...props
}) {
  const paddingMap = {
    none: 'p-0',
    sm: 'p-4',
    normal: 'p-6',
    lg: 'p-8',
  };

  return (
    <div
      onClick={onClick}
      className={`bg-white border border-[#E2E8F0] rounded-xl shadow-sm transition-all duration-150 ${
        hover ? 'hover:border-[#CBD5E1] hover:shadow-md cursor-pointer' : ''
      } ${className}`}
      {...props}
    >
      {(title || subtitle || action) && (
        <div className="flex items-center justify-between border-b border-[#E2E8F0] px-6 py-4">
          <div>
            {title && (
              <h3 className="text-base font-semibold text-[#0F172A]">{title}</h3>
            )}
            {subtitle && (
              <p className="text-xs text-[#64748B] mt-0.5">{subtitle}</p>
            )}
          </div>
          {action && <div className="flex items-center gap-2">{action}</div>}
        </div>
      )}

      <div className={paddingMap[padding] || paddingMap.normal}>{children}</div>

      {footer && (
        <div className="border-t border-[#E2E8F0] bg-[#F8FAFC] px-6 py-3.5 rounded-b-xl">
          {footer}
        </div>
      )}
    </div>
  );
}
