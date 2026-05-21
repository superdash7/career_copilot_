import Stepper from './Stepper';
import NavBar from './NavBar';
import GridBg from './layout/GridBg';

interface Props {
  step: number;
  showStepper?: boolean;
  wide?: boolean;
  /** Скрыть кнопку «Личный кабинет» в шапке (например, на странице кабинета). */
  hidePersonalCabinet?: boolean;
  children: React.ReactNode;
}

export default function Layout({
  step,
  showStepper = true,
  wide = false,
  hidePersonalCabinet = false,
  children,
}: Props) {
  const maxW = wide ? 'max-w-6xl' : 'max-w-4xl';
  return (
    <GridBg className="min-h-screen bg-(--color-surface)">
      <header className="sticky top-0 z-30 border-b border-(--color-border) bg-(--color-surface-raised)/85 backdrop-blur-md">
        <div className={`mx-auto ${maxW} px-4`}>
          <NavBar hidePersonalCabinet={hidePersonalCabinet} />
          {showStepper && <Stepper current={step} />}
        </div>
      </header>
      <main className="flex-1">
        <div className={`mx-auto ${maxW} px-4 py-8`}>{children}</div>
      </main>
      <footer className="border-t border-(--color-border-muted) py-4 text-center text-xs text-(--color-text-muted)">
        Career Copilot
      </footer>
    </GridBg>
  );
}
