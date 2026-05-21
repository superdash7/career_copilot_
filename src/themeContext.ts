import { createContext } from 'react';

type Theme = 'light' | 'dark';

export interface ThemeCtx {
  theme: Theme;
  toggle: () => void;
}

export const ThemeContext = createContext<ThemeCtx>({ theme: 'light', toggle: () => {} });
