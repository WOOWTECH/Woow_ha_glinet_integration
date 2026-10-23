// WOOW GL.iNet sidebar panel. Holds the state; the tabs render it.
// Data: one snapshot, then a live feed (woow_glinet/subscribe): router updates, fast traffic samples, activity.

import { LitElement, css, html, nothing } from "lit";
import { property, state } from "lit/decorators.js";

import { Activity, Api, FeedEvent, HomeAssistant, Router, Sample, define, errorText } from "./api";
import { Key, Translate, makeTranslate } from "./i18n";
import { shared } from "./styles";
import { ConfirmRequest } from "./ui";
import "./views/access";
import "./views/activity";
import "./views/clients";
import "./views/overview";
import "./views/wifi";

type Tab = "overview" | "clients" | "wifi" | "access" | "activity";
const ACTIVITY_KEEP = 300;
const WAN_KEEP = 1500;
const RETRY_MS = 5000; // try again this soon after a failed (re)connect
const STALE_MS = 70000; // no event for this long: the feed is gone (Home Assistant restarted, a proxy dropped it)
const MENU = "M3,6H21V8H3V6M3,11H21V13H3V11M3,16H21V18H3V16Z";

export class WoowGlinetPanel extends LitElement {
  @property({ attribute: false }) narrow = false;
  @property({ attribute: false }) route?: unknown;
  @property({ attribute: false }) panel?: unknown;

  @state() private tab: Tab = "overview";
  @state() private routers: Record<string, Router> = {};
  @state() private wan: Record<string, Sample[]> = {};
  @state() private selected = "";
  @state() private activity: Activity[] = [];
  @state() private loaded = false;
  @state() private error = "";
  @state() private now = Date.now();
  @state() private toast: { text: string; ok: boolean } | null = null;
  @state() private confirmReq: ConfirmRequest | null = null;
  @state() private confirmBusy = false;

  private _hass?: HomeAssistant;
  private t: Translate = makeTranslate("en");
  private readonly api = new Api(() => this._hass as HomeAssistant);
  private unsubscribe?: () => Promise<void>;
  private connecting = false;
  private ticker?: number;
  private toastTimer?: number;
  private watchdog?: number;
  private retryTimer?: number;
  private lastEvent = Date.now();
  private readonly onReady = () => void this.resync();
  private readonly onKey = (e: KeyboardEvent) => {
    if (e.key === "Escape" && this.confirmReq && !this.confirmBusy) this.confirmReq = null;
  };

  static styles = [
    shared,
    css`
      :host {
        min-height: 100vh;
        background: var(--primary-background-color);
      }
      .toolbar {
        display: flex;
        align-items: center;
        gap: 8px;
        height: 56px;
        padding: 0 16px;
        background: var(--app-header-background-color, var(--primary-color));
        color: var(--app-header-text-color, var(--text-primary-color, #fff));
        font-size: 20px;
      }
      .toolbar button {
        border: none;
        background: none;
        color: inherit;
        padding: 8px;
        line-height: 0;
      }
      .tabs {
        display: flex;
        gap: 4px;
        padding: 0 12px;
        background: var(--app-header-background-color, var(--primary-color));
        overflow-x: auto;
      }
      .tab {
        border: none;
        border-bottom: 3px solid transparent;
        border-radius: 0;
        background: none;
        color: var(--app-header-text-color, var(--text-primary-color, #fff));
        opacity: 0.85;
        padding: 10px 14px;
        white-space: nowrap;
      }
      .tab.active {
        opacity: 1;
        border-bottom-color: var(--app-header-text-color, var(--text-primary-color, #fff));
      }
      .content {
        max-width: 1200px;
        margin: 0 auto;
        padding: 16px;
      }
      .count {
        margin-left: 6px;
        font-size: 0.8em;
        opacity: 0.85;
      }
      .picker {
        margin-bottom: 12px;
      }
      .toast {
        position: fixed;
        left: 50%;
        bottom: 24px;
        transform: translateX(-50%);
        z-index: 20;
        max-width: min(520px, calc(100vw - 32px));
        padding: 10px 16px;
        border-radius: 10px;
        background: var(--primary-text-color);
        color: var(--card-background-color, #fff);
        box-shadow: 0 2px 10px rgba(0, 0, 0, 0.35);
        font-size: 0.95em;
      }
      .toast.bad {
        background: var(--error-color, #db4437);
        color: #fff;
      }
    `,
  ];

  set hass(hass: HomeAssistant) {
    const first = !this._hass;
    this._hass = hass;
    if (first) {
      // after Home Assistant's socket reconnects (it restarted, the network dropped) fetch everything again
      hass.connection.addEventListener?.("ready", this.onReady);
      this.t = makeTranslate(hass.locale?.language ?? hass.language ?? "en");
      if (this.isConnected) void this.connect();
      this.requestUpdate();
    }
  }

  get hass(): HomeAssistant {
    return this._hass as HomeAssistant;
  }

