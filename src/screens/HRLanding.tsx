import { useState } from 'react';
import { ArrowLeft, BarChart3, Route, LineChart, Send, CheckCircle2 } from 'lucide-react';
import GridBg from '../components/layout/GridBg';
import NavBar from '../components/NavBar';
import Button from '../components/ui/Button';
import Eyebrow from '../components/ui/Eyebrow';

interface Props {
  onBack: () => void;
}

const VALUE_PROPS = [
  {
    icon: BarChart3,
    title: 'Карта навыков команды',
    desc: 'Выявляйте пробелы в знаниях (skill gaps). Система покажет реальный уровень сотрудников и подскажет, кого пора повысить.',
  },
  {
    icon: Route,
    title: 'Планы развития, которые работают',
    desc: 'Вместо формальных таблиц — интерактивные роадмапы, адаптированные под темп сотрудника и стратегию компании.',
  },
  {
    icon: LineChart,
    title: 'Оцифрованные результаты',
    desc: 'Наблюдайте за прогрессом в реальном времени. Вся аналитика по пройденным этапам и освоенным навыкам собирается в единый отчет.',
  },
];

export default function HRLanding({ onBack }: Props) {
  const [email, setEmail] = useState('');
  const [company, setCompany] = useState('');
  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitted(true);
  };

  return (
    <GridBg className="min-h-screen bg-[var(--bg)]">
      <header className="mx-auto w-full max-w-6xl px-5 md:px-8">
        <NavBar />
      </header>

      <main className="mx-auto w-full max-w-6xl px-5 pb-20 md:px-8">
        {/* Hero */}
        <section className="pb-14 pt-8 md:pb-20 md:pt-16">
          <div className="mx-auto max-w-2xl text-center">
            <Eyebrow className="mb-4 inline-flex items-center gap-2 rounded-full bg-[var(--chip)] px-4 py-1.5">
              Для HR и тимлидов
            </Eyebrow>

            <h1 className="text-3xl font-bold tracking-tight text-[var(--ink)] md:text-5xl">
              Превратите карьерный рост сотрудников в систему
            </h1>

            <p className="mx-auto mt-6 max-w-xl text-lg leading-relaxed text-[var(--muted)]">
              Career Copilot — это AI-платформа, которая помогает растить кадры внутри компании,
              снижать текучесть и прозрачно управлять компетенциями команды.
            </p>
          </div>
        </section>

        {/* Value props */}
        <section className="mb-16">
          <div className="grid gap-6 md:grid-cols-3">
            {VALUE_PROPS.map((vp, i) => (
              <div
                key={i}
                className="rounded-2xl border border-[var(--line)] bg-[var(--paper)] p-6 shadow-[var(--shadow-soft)]"
              >
                <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-xl bg-[var(--chip)]">
                  <vp.icon className="h-5 w-5 text-[var(--blue-deep)]" />
                </div>
                <h3 className="mb-2 text-base font-semibold text-[var(--ink)]">{vp.title}</h3>
                <p className="text-sm leading-relaxed text-[var(--muted)]">{vp.desc}</p>
              </div>
            ))}
          </div>
        </section>

        {/* Contact form */}
        <section className="mx-auto max-w-md">
          <div className="rounded-2xl border border-[var(--line)] bg-[var(--paper)] p-8 shadow-[var(--shadow-soft)]">
            {submitted ? (
              <div className="text-center">
                <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-[var(--accent-green)]/10">
                  <CheckCircle2 className="h-6 w-6 text-[var(--accent-green)]" />
                </div>
                <h3 className="text-lg font-semibold text-[var(--ink)]">Заявка отправлена</h3>
                <p className="mt-2 text-sm text-[var(--muted)]">
                  Мы свяжемся с вами в течение одного рабочего дня.
                </p>
              </div>
            ) : (
              <>
                <h3 className="mb-1 text-lg font-semibold text-[var(--ink)]">
                  Узнайте, как Career Copilot поможет вашей команде
                </h3>
                <p className="mb-6 text-sm text-[var(--muted)]">
                  Оставьте заявку, и мы покажем платформу в действии, а также рассчитаем стоимость для вашей компании.
                </p>

                <form onSubmit={handleSubmit} className="space-y-4">
                  <div className="float-field">
                    <input
                      type="email"
                      required
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      className="input-field"
                      placeholder="name@company.com"
                    />
                    <label className="float-label">Рабочий email</label>
                  </div>
                  <div className="float-field">
                    <input
                      type="text"
                      required
                      value={company}
                      onChange={(e) => setCompany(e.target.value)}
                      className="input-field"
                      placeholder="Название вашей компании"
                    />
                    <label className="float-label">Компания</label>
                  </div>
                  <Button type="submit" className="w-full">
                    <Send className="h-4 w-4" />
                    Запросить демо
                  </Button>
                  <p className="text-center text-xs text-[var(--muted)]">
                    Нажимая на кнопку, вы соглашаетесь с политикой конфиденциальности.
                  </p>
                </form>
              </>
            )}
          </div>
        </section>

        {/* Back link */}
        <div className="mt-8 text-center">
          <button
            onClick={onBack}
            className="inline-flex items-center gap-1.5 text-sm font-medium text-[var(--muted)] transition-colors hover:text-[var(--ink)]"
          >
            <ArrowLeft className="h-4 w-4" />
            Вернуться к Career Copilot
          </button>
        </div>
      </main>

      <footer className="border-t border-[var(--line)] py-6 text-center text-xs text-[var(--muted)]">
        Career Copilot
      </footer>
    </GridBg>
  );
}
