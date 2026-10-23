// Devices tab: every device the router knows, with live speed, totals and the controls
// (block, fixed IP, forget an offline one).

import { LitElement, css, html, nothing } from "lit";
import { property, state } from "lit/decorators.js";
import { repeat } from "lit/directives/repeat.js";

import { Api, Client, Router, Sample, clientName, copyText, define } from "../api";
import "../chart";
import { Translate, ago, explain, formatBytes, formatRate } from "../i18n";
import { shared } from "../styles";
import { askConfirm, ifaceLabel, notify } from "../ui";

type Filter = "all" | "online" | "offline" | "blocked";
type Sort = "speed" | "total" | "name" | "ip";
const FILTERS: Filter[] = ["all", "online", "offline", "blocked"];
const SORTS: Sort[] = ["name", "speed", "total", "ip"];
const value = (e: Event) => (e.target as HTMLInputElement).value;
const ipNumber = (ip: string) => ip.split(".").reduce((n, part) => n * 256 + (Number(part) || 0), 0);

export class WoowGlinetClients extends LitElement {
  @property({ attribute: false }) router!: Router;
  @property({ attribute: false }) t!: Translate;
  @property({ attribute: false }) api!: Api;
  @property({ attribute: false }) now = 0;

  @state() private query = "";
  @state() private filter: Filter = "all";
  @state() private sort: Sort = "name"; // stable: sorting by live speed moves cards under the pointer every few seconds
  @state() private open: string | null = null;
  @state() private history: Sample[] = [];
  @state() private busy: string | null = null;
  // fixed-IP dialog
  @state() private fixing: Client | null = null;
  @state() private fixIp = "";
  @state() private fixName = "";
  @state() private fixError = "";
  @state() private fixBusy = false;

  static styles = [
    shared,
    css`
      .bar {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        align-items: center;
        margin-bottom: 12px;
      }
      .bar input[type="search"] {
        flex: 1 1 220px;
      }
      .filters button {
        border-radius: 14px;
        padding: 2px 10px;
        font-size: 0.85em;
      }
      .list {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
        gap: 12px;
      }
      .client {
        border: 1px solid var(--divider-color, #e0e0e0);
        border-radius: 10px;
        padding: 10px 12px;
        display: grid;
        grid-template-columns: minmax(0, 1fr); /* the column must not grow to a long unbroken name */
        min-width: 0;
        content-visibility: auto; /* a site with hundreds of devices: skip layout and paint of cards off screen */
        contain-intrinsic-size: auto 190px;
        gap: 6px;
        align-content: start;
        background: var(--card-background-color, #fff);
      }
      .client.off .name {
        color: var(--secondary-text-color);
      }
      .name {
        font-weight: 500;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      .stats {
        font-variant-numeric: tabular-nums;
        gap: 4px 14px;
      }
      .actions button {
        font-size: 0.85em;
        padding: 3px 9px;
      }
      .detail {
        border-top: 1px dashed var(--divider-color, #e0e0e0);
        padding-top: 8px;
        display: grid;
        gap: 6px;
      }
    `,
  ];

  updated(changed: Map<string, unknown>): void {
    if (changed.has("fixing") && this.fixing) {
      (this.renderRoot.querySelector(".dialog input") as HTMLInputElement | null)?.focus();
    }
  }

  willUpdate(changed: Map<string, unknown>): void {
    // While a device's details are open, its live speed keeps drawing the chart.
    if (changed.has("router") && this.open) {
      const c = this.router.clients.find((x) => x.mac === this.open);
      const last = this.history[this.history.length - 1];
      const t = Date.now() / 1000;
      if (c && c.online && (!last || t - last[0] >= 2)) this.history = [...this.history, [t, c.rx, c.tx] as Sample].slice(-360);
    }
  }

  private async toggleDetails(c: Client): Promise<void> {
    if (this.open === c.mac) {
      this.open = null;
      return;
    }
    this.open = c.mac;
    this.history = [];
    try {
      const series = await this.api.clientHistory(this.router.entry_id, c.mac);
      if (this.open === c.mac) this.history = series;
    } catch {
      // the chart just stays empty
    }
  }

  private visible(): Client[] {
    const q = this.query.trim().toLowerCase();
    const rows = this.router.clients.filter((c) => {
      if (this.filter === "online" && !c.online) return false;
      if (this.filter === "offline" && c.online) return false;
      if (this.filter === "blocked" && !c.blocked) return false;
      return !q || [c.name, c.alias, c.ip, c.mac].some((s) => s.toLowerCase().includes(q));
    });
    const by: Record<Sort, (a: Client, b: Client) => number> = {
      speed: (a, b) => b.rx + b.tx - (a.rx + a.tx) || Number(b.online) - Number(a.online) || clientName(a).localeCompare(clientName(b)),
      total: (a, b) => b.total_rx + b.total_tx - (a.total_rx + a.total_tx),
      name: (a, b) => clientName(a).localeCompare(clientName(b)),
      ip: (a, b) => ipNumber(a.ip) - ipNumber(b.ip),
    };
    return rows.sort(by[this.sort]);
  }

