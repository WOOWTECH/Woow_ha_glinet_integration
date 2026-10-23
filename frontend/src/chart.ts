// A small SVG area chart of download (rx) and upload (tx) speed; no chart library.
// `compact` is the per-device sparkline: no axes, no tooltip text.

import { LitElement, css, html, nothing, svg } from "lit";
import { property, state } from "lit/decorators.js";

import { Sample, define } from "./api";
import { Translate, clock, formatRate } from "./i18n";
import { shared } from "./styles";
import { niceCeil } from "./util";

const PAD = { l: 4, r: 4, t: 16, b: 18 };
const MIN_TOP = 1000; // bytes/s: an idle line stays flat at the bottom instead of zooming into noise

export class WoowGlinetChart extends LitElement {
  @property({ attribute: false }) samples: Sample[] = [];
  @property({ attribute: false }) t!: Translate;
  @property({ type: Number }) window = 0; // seconds shown, ending at the newest sample; 0 = everything
  @property({ type: Boolean }) compact = false;
  @property({ type: Number }) height = 0; // px; 0 = 44 (compact) or 170

  @state() private width = 600;
  @state() private hover: number | null = null;

  private observer?: ResizeObserver;

  static styles = [
    shared,
    css`
      :host {
        position: relative;
        display: block;
      }
      svg {
        display: block;
        width: 100%;
        touch-action: pan-y;
      }
      .grid {
        stroke: var(--divider-color, #e0e0e0);
        stroke-width: 1;
      }
      .axis {
        fill: var(--secondary-text-color);
        font-size: 10px;
      }
      .line {
        fill: none;
        stroke-width: 1.5;
        stroke-linejoin: round;
      }
      .line.rx {
        stroke: var(--success-color, #43a047);
      }
      .line.tx {
        stroke: var(--info-color, #039be5);
      }
      .area.rx {
        fill: var(--success-color, #43a047);
        fill-opacity: 0.16;
      }
      .area.tx {
        fill: var(--info-color, #039be5);
        fill-opacity: 0.16;
      }
      .cursor {
        stroke: var(--secondary-text-color);
        stroke-width: 1;
        stroke-dasharray: 3 3;
      }
      .tip {
        position: absolute;
        top: 0;
        pointer-events: none;
        padding: 4px 8px;
        border-radius: 6px;
        font-size: 0.8em;
        white-space: nowrap;
        background: var(--card-background-color, #fff);
        border: 1px solid var(--divider-color, #ccc);
        box-shadow: 0 1px 4px rgba(0, 0, 0, 0.2);
      }
      .none {
        display: flex;
        align-items: center;
        justify-content: center;
        color: var(--secondary-text-color);
        font-size: 0.9em;
      }
    `,
  ];

  connectedCallback(): void {
    super.connectedCallback();
    this.observer = new ResizeObserver((entries) => {
      const w = Math.round(entries[0].contentRect.width);
      if (w > 0 && w !== this.width) this.width = w;
    });
    this.observer.observe(this);
  }

  disconnectedCallback(): void {
    super.disconnectedCallback();
    this.observer?.disconnect();
  }

  private get visible(): Sample[] {
    const all = this.samples;
    if (!this.window || all.length === 0) return all;
    const from = all[all.length - 1][0] - this.window;
    const i = all.findIndex((s) => s[0] >= from);
    return i < 0 ? [] : all.slice(i);
  }

  private onMove(e: PointerEvent, data: Sample[], x: (time: number) => number): void {
    const box = (e.currentTarget as SVGElement).getBoundingClientRect();
    const px = e.clientX - box.left;
    let best = 0;
    for (let i = 1; i < data.length; i++) {
      if (Math.abs(x(data[i][0]) - px) < Math.abs(x(data[best][0]) - px)) best = i;
    }
    this.hover = best;
  }

  render() {
    const data = this.visible;
    const height = this.height || (this.compact ? 44 : 170);
    if (data.length < 2) {
      return html`<div class="none" style="height:${height}px">${this.compact ? nothing : this.t("chart_empty")}</div>`;
    }
    const pad = this.compact ? { l: 2, r: 2, t: 3, b: 3 } : PAD;
    const w = this.width;
    const t0 = data[0][0];
    const t1 = data[data.length - 1][0];
    const top = niceCeil(Math.max(MIN_TOP, ...data.map((s) => Math.max(s[1], s[2]))));
    const x = (time: number) => pad.l + ((time - t0) / (t1 - t0 || 1)) * (w - pad.l - pad.r);
    const y = (value: number) => height - pad.b - (value / top) * (height - pad.t - pad.b);
    const base = y(0);
    const path = (index: 1 | 2) => data.map((s, i) => `${i ? "L" : "M"}${x(s[0]).toFixed(1)},${y(s[index]).toFixed(1)}`).join(" ");
    const area = (index: 1 | 2) => `${path(index)} L${x(t1).toFixed(1)},${base} L${x(t0).toFixed(1)},${base} Z`;
    const point = this.hover !== null ? data[Math.min(this.hover, data.length - 1)] : null;
    const withSeconds = t1 - t0 < 600;
    const last = data[data.length - 1];
    return html`<svg
        role="img"
        aria-label=${this.t("traffic_now", { rx: formatRate(last[1]), tx: formatRate(last[2]) })}
        viewBox="0 0 ${w} ${height}"
        height=${height}
        @pointermove=${(e: PointerEvent) => !this.compact && this.onMove(e, data, x)}
        @pointerleave=${() => (this.hover = null)}
      >
        ${this.compact
          ? nothing
          : svg`
            <line class="grid" x1=${pad.l} x2=${w - pad.r} y1=${y(top)} y2=${y(top)}></line>
            <line class="grid" x1=${pad.l} x2=${w - pad.r} y1=${y(top / 2)} y2=${y(top / 2)}></line>
            <line class="grid" x1=${pad.l} x2=${w - pad.r} y1=${base} y2=${base}></line>
            <text class="axis" x=${pad.l + 2} y=${y(top) - 2}>${formatRate(top)}</text>
            <text class="axis" x=${pad.l + 2} y=${y(top / 2) - 2}>${formatRate(top / 2)}</text>
            <text class="axis" x=${pad.l} y=${height - 4}>${clock(t0, withSeconds)}</text>
            <text class="axis" x=${w - pad.r} y=${height - 4} text-anchor="end">${clock(t1, withSeconds)}</text>`}
        ${svg`
          <path class="area rx" d=${area(1)}></path>
          <path class="area tx" d=${area(2)}></path>
          <path class="line rx" d=${path(1)}></path>
          <path class="line tx" d=${path(2)}></path>`}
        ${point
          ? svg`<line class="cursor" x1=${x(point[0])} x2=${x(point[0])} y1=${pad.t} y2=${base}></line>`
          : nothing}
      </svg>
      ${point
        ? html`<div class="tip" style="left:${Math.min(Math.max(x(point[0]) - 70, 0), w - 150)}px">
            <b>${clock(point[0])}</b>
            <span class="rx">↓ ${formatRate(point[1])}</span> <span class="tx">↑ ${formatRate(point[2])}</span>
          </div>`
        : nothing}`;
  }
}

define("woow-glinet-chart", WoowGlinetChart);
