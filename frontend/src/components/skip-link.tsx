/** First focusable control for keyboard users — jumps past chrome into main content. */
export function SkipLink() {
  return (
    <a href="#main-content" className="sd-skip-link">
      Skip to main content
    </a>
  );
}