  private count(filter: Filter): number {
    const cs = this.router.clients;
    if (filter === "online") return cs.filter((c) => c.online).length;
    if (filter === "offline") return cs.filter((c) => !c.online).length;
    if (filter === "blocked") return cs.filter((c) => c.blocked).length;
    return cs.length;
  }

  // ---- actions ------------------------------------------------------------------------
  private async setBlocked(c: Client, blocked: boolean): Promise<void> {
    const t = this.t;
    this.busy = c.mac;
    try {
      await this.api.block(this.router.entry_id, c.mac, blocked);
      notify(this, t(blocked ? "blocked_toast" : "unblocked_toast", { name: clientName(c) }));
    } catch (err) {
      notify(this, explain(err, t), false);
    } finally {
      this.busy = null;
    }
  }

  private block(c: Client): void {
    const t = this.t;
    askConfirm(this, {
      title: t("block_title", { name: clientName(c) }),
      text: t("block_text"),
      action: t("act_block"),
      danger: true,
      run: () => this.setBlocked(c, true),
    });
  }

  private forget(c: Client): void {
    const t = this.t;
    askConfirm(this, {
      title: t("forget_title", { name: clientName(c) }),
      text: t("forget_text"),
      action: t("act_forget"),
      danger: true,
      run: async () => {
        try {
          await this.api.forget(this.router.entry_id, c.mac);
        } catch (err) {
          notify(this, explain(err, t), false);
        }
      },
    });
  }

  private forgetAll(): void {
    const t = this.t;
    const offline = this.router.clients.filter((c) => !c.online);
    askConfirm(this, {
      title: t("forget_all_title", { n: offline.length }),
      text: t("forget_all_text"),
      action: t("act_forget"),
      danger: true,
      run: async () => {
        let done = 0;
        for (const c of offline) {
          try {
            await this.api.forget(this.router.entry_id, c.mac);
            done += 1;
          } catch (err) {
            notify(this, explain(err, t), false);
            break;
          }
        }
        if (done) notify(this, t("forgot_n", { n: done }));
      },
    });
  }

  private startFix(c: Client): void {
    this.fixing = c;
    this.fixIp = c.ip;
    this.fixName = clientName(c) === c.mac ? "" : clientName(c);
    this.fixError = "";
  }

  private async confirmFix(): Promise<void> {
    const c = this.fixing;
    if (!c || this.fixBusy) return;
    this.fixBusy = true;
    this.fixError = "";
    try {
      await this.api.addStaticIp(this.router.entry_id, c.mac, this.fixIp.trim(), this.fixName.trim());
      notify(this, this.t("static_saved", { ip: this.fixIp.trim() }));
      this.fixing = null;
    } catch (err) {
      this.fixError = explain(err, this.t);
    } finally {
      this.fixBusy = false;
    }
  }

