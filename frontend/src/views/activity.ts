// Activity tab: what changed on the router and who did it (this panel, service calls, entity actions).

import { LitElement, css, html, nothing } from "lit";
import { property, state } from "lit/decorators.js";

import { Activity, define } from "../api";
import { Translate, ago, clock, isKey } from "../i18n";
import { shared } from "../styles";

const value = (e: Event) => (e.target as HTMLSelectElement).value;

export class WoowGlinetActivity extends LitElement {
  @property({ attribute: false }) entries: Activity[] = [];
  @property({ attribute: false }) now = 0;
  @property({ attribute: false }) t!: Translate;
  @property({ type: Boolean }) multi = false; // several routers: name the router on each line

  @state() private channel = "";

  static styles = [
    shared,
    css`
      .entry {
        display: grid;
        grid-template-columns: 7.5em minmax(0, 1fr);
        gap: 4px 12px;
        padding: 10px 0;
        border-top: 1px solid var(--divider-color, #eee);
      }
      .when {
        color: var(--secondary-text-color);
        font-size: 0.85em;
      }
      .fail {
        color: var(--error-color, #db4437);
      }
    `,
  ];

  private channelLabel(channel: string): string {
    const key = `channel_${channel}`;
    return isKey(key) ? this.t(key) : channel;
  }

  /** The entry's message in the panel's language; else the English summary the backend wrote. */
  private message(e: Activity): string {
    const key = `log_${e.msg}`;
    if (!e.msg || !isKey(key)) return e.summary;
    const args: Record<string, string | number> = { ...e.args };
    const code = `err_${args.code}`;
    if ("error" in args && isKey(code)) args.error = this.t(code);
    return this.t(key, args);
  }

  render() {
    const t = this.t;
    const rows = this.entries.filter((e) => !this.channel || e.channel === this.channel).sort((a, b) => b.t - a.t);
    return html`<div class="card">
      <div class="row">
        <h2 class="grow">${t("tab_activity")}</h2>
        <select @change=${(e: Event) => (this.channel = value(e))} aria-label=${t("all_channels")}>
          <option value="">${t("all_channels")}</option>
          ${["panel", "service", "entity"].map((c) => html`<option value=${c}>${this.channelLabel(c)}</option>`)}
        </select>
      </div>
      <div class="muted">${t("activity_hint")}</div>
      ${rows.length === 0
        ? html`<div class="empty">${t("activity_empty")}</div>`
        : rows.map(
            (e) => html`<div class="entry">
              <div class="when" title=${new Date(e.t * 1000).toLocaleString()}>${ago(e.t, t)}<br />${clock(e.t)}</div>
              <div>
                <div class="row">
                  <span class="chip ${e.channel === "service" ? "info" : ""}">${this.channelLabel(e.channel)}</span>
                  ${e.user ? html`<span class="chip">${e.user}</span>` : nothing}
                  ${this.multi && e.router ? html`<span class="chip ok">${e.router}</span>` : nothing}
                </div>
                <div class=${e.ok ? "" : "fail"} title=${e.summary}>${e.ok ? "" : "✗ "}${this.message(e)}</div>
              </div>
            </div>`,
          )}
    </div>`;
  }
}

define("woow-glinet-activity", WoowGlinetActivity);
