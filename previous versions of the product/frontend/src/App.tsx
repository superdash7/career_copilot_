import { useState, useEffect, useCallback } from 'react';
import Welcome from './screens/Welcome';
import GoalSetup from './screens/GoalSetup';
import Skills from './screens/Skills';
import Confirmation from './screens/Confirmation';
import Result from './screens/Result';
import Alert from './components/Alert';
import NavBar from './components/NavBar';
import ToastContainer from './components/Toast';
import { healthCheck } from './api/client';
import type { AppState, PlanResponse } from './types';
import { INITIAL_STATE } from './types';

type Screen = 'welcome' | 'goal' | 'skills' | 'confirm' | 'result';

const SCREEN_ORDER: Screen[] = ['welcome', 'goal', 'skills', 'confirm', 'result'];

const STORAGE_KEY = 'career_copilot_state';
const PLAN_STORAGE_KEY = 'career_copilot_plan';

function loadSavedState(): AppState {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      return { ...INITIAL_STATE, ...parsed };
    }
  } catch { /* ignore */ }
  return INITIAL_STATE;
}

function loadSavedPlan(): PlanResponse | null {
  try {
    const raw = sessionStorage.getItem(PLAN_STORAGE_KEY);
    if (raw) return JSON.parse(raw);
  } catch { /* ignore */ }
  return null;
}

function screenFromHash(): Screen {
  const hash = window.location.hash.replace('#', '') as Screen;
  if (SCREEN_ORDER.includes(hash)) return hash;
  return 'welcome';
}

export default function App() {
  const [screen, setScreenRaw] = useState<Screen>(screenFromHash);
  const [state, setStateRaw] = useState<AppState>(loadSavedState);
  const [plan, setPlanRaw] = useState<PlanResponse | null>(loadSavedPlan);
  const [serviceDown, setServiceDown] = useState(false);

  useEffect(() => {
    healthCheck().then((ok) => {
      if (!ok) setServiceDown(true);
    });
  }, []);

  // Persist state to sessionStorage
  useEffect(() => {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  }, [state]);

  useEffect(() => {
    if (plan) {
      sessionStorage.setItem(PLAN_STORAGE_KEY, JSON.stringify(plan));
    } else {
      sessionStorage.removeItem(PLAN_STORAGE_KEY);
    }
  }, [plan]);

  // Browser history integration
  const setScreen = useCallback((s: Screen, replace = false) => {
    setScreenRaw(s);
    const method = replace ? 'replaceState' : 'pushState';
    window.history[method]({ screen: s }, '', `#${s}`);
  }, []);

  useEffect(() => {
    const onPop = (e: PopStateEvent) => {
      const s = (e.state?.screen as Screen) || screenFromHash();
      if (s === 'result' && !plan) {
        setScreenRaw('confirm');
        return;
      }
      setScreenRaw(s);
    };
    window.addEventListener('popstate', onPop);

    // Set initial history entry
    if (!window.history.state?.screen) {
      window.history.replaceState({ screen: screen }, '', `#${screen}`);
    }

    return () => window.removeEventListener('popstate', onPop);
  }, [plan, screen]);

  const update = (patch: Partial<AppState>) =>
    setStateRaw((prev) => ({ ...prev, ...patch }));

  const setPlan = (p: PlanResponse | null) => setPlanRaw(p);

  const reset = () => {
    setStateRaw(INITIAL_STATE);
    setPlanRaw(null);
    sessionStorage.removeItem(STORAGE_KEY);
    sessionStorage.removeItem(PLAN_STORAGE_KEY);
    setScreen('welcome', true);
  };

  if (serviceDown) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center p-8 bg-(--color-surface)">
        <div className="max-w-md w-full">
          <div className="mb-4"><NavBar /></div>
          <Alert variant="warning" title="Сервис временно недоступен">
            Попробуйте обновить страницу через минуту.
          </Alert>
          <div className="mt-4 text-center">
            <button
              onClick={() => {
                healthCheck().then((ok) => {
                  if (ok) setServiceDown(false);
                });
              }}
              className="btn-secondary text-sm"
            >
              Проверить снова
            </button>
          </div>
        </div>
        <ToastContainer />
      </div>
    );
  }

  const renderScreen = () => {
    switch (screen) {
      case 'welcome':
        return <Welcome onStart={() => setScreen('goal')} />;
      case 'goal':
        return (
          <GoalSetup
            state={state}
            onChange={update}
            onNext={() => setScreen('skills')}
            onBack={() => setScreen('welcome')}
          />
        );
      case 'skills':
        return (
          <Skills
            state={state}
            onChange={update}
            onNext={() => setScreen('confirm')}
            onBack={() => setScreen('goal')}
          />
        );
      case 'confirm':
        return (
          <Confirmation
            state={state}
            onBack={() => setScreen('skills')}
            onResult={(p) => {
              setPlan(p);
              setScreen('result');
            }}
          />
        );
      case 'result':
        return plan ? (
          <Result
            plan={plan}
            appState={state}
            onReset={reset}
            onBackToSkills={() => setScreen('skills')}
          />
        ) : (
          <div className="min-h-screen flex flex-col items-center justify-center p-8 bg-(--color-surface)">
            <div className="max-w-md w-full text-center">
              <NavBar />
              <Alert variant="info" title="План ещё не создан">
                Вернитесь к предыдущему шагу и сгенерируйте план.
              </Alert>
              <button
                onClick={() => setScreen('confirm')}
                className="btn-primary mt-6"
              >
                Вернуться к подтверждению
              </button>
            </div>
          </div>
        );
      default:
        return null;
    }
  };

  return (
    <>
      {renderScreen()}
      <ToastContainer />
    </>
  );
}