  // ---- rendering ------------------------------------------------------------------------
  private renderClient(c: Client) {
    const t = this.t;
    const busy = this.busy === c.mac;
    const expanded = this.open === c.mac;
    return html`<div class="client ${c.online ? "" : "off"}">
      <div class="row" style="flex-wrap:nowrap">
        <span class="dot ${c.blocked ? "bad" : c.online ? "on" : ""}" title=${c.online ? "" : t("offline")}></span>
        <span class="name grow" title=${clientName(c)}>${c.name || c.alias || t("unnamed")}</span>
        ${c.iface ? html`<span class="chip">${ifaceLabel(c.iface, t)}</span>` : nothing}
      </div>
      <div class="row">
        ${c.blocked ? html`<span class="chip bad">${t("chip_blocked")}</span>` : nothing}
        ${c.static_ip ? html`<span class="chip info">${t("chip_static", { ip: c.static_ip })}</span>` : nothing}
        ${c.limit_rx || c.limit_tx ? html`<span class="chip warn">${t("chip_limit")}</span>` : nothing}
      </div>
      <div class="muted"><span class="mono">${c.ip || "—"}</span> · <span class="mono">${c.mac}</span></div>
      <div class="row stats">
        ${c.online
          ? html`<span class="rx">↓ ${formatRate(c.rx)}</span><span class="tx">↑ ${formatRate(c.tx)}</span>
              ${c.since ? html`<span class="muted">${t("online_for", { x: ago(c.since, t).replace(/\s*(ago|前)$/, "") })}</span>` : nothing}`
          : html`<span class="muted">${t("offline")}</span>`}
      </div>
      <div class="muted">${t("total_line", { rx: formatBytes(c.total_rx), tx: formatBytes(c.total_tx) })}</div>
      <div class="row actions">
        ${c.blocked
          ? html`<button ?disabled=${busy} @click=${() => this.setBlocked(c, false)}>${t("act_unblock")}</button>`
          : html`<button class="danger" ?disabled=${busy} @click=${() => this.block(c)}>${t("act_block")}</button>`}
        <button ?disabled=${!!c.static_ip} title=${c.static_ip ? t("already_static", { ip: c.static_ip }) : ""} @click=${() => this.startFix(c)}>${t("act_static")}</button>
        ${c.online ? nothing : html`<button class="danger" @click=${() => this.forget(c)}>${t("act_forget")}</button>`}
        <span class="grow"></span>
        <button class="link" @click=${() => this.toggleDetails(c)}>${t("act_details")} ${expanded ? "▴" : "▾"}</button>
      </div>
      ${expanded
        ? html`<div class="detail">
            <div class="row"><span class="muted">${t("history_title")}</span><span class="grow"></span>
              <button class="link" @click=${() => { copyText(c.mac); notify(this, t("copied")); }}>${t("act_copy_mac")}</button></div>
            <woow-glinet-chart .samples=${this.history} .t=${t} .height=${110}></woow-glinet-chart>
          </div>`
        : nothing}
    </div>`;
  }

  private renderFixDialog() {
    const c = this.fixing;
    if (!c) return nothing;
    const t = this.t;
    return html`<div class="scrim" @click=${(e: Event) => e.target === e.currentTarget && (this.fixing = null)}
        @keydown=${(e: KeyboardEvent) => e.key === "Escape" && (this.fixing = null)}>
      <div class="dialog" role="dialog" aria-modal="true" aria-label=${t("static_title", { name: clientName(c) })}>
        <h2>${t("static_title", { name: clientName(c) })}</h2>
        <div class="muted">${t("static_hint")}</div>
        <div class="mono muted">${c.mac}</div>
        <label>${t("ip_address")}
          <input class="mono" .value=${this.fixIp} @input=${(e: Event) => (this.fixIp = value(e))} @keydown=${(e: KeyboardEvent) => e.key === "Enter" && this.confirmFix()} />
        </label>
        <label>${t("device_name")}
          <input .value=${this.fixName} @input=${(e: Event) => (this.fixName = value(e))} @keydown=${(e: KeyboardEvent) => e.key === "Enter" && this.confirmFix()} />
        </label>
        ${this.fixError ? html`<div class="error">${this.fixError}</div>` : nothing}
        <div class="row">
          <span class="grow"></span>
          <button @click=${() => (this.fixing = null)}>${t("cancel")}</button>
          <button class="primary" ?disabled=${this.fixBusy || !this.fixIp.trim() || !this.fixName.trim()} @click=${() => this.confirmFix()}>${t("add")}</button>
        </div>
      </div>
    </div>`;
  }

  render() {
    const t = this.t;
    const rows = this.visible();
    const offline = this.count("offline");
    return html`<div class="card">
        <div class="bar">
          <input type="search" .value=${this.query} placeholder=${t("search_ph")} aria-label=${t("search_ph")} @input=${(e: Event) => (this.query = value(e))} />
          <select @change=${(e: Event) => (this.sort = value(e) as Sort)} aria-label=${t("sort_label")}>
            ${SORTS.map((s) => html`<option value=${s} ?selected=${this.sort === s}>${t(`sort_${s}` as "sort_speed")}</option>`)}
          </select>
        </div>
        <div class="bar">
          <div class="row filters">
            ${FILTERS.map(
              (f) => html`<button class=${this.filter === f ? "on" : ""} @click=${() => (this.filter = f)}>${t(`f_${f}` as "f_all")} ${this.count(f)}</button>`,
            )}
          </div>
          <span class="grow"></span>
          ${offline ? html`<button class="danger" @click=${() => this.forgetAll()}>${t("forget_all", { n: offline })}</button>` : nothing}
        </div>
        ${rows.length === 0
          ? html`<div class="empty">${this.router.clients.length ? t("clients_empty") : t("clients_none")}</div>`
          : html`<div class="list">${repeat(rows, (c) => c.mac, (c) => this.renderClient(c))}</div>`}
      </div>
      ${this.renderFixDialog()}`;
  }
}

define("woow-glinet-clients", WoowGlinetClients);
