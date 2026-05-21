import { useContext } from 'react';
import { ThemeContext } from './themeContext';
import type { ThemeCtx } from './themeContext';

export function useTheme(): ThemeCtx {
  return useContext(ThemeContext);
}
