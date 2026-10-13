import { Component, type ErrorInfo, type ReactNode } from "react";
import { Icon } from "./Icon";
import { Button } from "./Button";

type Props = {
  children: ReactNode;
  onReset?: () => void;
};

type State = {
  error: Error | null;
};

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("[ErrorBoundary]", error, info.componentStack);
  }

  handleReset = () => {
    this.props.onReset?.();
    this.setState({ error: null });
  };

  render() {
    if (!this.state.error) return this.props.children;

    return (
      <div className="flex min-h-[60vh] items-center justify-center p-6">
        <div className="panel w-full max-w-md p-8 text-center">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-red-500/15 text-red-400">
            <Icon name="alert" className="h-7 w-7" />
          </div>
          <h2 className="mt-4 font-display text-xl font-semibold text-white">
            Something went wrong
          </h2>
          <p className="mt-2 text-sm text-slate-400">
            {this.state.error.message || "An unexpected error occurred while rendering this screen."}
          </p>
          <Button className="mt-6" onClick={this.handleReset}>
            <Icon name="refresh" className="h-4 w-4" /> Try again
          </Button>
        </div>
      </div>
    );
  }
}