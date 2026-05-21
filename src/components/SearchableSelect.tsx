import { useState, useRef, useEffect, useCallback } from 'react';
import { ChevronDown, Search, X } from 'lucide-react';

interface Props {
  options: string[];
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
}

export default function SearchableSelect({ options, value, onChange, placeholder = 'Выберите…' }: Props) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [highlighted, setHighlighted] = useState(-1);
  const wrapRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  const filtered = query
    ? options.filter((o) => o.toLowerCase().includes(query.toLowerCase()))
    : options;

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) {
        setOpen(false);
        setQuery('');
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  useEffect(() => {
    if (open && inputRef.current) inputRef.current.focus();
  }, [open]);

  useEffect(() => {
    if (highlighted >= 0 && listRef.current) {
      const el = listRef.current.children[highlighted] as HTMLElement | undefined;
      el?.scrollIntoView({ block: 'nearest' });
    }
  }, [highlighted]);

  const select = useCallback(
    (val: string) => {
      onChange(val);
      setOpen(false);
      setQuery('');
    },
    [onChange],
  );

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setHighlighted((h) => Math.min(h + 1, filtered.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setHighlighted((h) => Math.max(h - 1, 0));
    } else if (e.key === 'Enter' && highlighted >= 0 && filtered[highlighted]) {
      e.preventDefault();
      select(filtered[highlighted]);
    } else if (e.key === 'Escape') {
      setOpen(false);
      setQuery('');
    }
  };

  return (
    <div className="relative" ref={wrapRef}>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="input-field flex items-center justify-between text-left"
      >
        <span className={value ? 'text-(--color-text-primary)' : 'text-(--color-text-muted)'}>
          {value || placeholder}
        </span>
        <div className="flex items-center gap-1">
          {value && (
            <span
              role="button"
              onClick={(e) => {
                e.stopPropagation();
                onChange('');
              }}
              className="p-0.5 rounded hover:bg-(--color-surface-alt) text-(--color-text-muted) hover:text-(--color-text-secondary) transition-colors"
            >
              <X className="h-3.5 w-3.5" />
            </span>
          )}
          <ChevronDown
            className={`h-4 w-4 text-(--color-text-muted) transition-transform duration-200 ${open ? 'rotate-180' : ''}`}
          />
        </div>
      </button>

      {open && (
        <div className="absolute z-30 mt-1 w-full rounded-xl border border-(--color-border) bg-(--color-surface-raised) shadow-lg overflow-hidden fade-in">
          <div className="flex items-center gap-2 border-b border-(--color-border) px-3 py-2">
            <Search className="h-4 w-4 text-(--color-text-muted) shrink-0" />
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={(e) => { setQuery(e.target.value); setHighlighted(-1); }}
              onKeyDown={handleKeyDown}
              placeholder="Поиск…"
              className="flex-1 bg-transparent text-sm text-(--color-text-primary) placeholder-(--color-text-muted) outline-none"
            />
          </div>
          <div ref={listRef} className="max-h-60 overflow-y-auto">
            {filtered.length === 0 ? (
              <p className="px-4 py-3 text-sm text-(--color-text-muted)">Ничего не найдено</p>
            ) : (
              filtered.map((opt, i) => (
                <button
                  key={opt}
                  onClick={() => select(opt)}
                  className={`w-full text-left px-4 py-2.5 text-sm transition-colors ${
                    opt === value
                      ? 'bg-(--color-accent-light) text-(--color-accent) font-medium'
                      : i === highlighted
                        ? 'bg-(--color-accent-light)/50 text-(--color-text-primary)'
                        : 'text-(--color-text-secondary) hover:bg-(--color-accent-light)/30'
                  }`}
                >
                  {opt}
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
