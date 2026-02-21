import * as React from 'react';

export function Table({ className = '', ...props }: React.TableHTMLAttributes<HTMLTableElement>) {
  return (
    <table
      className={`w-full min-w-[720px] md:min-w-0 text-sm border-separate border-spacing-0 ${className}`}
      {...props}
    />
  );
}

export function THead({ className = '', ...props }: React.HTMLAttributes<HTMLTableSectionElement>) {
  return <thead className={`sticky top-0 z-10 bg-slate-900/90 backdrop-blur border-b border-white/10 text-slate-400 ${className}`} {...props} />;
}

export function TH({ className = '', ...props }: React.ThHTMLAttributes<HTMLTableCellElement>) {
  return <th className={`px-2.5 py-2 text-left text-[10px] font-semibold uppercase tracking-[0.14em] sm:px-3 sm:text-[11px] sm:tracking-[0.2em] ${className}`} {...props} />;
}

export function TBody({ className = '', ...props }: React.HTMLAttributes<HTMLTableSectionElement>) {
  return <tbody className={className} {...props} />;
}

export function TR({ className = '', ...props }: React.HTMLAttributes<HTMLTableRowElement>) {
  return <tr className={`border-t border-white/5 transition hover:bg-white/5 text-slate-200 ${className}`} {...props} />;
}

export function TD({ className = '', ...props }: React.TdHTMLAttributes<HTMLTableCellElement>) {
  return <td className={`px-2.5 py-2 align-top text-xs sm:px-3 sm:text-sm ${className}`} {...props} />;
}
