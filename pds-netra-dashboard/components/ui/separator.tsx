import * as React from 'react';

export function Separator({ className = '', ...props }: React.HTMLAttributes<HTMLHRElement>) {
  return <hr className={`border-slate-200 ${className}`} {...props} />;
}
