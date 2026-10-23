// Overview tab: the router's state, live internet traffic and the busiest devices.

import { LitElement, css, html, nothing } from "lit";
import { property, state } from "lit/decorators.js";

import { Api, Client, Router, Sample, clientName, define } from "../api";
import "../chart";
import { Translate, ago, explain, formatBytes, formatDuration, formatRate } from "../i18n";
import { shared } from "../styles";
import { askConfirm, linkLabel, modeLabel, notify } from "../ui";

type Range = "5m" | "30m" | "all";
const RANGES: Record<Range, number> = { "5m": 300, "30m": 1800, all: 0 };
const TOP = 6;

export class WoowGlinetOverview extends LitElement {
  @property({ attribute: false }) router!: Router;
  @property({ attribute: false }) wan: Sample[] = [];
  @property({ attribute: false }) t!: Translate;
  @property({ attribute: false }) api!: Api;
  @property({ attribute: false }) now = 0;

  @state() private range: Range = "30m";
  @state() private busy = false;

  static styles = [
    shared,
    css`
      .title {
        font-size: 1.1em;
        font-weight: 500;
      }
      .facts {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
        gap: 12px 16px;
        margin: 14px 0;
      }
      .k {
        font-size: 0.8em;
        color: var(--secondary-text-color);
      }
      .v {
        margin-top: 2px;
        word-break: break-word;
      }
      .meter {
        height: 6px;
        border-radius: 3px;
        background: var(--secondary-background-color, #eee);
        margin-top: 4px;
        overflow: hidden;
      }
      .meter > div {
        height: 100%;
        background: var(--primary-color);
      }
      .meter > div.warn {
        background: var(--warning-color, #ff9800);
      }
      .meter > div.bad {
        background: var(--error-color, #db4437);
      }
      .ranges button {
        border-radius: 14px;
        padding: 2px 10px;
        font-size: 0.85em;
      }
      .ranges button.on {
        background: var(--primary-color);
        border-color: var(--primary-color);
        color: var(--text-primary-color, #fff);
      }
      .big {
        display: flex;
        flex-wrap: wrap;
        gap: 4px 28px;
        margin: 4px 0 8px;
      }
      .big .num {
        font-size: 1.5em;
        font-weight: 500;
      }
      .top {
        display: grid;
        gap: 10px;
      }
      .top .who {
        min-width: 0;
      }
      .top .name {
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      .bars {
        display: grid;
        gap: 3px;
        margin-top: 4px;
      }
      .bar {
        height: 5px;
        border-radius: 3px;
        min-width: 2px;
      }
      .bar.rx {
        background: var(--success-color, #43a047);
      }
      .bar.tx {
        background: var(--info-color, #039be5);
      }
      .rates {
        text-align: right;
        font-variant-numeric: tabular-nums;
        white-space: nowrap;
      }
    `,
  ];

  private get series(): Sample[] {
    const window = RANGES[this.range];
    if (!window || this.wan.length === 0) return this.wan;
    const from = this.wan[this.wan.length - 1][0] - window;
    return this.wan.filter((s) => s[0] >= from);
  }

  private async refresh(): Promise<void> {
    this.busy = true;
    try {
      await this.api.refresh(this.router.entry_id);
    } catch (err) {
      notify(this, explain(err, this.t), false);
    } finally {
      this.busy = false;
    }
  }

  private reboot(): void {
    const t = this.t;
    askConfirm(this, {
      title: t("reboot_title", { router: this.router.title }),
      text: t("reboot_text"),
      action: t("reboot"),
      danger: true,
      run: async () => {
        try {
          await this.api.reboot(this.router.entry_id);
          notify(this, t("rebooting"));
        } catch (err) {
          notify(this, explain(err, t), false);
        }
      },
    });
  }

  private meter(used: number, total: number) {
    const pct = total > 0 ? Math.min(100, Math.max(0, (used / total) * 100)) : 0;
    return html`<div class="meter"><div class=${pct > 95 ? "bad" : pct > 85 ? "warn" : ""} style="width:${pct.toFixed(0)}%"></div></div>`;
  }

  private fact(label: string, value: unknown) {
    return html`<div><div class="k">${label}</div><div class="v">${value}</div></div>`;
  }

