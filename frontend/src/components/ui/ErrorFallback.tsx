"use client";

import { Component, ReactNode } from "react";

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error?: Error;
}

export default class ErrorFallback extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div className="flex flex-col items-center justify-center py-16 px-4 text-center">
          <div className="text-destructive mb-4 text-4xl animate-float">⚠</div>
          <h3 className="text-lg font-semibold text-surface-foreground font-heading">
            出错了
          </h3>
          <p className="mt-2 text-sm text-surface-muted-foreground max-w-sm">
            {this.state.error?.message || "发生了未知错误"}
          </p>
          <button
            onClick={() => this.setState({ hasError: false })}
            className="mt-4 px-5 py-2 bg-brand-accent text-surface-card rounded-xl text-sm hover:bg-brand-accent-strong hover:shadow-[var(--shadow-glow-sm)] active:scale-[0.98] transition-all duration-200 cursor-pointer"
          >
            重试
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
