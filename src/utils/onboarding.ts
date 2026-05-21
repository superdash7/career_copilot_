import type { OnboardingPainPoint, Scenario, UserProfile } from '../types';

export const PAIN_POINT_TO_SCENARIO: Record<OnboardingPainPoint, Scenario> = {
  рост: 'Следующий грейд',
  смена: 'Смена профессии',
  стагнация: 'Исследование возможностей',
  неопределённость: 'Исследование возможностей',
};

export function recommendScenarioFromPainPoint(painPoint: OnboardingPainPoint): Scenario {
  return PAIN_POINT_TO_SCENARIO[painPoint] || 'Исследование возможностей';
}

export function deriveScenarioRecommendation(painPoint: OnboardingPainPoint): Scenario {
  return recommendScenarioFromPainPoint(painPoint);
}

export function deriveWeeklyHours(hours?: number): number | undefined {
  if (typeof hours !== 'number' || !Number.isFinite(hours) || hours <= 0) return undefined;
  return Math.round(hours);
}

export function hasCompletedOnboarding(user: UserProfile | null): boolean {
  if (!user) return false;
  const hasExperience = typeof user.experience_level === 'string' && user.experience_level.trim().length > 0;
  const hasPainPoint = typeof user.pain_point === 'string' && user.pain_point.trim().length > 0;
  const hasHours =
    typeof user.development_hours_per_week === 'number' &&
    Number.isFinite(user.development_hours_per_week) &&
    user.development_hours_per_week > 0;
  return hasExperience && hasPainPoint && hasHours;
}
