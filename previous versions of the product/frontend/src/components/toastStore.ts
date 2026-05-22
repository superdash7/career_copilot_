export interface ToastItem {
  id: number;
  message: string;
  action?: { label: string; onClick: () => void };
}

type Listener = (t: Omit<ToastItem, 'id'>) => void;

let _listener: Listener = () => {};

export function setToastListener(fn: Listener) {
  _listener = fn;
}

export function showToast(message: string, action?: ToastItem['action']) {
  _listener({ message, action });
}
