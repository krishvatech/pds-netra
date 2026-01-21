import * as React from 'react';

export type SelectOption = { label: string; value: string };

type Props = React.SelectHTMLAttributes<HTMLSelectElement> & {
  options: SelectOption[];
  placeholder?: string;
};

export function Select({ options, placeholder, className = '', ...props }: Props) {
  return (
    <select
      className={`h-11 w-full rounded-xl border border-white/60 bg-white/80 px-3 py-2 text-sm outline-none transition focus:border-amber-400 focus:ring-2 focus:ring-amber-200 ${className}`}
      {...props}
    >
      {placeholder ? <option value="">{placeholder}</option> : null}
      {options.map((o) => (
        <option key={o.value} value={o.value}>
          {o.label}
        </option>
      ))}
    </select>
  );
}
