import { useState } from 'react';
import Alert from '../components/Alert';
import GridBg from '../components/layout/GridBg';
import Button from '../components/ui/Button';
import LegalModal from '../components/LegalModal';
import { useAuth } from '../auth/AuthContext';
import { CONSENT_FULL_TEXT, PRIVACY_FULL_TEXT } from '../legal/legalFullTexts';

interface Props {
  initialMode?: 'login' | 'register';
  onSuccess: () => void;
  onSkip?: () => void;
  onBackToPublic?: () => void;
  authNotice?: string;
  onDismissNotice?: () => void;
}

export default function Auth({
  initialMode = 'register',
  onSuccess,
  onSkip,
  onBackToPublic,
  authNotice,
  onDismissNotice,
}: Props) {
  const { login, register } = useAuth();
  const [mode, setMode] = useState<'login' | 'register'>(initialMode);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [showPrivacy, setShowPrivacy] = useState(false);
  const [showConsent, setShowConsent] = useState(false);
  const [consentPurposePlan, setConsentPurposePlan] = useState(false);
  const [consentPurposeInfo, setConsentPurposeInfo] = useState(false);

  const consentPurposesOk = consentPurposePlan && consentPurposeInfo;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    if (mode === 'register' && !consentPurposesOk) {
      setError('Отметьте оба пункта под «в целях».');
      return;
    }
    setLoading(true);
    try {
      if (mode === 'register') {
        await register(email.trim(), password);
      } else {
        await login(email, password);
      }
      onSuccess();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Произошла ошибка');
    } finally {
      setLoading(false);
    }
  };

  return (
    <GridBg className="flex min-h-screen items-center justify-center bg-[var(--bg)]">
      <div className="w-full max-w-[420px] px-5">
        <div className="rounded-2xl border border-[var(--line)] bg-[var(--paper)] p-8 shadow-[var(--shadow-soft)]">
          {/* Logo + tagline */}
          <div className="mb-8 text-center">
            <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-[var(--blue-deep)] text-lg font-bold text-white">
              ✦
            </div>
            <h1 className="text-xl font-semibold text-[var(--ink)]">Career Copilot</h1>
            <p className="mt-1 text-sm text-[var(--muted)]">
              Твой AI-проводник на пути к блистательной карьере
            </p>
          </div>

          {authNotice && (
            <div className="mb-4">
              <Alert variant="warning" onClose={onDismissNotice}>
                {authNotice}
              </Alert>
            </div>
          )}

          {error && (
            <div className="mb-4">
              <Alert variant="error" onClose={() => setError('')}>
                {error}
              </Alert>
            </div>
          )}

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="float-field">
              <input
                id="auth-email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="input-field"
                placeholder="Email"
                autoComplete="email"
              />
              <label htmlFor="auth-email" className="float-label">
                Email
              </label>
            </div>
            <div className="float-field">
              <input
                id="auth-password"
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="input-field"
                placeholder="Пароль"
                minLength={mode === 'register' ? 8 : undefined}
                autoComplete={mode === 'register' ? 'new-password' : 'current-password'}
              />
              <label htmlFor="auth-password" className="float-label">
                Пароль
              </label>
            </div>

            {mode === 'register' && (
              <div className="rounded-xl border border-[var(--line)] bg-[var(--paper)] p-4 text-left text-sm leading-relaxed text-[var(--ink)]">
                <p className="m-0 text-left text-[var(--ink)]">
                  Соглашаюсь на обработку персональных данных на условиях{' '}
                  <button
                    type="button"
                    className="m-0 inline border-0 bg-transparent p-0 text-left align-baseline font-semibold text-[var(--blue-deep)] underline decoration-[var(--blue-deep)] underline-offset-2 hover:text-[var(--color-accent-hover)]"
                    onClick={() => setShowPrivacy(true)}
                  >
                    политики
                  </button>{' '}
                  и{' '}
                  <button
                    type="button"
                    className="m-0 inline max-w-full border-0 bg-transparent p-0 text-left align-baseline font-semibold hover:text-[var(--color-accent-hover)]"
                    onClick={() => setShowConsent(true)}
                  >
                    <span className="text-[var(--blue-deep)] underline decoration-[var(--blue-deep)] underline-offset-2">
                      согласия на обработку персональных данных
                    </span>
                    {/* U+2060: не даём переносу оторвать «, в целях:» от конца ссылки */}
                    <span className="whitespace-nowrap font-normal text-[var(--ink)] no-underline">
                      {'\u2060'}
                      {',\u00a0в\u00a0целях:'}
                    </span>
                  </button>
                </p>
                <div className="mt-3 space-y-2.5">
                  <label
                    htmlFor="auth-consent-plan"
                    className="flex cursor-pointer items-start gap-2.5 text-left text-[var(--ink)]"
                  >
                    <input
                      id="auth-consent-plan"
                      type="checkbox"
                      checked={consentPurposePlan}
                      onChange={(e) => setConsentPurposePlan(e.target.checked)}
                      className="mt-0.5 size-4 shrink-0 rounded border-[var(--line)] text-[var(--blue-deep)] focus:ring-[var(--blue-deep)]"
                    />
                    <span className="min-w-0 flex-1 text-left leading-relaxed">
                      Формирования моего индивидуального плана карьерного роста.
                    </span>
                  </label>
                  <label
                    htmlFor="auth-consent-info"
                    className="flex cursor-pointer items-start gap-2.5 text-left text-[var(--ink)]"
                  >
                    <input
                      id="auth-consent-info"
                      type="checkbox"
                      checked={consentPurposeInfo}
                      onChange={(e) => setConsentPurposeInfo(e.target.checked)}
                      className="mt-0.5 size-4 shrink-0 rounded border-[var(--line)] text-[var(--blue-deep)] focus:ring-[var(--blue-deep)]"
                    />
                    <span className="min-w-0 flex-1 text-left leading-relaxed">
                      Направления мне информации о возможностях сервиса.
                    </span>
                  </label>
                </div>
              </div>
            )}

            <Button type="submit" className="w-full" disabled={loading || (mode === 'register' && !consentPurposesOk)}>
              {loading
                ? (mode === 'register' ? 'Создаем аккаунт...' : 'Входим...')
                : (mode === 'register' ? 'Создать аккаунт' : 'Войти')
              }
            </Button>
          </form>

          {/* Mode toggle */}
          <div className="mt-5 text-center text-sm text-[var(--muted)]">
            {mode === 'register' ? (
              <>
                Уже есть аккаунт?{' '}
                <button
                  type="button"
                  onClick={() => { setMode('login'); setError(''); setConsentPurposePlan(false); setConsentPurposeInfo(false); }}
                  className="font-semibold text-[var(--blue-deep)] hover:underline"
                >
                  Войти
                </button>
              </>
            ) : (
              <>
                Нет аккаунта?{' '}
                <button
                  type="button"
                  onClick={() => { setMode('register'); setError(''); setConsentPurposePlan(false); setConsentPurposeInfo(false); }}
                  className="font-semibold text-[var(--blue-deep)] hover:underline"
                >
                  Создать
                </button>
              </>
            )}
          </div>

          {/* Skip */}
          {onSkip && (
            <div className="mt-4 text-center">
              <button
                type="button"
                onClick={onSkip}
                className="text-sm font-medium text-[var(--muted)] transition-colors hover:text-[var(--ink)] hover:underline"
              >
                Продолжить без аккаунта →
              </button>
            </div>
          )}
        </div>

        {onBackToPublic && (
          <div className="mt-4 text-center">
            <button
              type="button"
              onClick={onBackToPublic}
              className="text-sm font-medium text-[var(--muted)] transition-colors hover:text-[var(--ink)] hover:underline"
            >
              ← На главную
            </button>
          </div>
        )}

        <LegalModal
          open={showPrivacy}
          title="Политика конфиденциальности и обработки персональных данных"
          onClose={() => setShowPrivacy(false)}
        >
          <div className="whitespace-pre-wrap">{PRIVACY_FULL_TEXT}</div>
        </LegalModal>
        <LegalModal open={showConsent} title="Согласие на обработку персональных данных" onClose={() => setShowConsent(false)}>
          <div className="whitespace-pre-wrap">{CONSENT_FULL_TEXT}</div>
        </LegalModal>
      </div>
    </GridBg>
  );
}
