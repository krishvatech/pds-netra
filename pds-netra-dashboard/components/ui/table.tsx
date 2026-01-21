import * as React from 'react';

export function Table({ className = '', ...props }: React.TableHTMLAttributes<HTMLTableElement>) {
  return <table className={`w-full text-sm border-separate border-spacing-0 ${className}`} {...props} />;
}

export function THead({ className = '', ...props }: React.HTMLAttributes<HTMLTableSectionElement>) {
  return <thead className={`sticky top-0 z-10 bg-white/80 backdrop-blur text-slate-600 ${className}`} {...props} />;
}

export function TH({ className = '', ...props }: React.ThHTMLAttributes<HTMLTableCellElement>) {
  return <th className={`px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-[0.2em] ${className}`} {...props} />;
}

export function TBody({ className = '', ...props }: React.HTMLAttributes<HTMLTableSectionElement>) {
  return <tbody className={className} {...props} />;
}

export function TR({ className = '', ...props }: React.HTMLAttributes<HTMLTableRowElement>) {
  return <tr className={`border-t border-white/60 transition hover:bg-white/60 ${className}`} {...props} />;
}

export function TD({ className = '', ...props }: React.TdHTMLAttributes<HTMLTableCellElement>) {
  return <td className={`px-3 py-2 align-top ${className}`} {...props} />;
}
