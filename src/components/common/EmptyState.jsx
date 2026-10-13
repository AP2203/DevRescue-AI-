import React from 'react';
import Button from './Button';

export default function EmptyState({
  icon: Icon,
  title,
  description,
  actionLabel,
  onAction,
  actionTo,
  className = '',
}) {
  return (
    <div
      className={`flex flex-col items-center justify-center text-center p-12 bg-white border border-[#E2E8F0] rounded-xl ${className}`}
    >
      {Icon && (
        <div className="w-12 h-12 rounded-xl bg-[#EFF6FF] border border-[#BFDBFE] flex items-center justify-center text-[#2563EB] mb-4">
          <Icon className="w-6 h-6" />
        </div>
      )}
      <h3 className="text-base font-semibold text-[#0F172A]">{title}</h3>
      {description && (
        <p className="text-sm text-[#64748B] max-w-sm mt-1.5 leading-relaxed">
          {description}
        </p>
      )}
      {(actionLabel && (onAction || actionTo)) && (
        <div className="mt-6">
          <Button
            variant="primary"
            size="sm"
            onClick={onAction}
            to={actionTo}
          >
            {actionLabel}
          </Button>
        </div>
      )}
    </div>
  );
}
