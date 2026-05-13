import { ArrowRight, Map, Brain, TrendingUp, Sparkles } from 'lucide-react';
import NavBar from '../components/NavBar';
import Button from '../components/ui/Button';
import Eyebrow from '../components/ui/Eyebrow';
import GridBg from '../components/layout/GridBg';
import Mark from '../components/ui/Mark';

interface Props {
  onTryInstant: (scenario?: string) => void;
  onWatchDemo: () => void;
  onLogin: () => void;
  onRegister: () => void;
  onTeams?: () => void;
}

type Scenario = 'Следующий грейд' | 'Смена профессии' | 'Исследование возможностей';

const EXAMPLES: Array<{ label: string; scenario: Scenario; color: string }> = [
  { label: 'Вырасти до Senior', scenario: 'Следующий грейд', color: 'bg-[var(--blue-deep)]/10 text-[var(--blue-deep)] border-[var(--blue-deep)]/20' },
  { label: 'Перейти в UX-дизайн', scenario: 'Смена профессии', color: 'bg-[#7c3aed]/10 text-[#7c3aed] border-[#7c3aed]/20' },
  { label: 'Уйти в менеджмент', scenario: 'Смена профессии', color: 'bg-[var(--accent-green)]/10 text-[var(--accent-green)] border-[var(--accent-green)]/20' },
  { label: 'Стать тимлидом', scenario: 'Следующий грейд', color: 'bg-[#0ea5e9]/10 text-[#0ea5e9] border-[#0ea5e9]/20' },
  { label: 'Освоить продукт', scenario: 'Смена профессии', color: 'bg-[#f59e0b]/10 text-[#f59e0b] border-[#f59e0b]/20' },
  { label: 'Перейти в аналитику', scenario: 'Смена профессии', color: 'bg-[#ec4899]/10 text-[#ec4899] border-[#ec4899]/20' },
  { label: 'Вырасти до архитектора', scenario: 'Следующий грейд', color: 'bg-[var(--blue-deep)]/10 text-[var(--blue-deep)] border-[var(--blue-deep)]/20' },
  { label: 'Стать фрилансером', scenario: 'Исследование возможностей', color: 'bg-[#7c3aed]/10 text-[#7c3aed] border-[#7c3aed]/20' },
  { label: 'Уйти в DevOps', scenario: 'Смена профессии', color: 'bg-[var(--accent-green)]/10 text-[var(--accent-green)] border-[var(--accent-green)]/20' },
  { label: 'Сменить индустрию', scenario: 'Исследование возможностей', color: 'bg-[#0ea5e9]/10 text-[#0ea5e9] border-[#0ea5e9]/20' },
];

const FEATURES = [
  {
    icon: Map,
    title: 'Индивидуальный роадмап',
    desc: 'Разбиваем большую цель на понятные шаги по неделям. План подстраивается под ваш темп и свободное время.',
  },
  {
    icon: Brain,
    title: 'Оценка навыков',
    desc: 'AI сравнит ваш текущий опыт с требованиями к новой роли и покажет, какие именно компетенции нужно подтянуть.',
  },
  {
    icon: TrendingUp,
    title: 'Трекинг прогресса',
    desc: 'Отмечайте выполненные задачи, получайте советы от AI и экспертов и наглядно видите, как приближаетесь к цели.',
  },
];

export default function PublicLanding({ onTryInstant, onLogin, onRegister, onTeams }: Props) {
  return (
    <GridBg className="min-h-screen bg-[var(--bg)]">
      <header className="mx-auto w-full max-w-6xl px-5 md:px-8">
        <NavBar onLogin={onLogin} onRegister={onRegister} onTeams={onTeams} />
      </header>

      <main className="mx-auto w-full max-w-6xl px-5 pb-20 md:px-8">
        {/* Hero */}
        <section className="pb-14 pt-8 md:pb-20 md:pt-16">
          <div className="mx-auto max-w-3xl text-center">
            <Eyebrow className="mb-4 inline-flex items-center gap-2 rounded-full bg-[var(--chip)] px-4 py-1.5">
              <Sparkles className="h-3.5 w-3.5" />
              AI-проводник карьерного роста
            </Eyebrow>

            <h1 className="text-4xl leading-[1.1] tracking-tight text-[var(--ink)] md:text-6xl">
              Ваш точный маршрут к{' '}
              <Mark>карьере мечты</Mark>
            </h1>

            <p className="mx-auto mt-6 max-w-2xl text-lg leading-relaxed text-[var(--muted)]">
              Career Copilot проанализирует ваше резюме и требования рынка, чтобы построить
              понятный пошаговый план развития. Без воды, с задачами на каждую неделю.
            </p>

            {/* Chips */}
            <div className="mx-auto mt-8 flex max-w-2xl flex-wrap items-center justify-center gap-2">
              {EXAMPLES.map((ex) => (
                <button
                  key={ex.label}
                  onClick={() => onTryInstant(ex.scenario)}
                  className={`rounded-full border px-4 py-2 text-sm font-medium transition-all hover:scale-105 ${ex.color}`}
                >
                  {ex.label}
                </button>
              ))}
            </div>

            {/* CTA */}
            <div className="mt-8">
              <Button size="lg" onClick={() => onTryInstant()}>
                Построить план
                <ArrowRight className="h-5 w-5" />
              </Button>
            </div>

          </div>
        </section>

        {/* Feature cards */}
        <section className="mb-16 md:mb-24">
          <div className="grid gap-6 md:grid-cols-3">
            {FEATURES.map((f, i) => (
              <div
                key={i}
                className="group rounded-2xl border border-[var(--line)] bg-[var(--paper)] p-6 shadow-[var(--shadow-soft)] transition-all duration-300 hover:border-[var(--blue-deep)]/30 hover:shadow-[0_8px_32px_rgba(79,70,229,0.1)]"
              >
                <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-xl bg-[var(--chip)] transition-colors group-hover:bg-[var(--blue-deep)] group-hover:text-white">
                  <f.icon className="h-5 w-5 text-[var(--blue-deep)] group-hover:text-white" />
                </div>
                <h3 className="mb-2 text-lg font-semibold text-[var(--ink)]">{f.title}</h3>
                <p className="text-sm leading-relaxed text-[var(--muted)]">{f.desc}</p>
              </div>
            ))}
          </div>
        </section>
      </main>

      <footer className="border-t border-[var(--line)] py-6 text-center text-xs text-[var(--muted)]">
        Career Copilot
      </footer>
    </GridBg>
  );
}
