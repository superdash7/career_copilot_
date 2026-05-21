/**
 * Favicon pulse while profile analysis runs + desktop notification when done in background.
 * Uses the Notification API (user must grant permission; typically prompted on first "Построить план").
 */

const FAVICON_DEFAULT =
  "data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>🧭</text></svg>";
const FAVICON_ALT =
  "data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>✨</text></svg>";

let pulseTimer: ReturnType<typeof setInterval> | null = null;
let faviconLink: HTMLLinkElement | null = null;
let pulseToggle = false;

function getFaviconLink(): HTMLLinkElement | null {
  if (typeof document === 'undefined') return null;
  let link = document.querySelector<HTMLLinkElement>("link[rel='icon']");
  if (!link) {
    link = document.createElement('link');
    link.rel = 'icon';
    document.head.appendChild(link);
  }
  return link;
}

export function startProfileAnalysisFaviconPulse(): void {
  stopProfileAnalysisFaviconPulse();
  faviconLink = getFaviconLink();
  if (!faviconLink) return;
  pulseToggle = false;
  pulseTimer = setInterval(() => {
    pulseToggle = !pulseToggle;
    faviconLink!.href = pulseToggle ? FAVICON_ALT : FAVICON_DEFAULT;
  }, 600);
}

export function stopProfileAnalysisFaviconPulse(): void {
  if (pulseTimer !== null) {
    clearInterval(pulseTimer);
    pulseTimer = null;
  }
  const link = getFaviconLink();
  if (link) link.href = FAVICON_DEFAULT;
}

export async function requestAnalysisNotificationPermission(): Promise<NotificationPermission> {
  if (typeof Notification === 'undefined') return 'denied';
  if (Notification.permission === 'granted' || Notification.permission === 'denied') {
    return Notification.permission;
  }
  try {
    return await Notification.requestPermission();
  } catch {
    return Notification.permission;
  }
}

/**
 * Call with `userWasAway` = document had hidden state **before** navigation
 * (e.g. before onResult), otherwise switching screen can flip visibility to visible
 * synchronously and block the notification.
 */
export function notifyProfileAnalysisReadyIfHadBackground(userWasAway: boolean): void {
  if (!userWasAway) return;
  if (typeof Notification === 'undefined') return;
  if (Notification.permission !== 'granted') return;
  const show = () => {
    try {
      new Notification('Career Copilot — анализ готов', {
        body: 'Профиль обработан, можно смотреть результат.',
        icon: FAVICON_DEFAULT,
        tag: `career-copilot-analysis-ready-${Date.now()}`,
      });
    } catch {
      /* ignore */
    }
  };
  // After parent re-render, some browsers still report visible — run after paint
  if (typeof queueMicrotask === 'function') {
    queueMicrotask(show);
  } else {
    setTimeout(show, 0);
  }
}
