import { useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import Button from './ui/Button';

type Props = {
  open: boolean;
  title: string;
  onClose: () => void;
  children: React.ReactNode;
};

/**
 * Простое окно с прокруткой для политики / согласия (нативный dialog).
 */
export default function LegalModal({ open, title, onClose, children }: Props) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    const onNativeClose = () => {
      onClose();
    };
    d.addEventListener('close', onNativeClose);
    return () => d.removeEventListener('close', onNativeClose);
  }, [onClose]);

  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) {
      d.showModal();
    }
    if (!open && d.open) {
      d.close();
    }
  }, [open]);

  const dialog = (
    <dialog
      ref={ref}
      className="legal-dialog fixed left-1/2 top-1/2 z-[200] max-h-[min(90vh,640px)] w-[min(calc(100vw-2rem),520px)] max-w-[520px] -translate-x-1/2 -translate-y-1/2 rounded-2xl border border-[var(--line)] bg-[var(--paper)] p-0 text-[var(--ink)] shadow-[var(--shadow-soft)]"
      onClick={(e) => {
        if (e.target === ref.current) onClose();
      }}
    >
      <div className="flex max-h-[min(90vh,640px)] flex-col">
        <div className="flex shrink-0 items-start justify-between gap-3 border-b border-[var(--line)] px-5 py-4">
          <h2 className="pr-2 text-left text-base font-semibold leading-snug">{title}</h2>
          <Button type="button" size="sm" variant="secondary" onClick={onClose} className="shrink-0">
            Закрыть
          </Button>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4 text-left text-sm leading-relaxed text-[var(--ink)]">
          {children}
        </div>
      </div>
    </dialog>
  );

  return createPortal(dialog, document.body);
}
