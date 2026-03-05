'use client';

import { Eye, EyeOff } from 'lucide-react';
import { useState } from 'react';
import type { InputHTMLAttributes } from 'react';

type PasswordInputProps = Omit<InputHTMLAttributes<HTMLInputElement>, 'type'>;

export function PasswordInput({ className, ...props }: PasswordInputProps) {
  const [visible, setVisible] = useState(false);
  const inputType = visible ? 'text' : 'password';

  return (
    <div className="relative">
      <input
        {...props}
        type={inputType}
        className={['w-full pr-11', className].filter(Boolean).join(' ')}
      />
      <button
        type="button"
        onClick={() => setVisible((prev) => !prev)}
        className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-200"
        aria-label={visible ? 'Hide password' : 'Show password'}
      >
        {visible ? <EyeOff size={18} /> : <Eye size={18} />}
      </button>
    </div>
  );
}