  connectedCallback(): void {
    super.connectedCallback();
    if (this._hass && !this.unsubscribe) void this.connect();
    this.ticker = window.setInterval(() => (this.now = Date.now()), 5000);
    this.watchdog = window.setInterval(() => this.watch(), 15000);
    window.addEventListener("keydown", this.onKey);
  }

  disconnectedCallback(): void {
    super.disconnectedCallback();
    window.clearInterval(this.ticker);
    window.clearInterval(this.watchdog);
    window.clearTimeout(this.toastTimer);
    window.clearTimeout(this.retryTimer);
    window.removeEventListener("keydown", this.onKey);
    this._hass?.connection.removeEventListener?.("ready", this.onReady);
    void this.dropSubscription();
  }

  updated(changed: Map<string, unknown>): void {
    if (changed.has("confirmReq") && this.confirmReq) {
      // a destructive question starts on "Cancel", so Enter cannot confirm it by accident
      const selector = this.confirmReq.danger ? ".dialog button:not(.primary)" : ".dialog button.primary";
      (this.renderRoot.querySelector(selector) as HTMLButtonElement | null)?.focus();
    }
  }

  private async dropSubscription(): Promise<void> {
    const stop = this.unsubscribe;
    this.unsubscribe = undefined;
    try {
      await stop?.();
    } catch {
      // the socket may be gone already
    }
  }

  private async resync(): Promise<void> {
    if (this.connecting) return;
    await this.dropSubscription();
    await this.connect();
  }

  private watch(): void {
    if (this._hass && !this.connecting && Date.now() - this.lastEvent > STALE_MS) void this.resync();
  }

  private async connect(): Promise<void> {
    if (this.connecting) return;
    this.connecting = true;
    window.clearTimeout(this.retryTimer);
    await this.dropSubscription();
    try {
      // Subscribe first: events that race the snapshot only replace what it holds, so nothing is lost.
      this.unsubscribe = await this.api.subscribe((event) => this.onEvent(event));
      const snap = await this.api.snapshot();
      this.routers = Object.fromEntries(snap.routers.map((r) => [r.entry_id, r]));
      this.wan = Object.fromEntries(snap.routers.map((r) => [r.entry_id, r.history?.wan ?? []]));
      this.activity = snap.activity;
      this.loaded = true;
      this.error = "";
      this.lastEvent = Date.now();
    } catch (err) {
      // e.g. Home Assistant is still starting and does not know our commands yet: keep trying
      this.error = errorText(err);
      this.retryTimer = window.setTimeout(() => void this.connect(), RETRY_MS);
    } finally {
      this.connecting = false;
    }
  }

  private onEvent(event: FeedEvent): void {
    this.lastEvent = Date.now();
    switch (event.kind) {
      case "router": {
        const id = event.router.entry_id;
        this.routers = { ...this.routers, [id]: event.router };
        if (!(id in this.wan)) this.wan = { ...this.wan, [id]: [] };
        break;
      }
      case "router_removed": {
        const { [event.entry_id]: _gone, ...rest } = this.routers;
        this.routers = rest;
        break;
      }
      case "live": {
        const router = this.routers[event.entry_id];
        if (!router) break;
        this.routers = {
          ...this.routers,
          [event.entry_id]: { ...router, available: true, clients: event.clients, wan: { ...router.wan, rx: event.wan.rx, tx: event.wan.tx } },
        };
        const series = [...(this.wan[event.entry_id] ?? []), [event.t, event.wan.rx, event.wan.tx] as Sample];
        this.wan = { ...this.wan, [event.entry_id]: series.slice(-WAN_KEEP) };
        break;
      }
      case "activity":
        this.activity = [...event.entries.reverse(), ...this.activity].slice(0, ACTIVITY_KEEP);
        break;
    }
  }

  private get routerList(): Router[] {
    return Object.values(this.routers).sort((a, b) => a.title.localeCompare(b.title));
  }

  private get current(): Router | undefined {
    return this.routers[this.selected] ?? this.routerList[0];
  }

  private tabsFor(router: Router | undefined): Tab[] {
    if (!router) return ["overview", "clients", "wifi", "access", "activity"];
    // Outside router mode the device list is the whole shared network and blocking / fixed IPs do not apply;
    // a feature this firmware lacks (the router said "Method not found") has no tab either.
    const inRouterMode = router.mode === "router";
    const f = router.features;
    const tabs: Tab[] = ["overview"];
    if (inRouterMode && f.clients) tabs.push("clients");
    if (f.wifi) tabs.push("wifi");
    if (inRouterMode && (f.blocklist || f.static_ip)) tabs.push("access");
    tabs.push("activity");
    return tabs;
  }

  private toggleMenu(): void {
    this.dispatchEvent(new Event("hass-toggle-menu", { bubbles: true, composed: true }));
  }

  private showToast(e: CustomEvent<{ text: string; ok: boolean }>): void {
    this.toast = e.detail;
    window.clearTimeout(this.toastTimer);
    this.toastTimer = window.setTimeout(() => (this.toast = null), e.detail.ok ? 3500 : 7000);
  }

