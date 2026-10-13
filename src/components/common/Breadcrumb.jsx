import React from 'react';
import { Link } from 'react-router-dom';
import { ChevronRight } from 'lucide-react';

export default function Breadcrumb({ items = [], className = '' }) {
  return (
    <nav aria-label="Breadcrumb" className={`flex items-center gap-1.5 text-xs text-[#64748B] ${className}`}>
      {items.map((item, idx) => {
        const isLast = idx === items.length - 1;
        return (
          <React.Fragment key={idx}>
            {idx > 0 && <ChevronRight className="w-3.5 h-3.5 text-slate-400" />}
            {item.to && !isLast ? (
              <Link
                to={item.to}
                className="hover:text-[#2563EB] transition-colors font-medium"
              >
                {item.label}
              </Link>
            ) : (
              <span className={isLast ? 'text-[#0F172A] font-medium' : ''}>
                {item.label}
              </span>
            )}
          </React.Fragment>
        );
      })}
    </nav>
  );
}
