export interface Skill {
  name: string;
  level: number; // 0..2, шаг 0.5
}

export const SKILL_LEVELS = [
  { value: 0,   label: 'Нет навыка',    short: '0',   tooltip: 'Не использую' },
  { value: 0.5, label: 'Начальный',     short: '0.5', tooltip: 'Иногда сталкивался' },
  { value: 1,   label: 'Базовый',       short: '1',   tooltip: 'Уверенно применяю' },
  { value: 1.5, label: 'Продвинутый',   short: '1.5', tooltip: 'Использую в сложных ситуациях' },
  { value: 2,   label: 'Эксперт',       short: '2',   tooltip: 'Могу обучать других' },
] as const;

export function skillLevelLabel(level: number): string {
  return SKILL_LEVELS.find((l) => l.value === level)?.label ?? `${level}`;
}

export type Scenario =
  | 'Следующий грейд'
  | 'Смена профессии'
  | 'Исследование возможностей';

export type Grade =
  | 'Младший (Junior)'
  | 'Специалист (Middle)'
  | 'Старший (Senior)'
  | 'Ведущий (Lead)'
  | 'Эксперт (Expert)';

export const GRADES: Grade[] = [
  'Младший (Junior)',
  'Специалист (Middle)',
  'Старший (Senior)',
  'Ведущий (Lead)',
  'Эксперт (Expert)',
];

export const SCENARIOS: { value: Scenario; label: string; description: string }[] = [
  {
    value: 'Следующий грейд',
    label: 'Следующий грейд',
    description: 'Хочу понять, что требуется для перехода на следующий уровень в моей роли.',
  },
  {
    value: 'Смена профессии',
    label: 'Смена профессии',
    description: 'Хочу рассмотреть переход в новую профессию и увидеть недостающие навыки.',
  },
  {
    value: 'Исследование возможностей',
    label: 'Исследование возможностей',
    description: 'Хочу посмотреть, какие роли ближе всего к моему профилю по навыкам.',
  },
];

export interface PlanRequest {
  profession: string;
  grade: Grade;
  skills: Skill[];
  scenario: Scenario;
  target_profession?: string;
}

// --- Structured analysis types ---

export interface RadarPoint {
  param: string;
  current: number;
  target: number;
  current_label: string;
  target_label: string;
}

export interface SkillGap {
  name: string;
  current: number;
  required: number;
  delta: number;
  level_key: string;
  description: string;
  tasks: string;
}

export interface SkillStrong {
  name: string;
  level: number;
}

export interface GrowthAnalysis {
  scenario: 'growth';
  current_grade: string;
  target_grade: string;
  match_percent: number;
  radar_data: RadarPoint[];
  skill_gaps: SkillGap[];
  skill_strong: SkillStrong[];
}

export interface TransferableSkill {
  name: string;
  snippet: string;
}

export interface SwitchGap {
  name: string;
  importance: string;
  level_key: string;
  description: string;
  tasks: string;
}

export interface SwitchAnalysis {
  scenario: 'switch';
  from_role: string;
  to_role: string;
  match_percent: number;
  baseline_level: string;
  transferable: TransferableSkill[];
  gaps: SwitchGap[];
  suggested_tracks: string[];
}

export interface ExploreRole {
  title: string;
  match: number;
  category: 'closest' | 'adjacent' | 'far';
  match_label: string;
  missing: string[];
  key_skills: string[];
  reasons: string[];
}

export interface ExploreAnalysis {
  scenario: 'explore';
  roles: ExploreRole[];
}

export type Analysis = GrowthAnalysis | SwitchAnalysis | ExploreAnalysis;

export interface PlanResponse {
  markdown: string;
  role_titles?: string[];
  analysis?: Analysis;
}

export interface FocusedPlanTask {
  skill: string;
  items: string[];
}

export interface FocusedPlan {
  tasks: FocusedPlanTask[];
  communication: string[];
  learning: string[];
}

export interface AppState {
  profession: string;
  scenario: Scenario | '';
  grade: Grade;
  targetProfession: string;
  skills: Skill[];
}

export const INITIAL_STATE: AppState = {
  profession: '',
  scenario: '',
  grade: 'Специалист (Middle)',
  targetProfession: '',
  skills: [],
};
