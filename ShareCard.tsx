import { useCallback, useMemo, useState } from 'react';
import { Check, Copy, Linkedin, Send } from 'lucide-react';

export interface Props {
  /** e.g. "Мой план развития" */
  title: string;
  /** e.g. "Следующий грейд" */
  scenario: string;
  /** e.g. 82 */
  matchPercent: number;
  /** Up to 5 skill names */
  topSkills: string[];
  /** For share URL */
  analysisId?: string;
}

function buildShareUrl(analysisId: string | undefined): string {
  if (!analysisId || typeof window === 'undefined') {
    return '';
  }
  return `${window.location.origin}${window.location.pathname}#share/${analysisId}`;
}

function matchBadgeClasses(percent: number): string {
  if (percent > 70) {
    return 'border-emerald-500/30 bg-emerald-500/15 text-emerald-800';
  }
  if (percent > 40) {
    return 'border-amber-500/30 bg-amber-500/15 text-amber-900';
  }
  return 'border-red-500/30 bg-red-500/15 text-red-800';
}

export default function ShareCard({
  title,
  scenario,
  matchPercent,
  topSkills,
  analysisId,
}: Props) {
  const [copied, setCopied] = useState(false);

  const shareUrl = useMemo(() => buildShareUrl(analysisId), [analysisId]);

  const shareText = useMemo(() => {
    const skills = topSkills.slice(0, 5).join(', ');
    return `${title} — ${scenario}${skills ? `. Навыки: ${skills}` : ''}`;
  }, [title, scenario, topSkills]);

  const telegramHref = useMemo(() => {
    const params = new URLSearchParams({
      url: shareUrl,
      text: shareText,
    });
    return `https://t.me/share/url?${params.toString()}`;
  }, [shareUrl, shareText]);

  const linkedInHref = useMemo(() => {
    const params = new URLSearchParams({ url: shareUrl });
    return `https://www.linkedin.com/sharing/share-offsite/?${params.toString()}`;
  }, [shareUrl]);

  const handleCopy = useCallback(async () => {
    if (!shareUrl) return;
    try {
      await navigator.clipboard.writeText(shareUrl);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  }, [shareUrl]);

  const openInNewTab = useCallback((href: string) => {
    window.open(href, '_blank', 'noopener,noreferrer');
  }, []);

  const skills = topSkills.slice(0, 5);
  const canShare = Boolean(shareUrl);

  return (
    <div className="bg-[var(--paper)] border border-[var(--line)] rounded-2xl shadow-[var(--shadow-soft)] p-6">
      <header className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="text-[var(--ink)] font-bold text-xl leading-tight">{title}</h2>
          <p className="mt-1 text-sm font-medium text-[var(--blue-deep)]">Career Copilot</p>
        </div>
        <div
          className={`inline-flex shrink-0 items-center rounded-full border px-4 py-1.5 text-sm font-semibold tabular-nums ${matchBadgeClasses(matchPercent)}`}
        >
          {Math.round(matchPercent)}% совпадение
        </div>
      </header>

      <p className="mb-4 text-sm text-[var(--muted)]">
        <span className="font-medium text-[var(--ink)]">{scenario}</span>
      </p>

      {skills.length > 0 && (
        <div className="mb-6 flex flex-wrap gap-2">
          {skills.map((skill) => (
            <span
              key={skill}
              className="bg-[var(--chip)] text-[var(--blue-deep)] rounded-full px-3 py-1 text-sm"
            >
              {skill}
            </span>
          ))}
        </div>
      )}

      <div className="mb-6 flex flex-col gap-2 sm:flex-row">
        <button
          type="button"
          onClick={handleCopy}
          disabled={!canShare}
          className="flex flex-1 items-center justify-center gap-2 rounded-xl border border-[var(--line)] bg-[var(--paper)] px-4 py-3 text-sm font-medium text-[var(--ink)] transition hover:border-[var(--blue-deep)]/40 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {copied ? (
            <Check className="h-4 w-4 shrink-0 text-emerald-600" aria-hidden />
          ) : (
            <Copy className="h-4 w-4 shrink-0 text-[var(--blue-deep)]" aria-hidden />
          )}
          {copied ? 'Скопировано!' : 'Скопировать ссылку'}
        </button>

        <button
          type="button"
          onClick={() => openInNewTab(telegramHref)}
          disabled={!canShare}
          className="flex flex-1 items-center justify-center gap-2 rounded-xl border border-[var(--line)] bg-[var(--paper)] px-4 py-3 text-sm font-medium text-[var(--ink)] transition hover:border-[var(--blue-deep)]/40 disabled:cursor-not-allowed disabled:opacity-50"
        >
          <Send className="h-4 w-4 shrink-0 text-[var(--blue-deep)]" aria-hidden />
          Telegram
        </button>

        <button
          type="button"
          onClick={() => openInNewTab(linkedInHref)}
          disabled={!canShare}
          className="flex flex-1 items-center justify-center gap-2 rounded-xl border border-[var(--line)] bg-[var(--paper)] px-4 py-3 text-sm font-medium text-[var(--ink)] transition hover:border-[var(--blue-deep)]/40 disabled:cursor-not-allowed disabled:opacity-50"
        >
          <Linkedin className="h-4 w-4 shrink-0 text-[var(--blue-deep)]" aria-hidden />
          LinkedIn
        </button>
      </div>

      <p className="text-center text-sm text-[var(--muted)]">
        Присоединяйтесь к Career Copilot!
      </p>
    </div>
  );
}
