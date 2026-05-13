/** Same key as used in App for post-register navigation back into the wizard. */
export const PENDING_SCREEN_AFTER_ONBOARDING_KEY = 'career_copilot_resume_after_onboarding';

export const FLOW_WIZARD_SCREEN_IDS = [
  'quickstart',
  'goal',
  'skills',
  'confirm',
  'result',
] as const;

export type FlowWizardScreenId = (typeof FLOW_WIZARD_SCREEN_IDS)[number];

export function isFlowWizardScreenId(id: string): id is FlowWizardScreenId {
  return (FLOW_WIZARD_SCREEN_IDS as readonly string[]).includes(id);
}

export function hasPendingWizardResume(): boolean {
  if (typeof sessionStorage === 'undefined') return false;
  try {
    const raw = sessionStorage.getItem(PENDING_SCREEN_AFTER_ONBOARDING_KEY);
    return Boolean(raw && isFlowWizardScreenId(raw));
  } catch {
    return false;
  }
}
