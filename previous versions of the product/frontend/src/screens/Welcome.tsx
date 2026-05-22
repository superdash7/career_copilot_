import { ArrowRight, Compass } from 'lucide-react';
import NavBar from '../components/NavBar';

interface Props {
  onStart: () => void;
}

export default function Welcome({ onStart }: Props) {
  return (
    <div className="min-h-screen flex flex-col bg-(--color-surface)">
      <header className="mx-auto w-full max-w-3xl px-4">
        <NavBar />
      </header>

      <div className="flex-1 flex items-center justify-center px-4 py-12">
        <div className="max-w-2xl w-full text-center slide-up">
          <div className="mb-6 inline-flex items-center justify-center h-16 w-16 rounded-2xl bg-(--color-accent-light)">
            <Compass className="h-8 w-8 text-(--color-accent)" />
          </div>

          <h1 className="text-4xl sm:text-5xl font-extrabold text-(--color-text-primary) tracking-tight mb-4">
            Career Copilot
          </h1>
          <p className="text-lg text-(--color-text-secondary) leading-relaxed mb-2">
            Ваш навигатор в профессиональном росте
          </p>
          <p className="text-base text-(--color-text-muted) leading-relaxed mb-10 max-w-lg mx-auto">
            Давайте вместе построим маршрут к вашему следующему карьерному шагу.
          </p>

          <button onClick={onStart} className="btn-primary text-lg px-8 py-4 mb-8">
            Начать путь <ArrowRight className="h-5 w-5" />
          </button>

          <div className="flex items-center justify-center gap-6 sm:gap-8 text-sm text-(--color-text-muted)">
            {[
              { n: '1', t: 'Определим цель' },
              { n: '2', t: 'Опишем навыки' },
              { n: '3', t: 'Сформируем план' },
            ].map((s, i) => (
              <div key={i} className="flex items-center gap-2">
                <span className="flex h-6 w-6 items-center justify-center rounded-full bg-(--color-accent-light) text-xs font-semibold text-(--color-accent)">
                  {s.n}
                </span>
                <span>{s.t}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <footer className="border-t border-(--color-border-muted) py-4 text-center text-xs text-(--color-text-muted)">
        Career Copilot
      </footer>
    </div>
  );
}
