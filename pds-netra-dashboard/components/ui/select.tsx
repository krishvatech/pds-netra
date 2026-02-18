import * as React from 'react';
import * as SelectPrimitive from '@radix-ui/react-select';
import { Check, ChevronDown } from 'lucide-react';

export type SelectOption = { label: string; value: string };

type TriggerProps = React.ComponentPropsWithoutRef<typeof SelectPrimitive.Trigger>;
type Props = Omit<TriggerProps, 'onChange' | 'value' | 'defaultValue'> & {
  options: SelectOption[];
  placeholder?: string;
  value?: string | number | readonly string[] | undefined;
  defaultValue?: string | number | readonly string[] | undefined;
  onChange?: (event: React.ChangeEvent<HTMLSelectElement>) => void;
  name?: string;
  disabled?: boolean;
  required?: boolean;
};

function normalizeValue(value?: string | number | readonly string[]) {
  if (value === undefined || value === null) return undefined;
  if (Array.isArray(value)) return value[0] ? String(value[0]) : '';
  return String(value);
}

const EMPTY_VALUE = '__pds_empty__';

export function Select({
  options,
  placeholder,
  className = '',
  value,
  defaultValue,
  onChange,
  name,
  disabled,
  required,
  ...props
}: Props) {
  const handleValueChange = (next: string) => {
    if (!onChange) return;
    const eventValue = next === EMPTY_VALUE ? '' : next;
    const event = {
      target: { value: eventValue, name }
    } as React.ChangeEvent<HTMLSelectElement>;
    onChange(event);
  };
  const normalizedValue = normalizeValue(value);
  const normalizedDefault = normalizeValue(defaultValue);
  const resolvedValue = normalizedValue === '' ? EMPTY_VALUE : normalizedValue;
  const resolvedDefault = normalizedDefault === '' ? EMPTY_VALUE : normalizedDefault;

  return (
    <SelectPrimitive.Root
      value={resolvedValue}
      defaultValue={resolvedDefault}
      onValueChange={handleValueChange}
      name={name}
      disabled={disabled}
      required={required}
    >
      <SelectPrimitive.Trigger
        className={`min-w-0 w-full h-11 md:h-10 rounded-xl px-3 text-base md:text-sm text-left flex items-center justify-between gap-2 input-field ${className}`}
        {...props}
      >
        <SelectPrimitive.Value placeholder={placeholder} />
        <SelectPrimitive.Icon className="text-slate-400">
          <ChevronDown className="h-4 w-4" />
        </SelectPrimitive.Icon>
      </SelectPrimitive.Trigger>
      <SelectPrimitive.Portal>
        <SelectPrimitive.Content
          position="popper"
          sideOffset={6}
          collisionPadding={16}
          className="z-[9999] w-[var(--radix-select-trigger-width)] min-w-[var(--radix-select-trigger-width)] max-w-[calc(100vw-2rem)] max-h-[min(60vh,320px)] overflow-y-auto rounded-xl border border-white/10 bg-slate-950/95 text-slate-100 shadow-2xl"
        >
          <SelectPrimitive.Viewport className="p-1">
            {options.map((option) => (
              <SelectItem
                key={option.value || EMPTY_VALUE}
                value={option.value === '' ? EMPTY_VALUE : option.value}
              >
                {option.label}
              </SelectItem>
            ))}
          </SelectPrimitive.Viewport>
        </SelectPrimitive.Content>
      </SelectPrimitive.Portal>
    </SelectPrimitive.Root>
  );
}

function SelectItem({
  children,
  className = '',
  ...props
}: React.ComponentPropsWithoutRef<typeof SelectPrimitive.Item>) {
  return (
    <SelectPrimitive.Item
      className={`relative flex w-full cursor-pointer select-none items-center rounded-lg h-11 px-3 text-base md:text-sm outline-none focus:bg-white/10 data-[state=checked]:bg-white/10 data-[disabled]:pointer-events-none data-[disabled]:opacity-50 ${className}`}
      {...props}
    >
      <SelectPrimitive.ItemText>{children}</SelectPrimitive.ItemText>
      <SelectPrimitive.ItemIndicator className="absolute right-3 inline-flex items-center justify-center">
        <Check className="h-4 w-4 text-emerald-300" />
      </SelectPrimitive.ItemIndicator>
    </SelectPrimitive.Item>
  );
}
