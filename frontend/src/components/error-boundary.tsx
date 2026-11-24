"use client";

import { Component, type ErrorInfo, type ReactNode } from "react";
import { Button } from "./ui/button";

type Props = {
  children: ReactNode;
  fallbackTitle?: string;
};

type State = {
  error: Error | null;
};

/**
 * Catches render errors so the desk never sticks on a blank/skeleton shell.
 */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    if (process.env.NODE_ENV !== "production") {
      console.error("ErrorBoundary", error, info.componentStack);
    }
  }

  private reset = () => {
    this.setState({ error: null });
  };

  render() {
    if (!this.state.error) return this.props.children;

    return (
      <div
        role="alert"
        className="mx-auto flex w-full max-w-lg flex-col gap-4 px-6 py-16 text-center"
      >
        <h1 className="font-[family-name:var(--font-display)] text-2xl text-[var(--ink)]">
          {this.props.fallbackTitle ?? "Something went wrong"}
        </h1>
        <p className="text-sm text-[var(--fog)]">
          The page hit an unexpected error. You can retry, or go back to the desk.
        </p>
        <div className="flex flex-wrap items-center justify-center gap-3">
          <Button type="button" onClick={this.reset}>
            Try again
          </Button>
          <Button
            type="button"
            variant="outline"
            onClick={() => {
              // Class error boundary cannot use useRouter; full navigation resets app state.
              // eslint-disable-next-line @next/next/no-location-assign-relative-destination
              window.location.href = "/";
            }}
          >
            Back to desk
          </Button>
        </div>
      </div>
    );
  }
}
