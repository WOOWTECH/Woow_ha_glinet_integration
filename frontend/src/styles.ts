import { css } from "lit";

// Shared look: Home Assistant theme variables, so light / dark themes just work (same as WOOW Serial / WOOW CAN).
export const shared = css`
  :host {
    display: block;
    color: var(--primary-text-color);
    font-family: var(--paper-font-body1_-_font-family, Roboto, "Noto Sans TC", sans-serif);
    /* device names and SSIDs are whatever people typed: a 300-character name must wrap, not widen the page */
    overflow-wrap: anywhere;
  }
  .card {
    background: var(--card-background-color, #fff);
    border: 1px solid var(--divider-color, #e0e0e0);
    border-radius: var(--ha-card-border-radius, 12px);
    padding: 16px;
    margin-bottom: 16px;
  }
  .card h2 {
    margin: 0 0 12px;
    font-size: 1.1em;
    font-weight: 500;
  }
  .row {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px;
  }
  .grow {
    flex: 1 1 auto;
    min-width: 0;
  }
  .muted {
    color: var(--secondary-text-color);
    font-size: 0.9em;
  }
  .mono {
    font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
    font-size: 0.92em;
    word-break: break-all;
  }
  .chip {
    display: inline-block;
    padding: 1px 8px;
    border-radius: 10px;
    font-size: 0.8em;
    line-height: 1.6;
    background: var(--secondary-background-color, #eee);
    color: var(--secondary-text-color);
    white-space: nowrap;
    max-width: 100%;
    overflow: hidden;
    text-overflow: ellipsis;
    vertical-align: bottom;
  }
  .chip.ok {
    background: rgba(67, 160, 71, 0.15);
    color: var(--success-color, #43a047);
  }
  .chip.warn {
    background: rgba(255, 152, 0, 0.15);
    color: var(--warning-color, #ff9800);
  }
  .chip.bad {
    background: rgba(219, 68, 55, 0.12);
    color: var(--error-color, #db4437);
  }
  .chip.info {
    background: rgba(3, 169, 244, 0.14);
    color: var(--info-color, #039be5);
  }
  button {
    font: inherit;
    border: 1px solid var(--divider-color, #ccc);
    background: var(--card-background-color, #fff);
    color: var(--primary-text-color);
    border-radius: 8px;
    padding: 4px 10px;
    cursor: pointer;
  }
  button:hover {
    border-color: var(--primary-color);
  }
  button.primary {
    background: var(--primary-color);
    border-color: var(--primary-color);
    color: var(--text-primary-color, #fff);
  }
  button.link {
    border: none;
    background: none;
    color: var(--primary-color);
    padding: 2px 4px;
  }
  button.danger {
    color: var(--error-color, #db4437);
  }
  button.primary.danger {
    background: var(--error-color, #db4437);
    border-color: var(--error-color, #db4437);
    color: #fff;
  }
  button:disabled {
    opacity: 0.5;
    cursor: default;
  }
  input,
  select {
    font: inherit;
    color: var(--primary-text-color);
    background: var(--card-background-color, #fff);
    border: 1px solid var(--divider-color, #ccc);
    border-radius: 8px;
    padding: 6px 8px;
    min-width: 0;
  }
  input:focus,
  select:focus {
    outline: 2px solid var(--primary-color);
    outline-offset: -1px;
  }
  .empty {
    padding: 24px 8px;
    text-align: center;
    color: var(--secondary-text-color);
  }
  .rx {
    color: var(--success-color, #43a047);
  }
  .tx {
    color: var(--info-color, #039be5);
  }
  .dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background: var(--disabled-text-color, #9e9e9e);
    flex: none;
  }
  .dot.on {
    background: var(--success-color, #43a047);
  }
  .dot.bad {
    background: var(--error-color, #db4437);
  }
  .banner {
    padding: 10px 12px;
    border-radius: 8px;
    background: rgba(255, 152, 0, 0.12);
    color: var(--primary-text-color);
    font-size: 0.92em;
    margin-bottom: 12px;
  }
  .banner.bad {
    background: rgba(219, 68, 55, 0.12);
  }
  .error {
    padding: 8px 10px;
    border-radius: 8px;
    background: rgba(219, 68, 55, 0.12);
    color: var(--error-color, #db4437);
    font-size: 0.9em;
  }
  .scrim {
    position: fixed;
    inset: 0;
    z-index: 10;
    background: rgba(0, 0, 0, 0.4);
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 16px;
  }
  .dialog {
    width: min(460px, 100%);
    max-height: 92vh;
    overflow: auto;
    background: var(--card-background-color, #fff);
    border-radius: 12px;
    padding: 20px;
    display: grid;
    gap: 12px;
  }
  .dialog h2 {
    margin: 0;
    font-size: 1.15em;
    font-weight: 500;
  }
  .dialog label {
    display: grid;
    gap: 4px;
    font-size: 0.85em;
    color: var(--secondary-text-color);
  }
  .dialog input,
  .dialog select {
    font-size: 1.05em;
  }
  /* Text colours from the theme can be too pale on their own tinted backgrounds (WCAG AA wants 4.5:1):
     mix them toward the theme's text colour, which darkens them on a light theme and lightens them on a dark one. */
  @supports (color: color-mix(in srgb, red 50%, blue)) {
    .chip.ok,
    .rx {
      color: color-mix(in srgb, var(--success-color, #43a047) 62%, var(--primary-text-color, #212121));
    }
    .chip.info,
    .tx {
      color: color-mix(in srgb, var(--info-color, #039be5) 62%, var(--primary-text-color, #212121));
    }
    .chip.bad,
    .fail,
    button.danger {
      color: color-mix(in srgb, var(--error-color, #db4437) 66%, var(--primary-text-color, #212121));
    }
    .chip.warn {
      color: color-mix(in srgb, var(--warning-color, #ff9800) 50%, var(--primary-text-color, #212121));
    }
    button.link {
      color: color-mix(in srgb, var(--primary-color) 65%, var(--primary-text-color, #212121));
    }
    .chip {
      color: color-mix(in srgb, var(--secondary-text-color) 70%, var(--primary-text-color, #212121));
    }
  }
`;
