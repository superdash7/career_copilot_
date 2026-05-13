import { useState, useEffect } from 'react';
import { Lightbulb } from 'lucide-react';

const TIPS = [
  '70% профессионального роста происходит через реальные задачи, а не через курсы',
  'Самый частый блокер карьеры — не навыки, а отсутствие плана',
  'Средний Senior тратит 5 часов в неделю на целенаправленное развитие',
  'Люди с письменным планом развития достигают целей в 2 раза чаще',
  'Навыки коммуникации влияют на карьерный рост больше, чем технические навыки',
  'Лучший способ закрепить навык — сразу применить его в рабочей задаче',
  'Регулярная обратная связь ускоряет рост в 3 раза по сравнению с самообучением',
  'Переход на следующий грейд в среднем занимает 12–18 месяцев с четким планом',
  '80% успешных карьерных переходов начинаются с анализа текущих навыков',
  'Менторство — самый недооцененный инструмент карьерного роста',
];

interface Props {
  text?: string;
  subtext?: string;
  /** When false, only text / progress / tips — no spinning ring */
  showSpinner?: boolean;
}

export default function LoadingCarousel({
  text = 'Создаем ваш персональный план...',
  subtext = 'Это может занять до минуты',
  showSpinner = true,
}: Props) {
  const [currentTip, setCurrentTip] = useState(0);
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => {
      setCurrentTip((prev) => (prev + 1) % TIPS.length);
    }, 4000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    const interval = setInterval(() => {
      setProgress((prev) => Math.min(prev + 0.5, 95));
    }, 300);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="mx-auto max-w-lg space-y-8 py-12 text-center">
      {/* Spinner + text */}
      <div>
        {showSpinner ? (
          <div className="mx-auto mb-4 h-10 w-10 animate-spin rounded-full border-3 border-[var(--line)] border-t-[var(--blue-deep)]" />
        ) : null}
        <p className={`text-lg font-semibold text-[var(--ink)] ${showSpinner ? '' : 'pt-1'}`}>{text}</p>
        <p className="mt-1 text-sm text-[var(--muted)]">{subtext}</p>
      </div>

      {/* Progress bar */}
      <div className="mx-auto max-w-xs">
        <div className="h-1.5 w-full overflow-hidden rounded-full bg-[var(--line)]">
          <div
            className="h-full rounded-full bg-[var(--blue-deep)] transition-all duration-500 ease-out"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      {/* Tip carousel */}
      <div className="mx-auto max-w-sm rounded-2xl border border-[var(--line)] bg-[var(--paper)] p-5 shadow-[var(--shadow-soft)]">
        <div className="mb-3 flex items-center justify-center gap-2 text-xs font-medium text-[var(--blue-deep)]">
          <Lightbulb className="h-4 w-4" />
          Знаете ли вы
        </div>
        <p
          key={currentTip}
          className="text-sm leading-relaxed text-[var(--muted)] fade-in"
        >
          {TIPS[currentTip]}
        </p>

        {/* Dots */}
        <div className="mt-4 flex items-center justify-center gap-1.5">
          {TIPS.map((_, i) => (
            <div
              key={i}
              className={`h-1.5 rounded-full transition-all duration-300 ${
                i === currentTip
                  ? 'w-4 bg-[var(--blue-deep)]'
                  : 'w-1.5 bg-[var(--line)]'
              }`}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
