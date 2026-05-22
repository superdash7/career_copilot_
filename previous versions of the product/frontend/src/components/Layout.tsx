import Stepper from './Stepper';
import NavBar from './NavBar';

interface Props {
  step: number;
  showStepper?: boolean;
  wide?: boolean;
  children: React.ReactNode;
}

export default function Layout({ step, showStepper = true, wide = false, children }: Props) {
  const maxW = wide ? 'max-w-5xl' : 'max-w-3xl';
  return (
    <div className="min-h-screen flex flex-col bg-(--color-surface)">
      <header className="sticky top-0 z-30 border-b border-(--color-border) bg-(--color-surface-raised)/80 backdrop-blur-md">
        <div className="mx-auto max-w-3xl px-4">
          <NavBar />
          {showStepper && <Stepper current={step} />}
        </div>
      </header>
      <main className="flex-1">
        <div className={`mx-auto ${maxW} px-4 py-8`}>{children}</div>
      </main>
      <footer className="border-t border-(--color-border-muted) py-4 text-center text-xs text-(--color-text-muted)">
        Career Copilot
      </footer>
    </div>
  );
}