  private renderFacts() {
    const r = this.router;
    const t = this.t;
    const uptime = r.uptime != null ? r.uptime + Math.max(0, this.now / 1000 - r.fetched_at) : null;
    const memUsed = r.memory ? r.memory.total - r.memory.free - r.memory.cache : 0;
    const flashUsed = r.flash ? r.flash.total - r.flash.free : 0;
    const online = r.clients.filter((c) => c.online).length;
    const wired = r.stations.cable ?? 0;
    const wireless = r.stations.wireless ?? 0;
    return html`<div class="facts">
      ${this.fact(t("fact_model"), r.model ?? "—")} ${this.fact(t("fact_firmware"), r.firmware ?? "—")}
      ${this.fact(t("fact_address"), html`<span class="mono">${r.host}</span>`)}
      ${r.lan_ip && r.lan_ip !== r.host ? this.fact(t("fact_lan"), html`<span class="mono">${r.lan_ip}</span>`) : nothing}
      ${uptime != null ? this.fact(t("fact_uptime"), formatDuration(uptime)) : nothing}
      ${r.load ? this.fact(t("fact_load"), r.load.map((n) => n.toFixed(2)).join(" / ")) : nothing}
      ${r.memory
        ? this.fact(t("fact_memory"), html`${t("used_of", { used: formatBytes(memUsed), total: formatBytes(r.memory.total) })}${this.meter(memUsed, r.memory.total)}`)
        : nothing}
      ${r.flash
        ? this.fact(t("fact_storage"), html`${t("used_of", { used: formatBytes(flashUsed), total: formatBytes(r.flash.total) })}${this.meter(flashUsed, r.flash.total)}`)
        : nothing}
      ${this.fact(
        t("fact_internet"),
        r.wan.online
          ? html`<span class="chip ok">${t("wan_online")}</span> <span class="muted">${r.wan.links.map((l) => linkLabel(l, t)).join(", ")}</span>`
          : html`<span class="chip bad">${t("wan_offline")}</span>`,
      )}
      ${r.mode === "router"
        ? this.fact(t("fact_devices"), html`${t("devices_online", { n: online })}<div class="muted">${t("devices_split", { wired, wireless })}</div>`)
        : nothing}
    </div>`;
  }

  private renderTraffic() {
    const t = this.t;
    const data = this.series;
    const last = data[data.length - 1];
    const peakRx = Math.max(0, ...data.map((s) => s[1]));
    const peakTx = Math.max(0, ...data.map((s) => s[2]));
    return html`<div class="card">
      <div class="row">
        <h2 class="grow" style="margin:0">${t("traffic_title")}</h2>
        <div class="row ranges">
          ${(Object.keys(RANGES) as Range[]).map(
            (r) => html`<button class=${this.range === r ? "on" : ""} @click=${() => (this.range = r)}>${t(`range_${r}` as "range_5m")}</button>`,
          )}
        </div>
      </div>
      <div class="big">
        <div><div class="k">${t("download")}</div><div class="num rx">↓ ${formatRate(last ? last[1] : this.router.wan.rx)}</div><div class="muted">${t("peak", { x: formatRate(peakRx) })}</div></div>
        <div><div class="k">${t("upload")}</div><div class="num tx">↑ ${formatRate(last ? last[2] : this.router.wan.tx)}</div><div class="muted">${t("peak", { x: formatRate(peakTx) })}</div></div>
      </div>
      <woow-glinet-chart .samples=${data} .t=${t}></woow-glinet-chart>
    </div>`;
  }

  private renderBusiest() {
    const t = this.t;
    const clients = this.router.clients
      .filter((c) => c.online && c.rx + c.tx > 0)
      .sort((a, b) => b.rx + b.tx - (a.rx + a.tx))
      .slice(0, TOP);
    const peak = Math.max(1, ...clients.map((c) => Math.max(c.rx, c.tx)));
    const bar = (cls: string, value: number) => html`<div class="bar ${cls}" style="width:${Math.max(0, (value / peak) * 100).toFixed(1)}%"></div>`;
    return html`<div class="card">
      <h2>${t("busiest_title")}</h2>
      ${clients.length === 0
        ? html`<div class="muted">${t("busiest_empty")}</div>`
        : html`<div class="top">
            ${clients.map(
              (c: Client) => html`<div class="row" style="flex-wrap:nowrap;align-items:flex-start">
                <div class="who grow">
                  <div class="name"><b>${clientName(c)}</b> <span class="muted mono">${c.ip}</span></div>
                  <div class="bars">${bar("rx", c.rx)}${bar("tx", c.tx)}</div>
                </div>
                <div class="rates"><div class="rx">↓ ${formatRate(c.rx)}</div><div class="tx">↑ ${formatRate(c.tx)}</div></div>
              </div>`,
            )}
          </div>`}
    </div>`;
  }

  render() {
    const r = this.router;
    const t = this.t;
    return html`
      ${!r.available ? html`<div class="banner bad">${t("unreachable")}</div>` : nothing}
      ${r.mode !== "router" ? html`<div class="banner">${t("mode_note")}</div>` : nothing}
      <div class="card">
        <div class="row">
          <span class="dot ${r.available ? "on" : "bad"}"></span>
          <span class="title grow">${r.title}</span>
          <span class="chip ${r.mode === "router" ? "ok" : "warn"}">${modeLabel(r.mode, t)}</span>
        </div>
        <div class="muted" style="margin-top:2px">${t("updated", { x: ago(r.fetched_at, t) })}</div>
        ${this.renderFacts()}
        <div class="row">
          <button ?disabled=${this.busy} @click=${() => this.refresh()}>${t("refresh")}</button>
          <button class="danger" @click=${() => this.reboot()}>${t("reboot")}</button>
        </div>
      </div>
      ${r.mode === "router" ? html`${this.renderTraffic()}${this.renderBusiest()}` : nothing}
    `;
  }
}

define("woow-glinet-overview", WoowGlinetOverview);