  private async runConfirm(): Promise<void> {
    const request = this.confirmReq;
    if (!request || this.confirmBusy) return;
    this.confirmBusy = true;
    try {
      await request.run();
    } finally {
      this.confirmBusy = false;
      this.confirmReq = null;
    }
  }

  private renderConfirm() {
    const request = this.confirmReq;
    if (!request) return nothing;
    const t = this.t;
    return html`<div class="scrim" @click=${(e: Event) => e.target === e.currentTarget && !this.confirmBusy && (this.confirmReq = null)}>
      <div class="dialog" role="dialog" aria-modal="true" aria-label=${request.title}>
        <h2>${request.title}</h2>
        ${request.text ? html`<div class="muted">${request.text}</div>` : nothing}
        <div class="row">
          <span class="grow"></span>
          <button ?disabled=${this.confirmBusy} @click=${() => (this.confirmReq = null)}>${t("cancel")}</button>
          <button class="primary ${request.danger ? "danger" : ""}" ?disabled=${this.confirmBusy} @click=${() => this.runConfirm()}>${request.action}</button>
        </div>
      </div>
    </div>`;
  }

  private renderTab(router: Router, tab: Tab) {
    const common = { router, t: this.t, api: this.api };
    switch (tab) {
      case "clients":
        return html`<woow-glinet-clients .router=${common.router} .t=${common.t} .api=${common.api} .now=${this.now}></woow-glinet-clients>`;
      case "wifi":
        return html`<woow-glinet-wifi .router=${common.router} .t=${common.t} .api=${common.api}></woow-glinet-wifi>`;
      case "access":
        return html`<woow-glinet-access .router=${common.router} .t=${common.t} .api=${common.api}></woow-glinet-access>`;
      case "activity": {
        const entries = this.activity.filter((a) => !a.entry_id || this.routerList.length < 2 || a.entry_id === router.entry_id);
        return html`<woow-glinet-activity .entries=${entries} .t=${this.t} .now=${this.now} ?multi=${this.routerList.length > 1}></woow-glinet-activity>`;
      }
      default:
        return html`<woow-glinet-overview .router=${common.router} .wan=${this.wan[router.entry_id] ?? []} .t=${common.t} .api=${common.api} .now=${this.now}></woow-glinet-overview>`;
    }
  }

  render() {
    const t = this.t;
    const router = this.current;
    const tabs = this.tabsFor(router);
    const tab = tabs.includes(this.tab) ? this.tab : "overview";
    const online = router ? router.clients.filter((c) => c.online).length : 0;
    const counts: Partial<Record<Tab, number>> = { clients: online, access: router ? router.blocklist.black.length : 0 };
    return html`
      <div class="toolbar">
        ${this.narrow
          ? html`<button @click=${this.toggleMenu} aria-label="menu">
              <svg viewBox="0 0 24 24" width="24" height="24"><path fill="currentColor" d=${MENU}></path></svg>
            </button>`
          : nothing}
        <div>${t("title")}</div>
      </div>
      <div class="tabs">
        ${tabs.map(
          (id) => html`<button class="tab ${tab === id ? "active" : ""}" @click=${() => (this.tab = id)}>
            ${t(`tab_${id}` as Key)}${counts[id] ? html`<span class="count">${counts[id]}</span>` : nothing}
          </button>`,
        )}
      </div>
      <div class="content" @notify=${(e: CustomEvent<{ text: string; ok: boolean }>) => this.showToast(e)}
        @confirm=${(e: CustomEvent<ConfirmRequest>) => (this.confirmReq = e.detail)}>
        ${this.error && this.loaded ? html`<div class="banner bad" role="alert">${t("reconnecting")}</div>` : nothing}
        ${this.error && !this.loaded
          ? html`<div class="card"><div class="error" role="alert">${t("error", { msg: this.error })}</div></div>`
          : !this.loaded
            ? html`<div class="empty">${t("loading")}</div>`
            : !router
              ? html`<div class="empty">${t("no_routers")}</div>`
              : html`${this.routerList.length > 1
                    ? html`<div class="row picker">
                        <span class="muted">${t("router_pick")}</span>
                        <select aria-label=${t("router_pick")} @change=${(e: Event) => (this.selected = (e.target as HTMLSelectElement).value)}>
                          ${this.routerList.map((r) => html`<option value=${r.entry_id} ?selected=${r.entry_id === router.entry_id}>${r.title}</option>`)}
                        </select>
                      </div>`
                    : nothing}
                  ${this.renderTab(router, tab)}`}
      </div>
      ${this.renderConfirm()}
      ${this.toast ? html`<div class="toast ${this.toast.ok ? "" : "bad"}" role="status" aria-live="polite">${this.toast.text}</div>` : nothing}
    `;
  }
}

define("woow-glinet-panel", WoowGlinetPanel);
