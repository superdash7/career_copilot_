import { Component } from 'react';
import type { ReactNode, ErrorInfo } from 'react';
import { AlertTriangle, RotateCcw } from 'lucide-react';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
}

export default class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(): State {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('ErrorBoundary caught:', error, info);
  }

  handleReset = () => {
    this.setState({ hasError: false });
    window.location.hash = '';
    window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen flex items-center justify-center bg-(--color-surface) p-8">
          <div className="max-w-md w-full text-center">
            <div className="mb-6 inline-flex items-center justify-center h-16 w-16 rounded-2xl bg-red-500/10">
              <AlertTriangle className="h-8 w-8 text-red-500" />
            </div>
            <h1 className="text-2xl font-bold text-(--color-text-primary) mb-2">
              Что-то пошло не так
            </h1>
            <p className="text-(--color-text-secondary) mb-8">
              Произошла непредвиденная ошибка. Попробуйте начать заново.
            </p>
            <button onClick={this.handleReset} className="btn-primary">
              <RotateCcw className="h-4 w-4" /> Начать заново
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
