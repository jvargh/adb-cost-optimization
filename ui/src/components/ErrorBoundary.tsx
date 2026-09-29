import { Component, type ErrorInfo, type ReactNode } from 'react';

interface Props {
  children: ReactNode;
  label: string;
}

interface State {
  error: Error | null;
}

/**
 * Renders the failure instead of blanking the screen. An assessment tool that
 * silently disappears is indistinguishable from one reporting "no findings",
 * which is exactly the ambiguity this toolkit refuses to create elsewhere.
 */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error(`[${this.props.label}] render failed`, error, info.componentStack);
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div className="callout danger">
        <span className="callout-icon">!</span>
        <div className="callout-body">
          <span className="callout-title">{this.props.label} could not be rendered</span>
          <span>
            This is a UI defect, not an assessment result. The underlying evidence is unchanged — nothing
            here should be read as "no cost" or "no findings".
          </span>
          <code className="mono">{this.state.error.message}</code>
          <div className="row">
            <button type="button" className="btn btn-sm" onClick={() => this.setState({ error: null })}>
              Try again
            </button>
          </div>
        </div>
      </div>
    );
  }
}
