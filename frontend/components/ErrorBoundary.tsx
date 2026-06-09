"use client";

import { Component, type ErrorInfo, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/Card";

interface State {
  error: Error | null;
}

export class ErrorBoundary extends Component<{ children: ReactNode }, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("Page error boundary caught:", error, errorInfo);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="grid min-h-screen place-items-center p-6">
          <Card className="max-w-lg p-6">
            <h1 className="text-xl font-medium">Something went wrong</h1>
            <p className="mt-3 text-sm text-[var(--text-secondary)]">
              {process.env.NODE_ENV === "development" ? this.state.error.message : "Refresh the page and try again."}
            </p>
            <Button className="mt-5" onClick={() => this.setState({ error: null })} variant="primary">
              Retry
            </Button>
          </Card>
        </div>
      );
    }

    return this.props.children;
  }
}
