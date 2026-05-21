import { createContext, useContext } from 'react';

/** Переход в личный кабинет (#dashboard) из шапки Layout на всех шагах мастера. */
const GoToDashboardContext = createContext<() => void>(() => {});

export function GoToDashboardProvider({
  value,
  children,
}: {
  value: () => void;
  children: React.ReactNode;
}) {
  return <GoToDashboardContext.Provider value={value}>{children}</GoToDashboardContext.Provider>;
}

export function useGoToDashboard() {
  return useContext(GoToDashboardContext);
}
