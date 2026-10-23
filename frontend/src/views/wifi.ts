// Wi-Fi tab: each interface (main and guest, 2.4 and 5 GHz) with an on/off switch, name and password.
// The password is never in the panel's data; "show current password" asks the backend for it.

import { LitElement, css, html, nothing } from "lit";
import { property, state } from "lit/decorators.js";

import { Api, Router, WifiBand, WifiIface, define } from "../api";
import { Translate, explain } from "../i18n";
import { shared } from "../styles";
import { askConfirm, notify } from "../ui";

interface Edit {
  ssid?: string;
  key?: string;
}

const value = (e: Event) => (e.target as HTMLInputElement).value;
const bytes = (s: string) => new TextEncoder().encode(s).length;

export class WoowGlinetWifi extends LitElement {
  @property({ attribute: false }) router!: Router;
  @property({ attribute: false }) t!: Translate;
  @property({ attribute: false }) api!: Api;

  @state() private edits: Record<string, Edit> = {};
  @state() private revealed: Record<string, string> = {};
  @state() private busy: string | null = null;
  @state() private errors: Record<string, string> = {};

  static styles = [
    shared,
    css`
      .ssid {
        font-size: 1.05em;
        font-weight: 500;
      }
      .switch {
        position: relative;
        width: 44px;
        height: 24px;
        border-radius: 12px;
        border: none;
        padding: 0;
        background: var(--disabled-text-color, #bdbdbd);
        flex: none;
      }
      .switch::after {
        content: "";
        position: absolute;
        top: 2px;
        left: 2px;
        width: 20px;
        height: 20px;
        border-radius: 50%;
        background: #fff;
        transition: transform 0.15s;
      }
      .switch.on {
        background: var(--primary-color);
      }
      .switch.on::after {
        transform: translateX(20px);
      }
      .form {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
        gap: 10px 16px;
        margin: 12px 0 8px;
      }
      .form label {
        display: grid;
        gap: 4px;
        font-size: 0.85em;
        color: var(--secondary-text-color);
      }
      .form input {
        font-size: 1.05em;
      }
      .card.busy {
        opacity: 0.65;
        pointer-events: none;
      }
      .form input.bad {
        outline: 2px solid var(--error-color, #db4437);
        outline-offset: -1px;
      }
    `,
  ];

  private bandLabel(band: WifiBand): string {
    return band.band === "2G" ? this.t("band_2g") : band.band === "5G" ? this.t("band_5g") : band.band;
  }

  private edit(name: string): Edit {
    return this.edits[name] ?? {};
  }

  private setEdit(name: string, change: Edit): void {
    this.edits = { ...this.edits, [name]: { ...this.edit(name), ...change } };
  }

  private ssidOf(iface: WifiIface): string {
    return this.edit(iface.name).ssid ?? iface.ssid;
  }

  private problems(iface: WifiIface): { ssid: boolean; key: boolean } {
    const e = this.edit(iface.name);
    return {
      ssid: e.ssid !== undefined && (bytes(e.ssid) < 1 || bytes(e.ssid) > 32),
      key: !!e.key && (e.key.length < 8 || e.key.length > 63),
    };
  }

  private dirty(iface: WifiIface): boolean {
    const e = this.edit(iface.name);
    return (e.ssid !== undefined && e.ssid !== iface.ssid) || !!e.key;
  }

  private async run(name: string, work: () => Promise<void>): Promise<void> {
    this.busy = name;
    this.errors = { ...this.errors, [name]: "" };
    try {
      await work();
    } catch (err) {
      this.errors = { ...this.errors, [name]: explain(err, this.t) };
    } finally {
      this.busy = null;
    }
  }

  private toggle(iface: WifiIface): void {
    const t = this.t;
    const turn = async () =>
      this.run(iface.name, async () => {
        await this.api.setWifi(this.router.entry_id, iface.name, { enabled: !iface.enabled });
        notify(this, t(iface.enabled ? "wifi_off_toast" : "wifi_on_toast", { ssid: iface.ssid }));
      });
    if (iface.enabled && !iface.guest) {
      // switching a main network off disconnects everything on it
      askConfirm(this, { title: t("wifi_confirm_title", { ssid: iface.ssid }), text: t("wifi_warn"), action: t("confirm"), danger: true, run: turn });
    } else {
      void turn();
    }
  }

  private save(iface: WifiIface): void {
    const t = this.t;
    const e = this.edit(iface.name);
    const patch: { ssid?: string; key?: string } = {};
    if (e.ssid !== undefined && e.ssid !== iface.ssid) patch.ssid = e.ssid;
    if (e.key) patch.key = e.key;
    const apply = async () =>
      this.run(iface.name, async () => {
        await this.api.setWifi(this.router.entry_id, iface.name, patch);
        const { [iface.name]: _gone, ...rest } = this.edits;
        this.edits = rest;
        const { [iface.name]: _hidden, ...keys } = this.revealed;
        this.revealed = keys;
        notify(this, t("wifi_saved"));
      });
    if (iface.guest) {
      void apply();
    } else {
      askConfirm(this, { title: t("wifi_confirm_title", { ssid: iface.ssid }), text: t("wifi_warn"), action: t("save"), danger: true, run: apply });
    }
  }

  private async reveal(iface: WifiIface): Promise<void> {
    if (iface.name in this.revealed) {
      const { [iface.name]: _hidden, ...rest } = this.revealed;
      this.revealed = rest;
      return;
    }
    await this.run(iface.name, async () => {
      this.revealed = { ...this.revealed, [iface.name]: await this.api.wifiKey(this.router.entry_id, iface.name) };
    });
  }

  private renderIface(band: WifiBand, iface: WifiIface) {
    const t = this.t;
    const bad = this.problems(iface);
    const busy = this.busy === iface.name;
    const e = this.edit(iface.name);
    return html`<div class="card ${busy ? "busy" : ""}">
      <div class="row">
        <span class="dot ${iface.up ? "on" : ""}" title=${iface.up ? t("on_air") : t("radio_off")}></span>
        <span class="ssid grow">${iface.ssid}</span>
        <span class="chip">${this.bandLabel(band)}</span>
        ${iface.guest ? html`<span class="chip info">${t("guest")}</span>` : nothing}
        ${iface.hidden ? html`<span class="chip">${t("hidden")}</span>` : nothing}
        <button class="switch ${iface.enabled ? "on" : ""}" role="switch" aria-checked=${iface.enabled} aria-label=${t("enabled")}
          ?disabled=${busy} @click=${() => this.toggle(iface)}></button>
      </div>
      <div class="muted">
        ${iface.up ? t("on_air") : t("radio_off")} · ${t("wifi_enc")} ${iface.encryption}
        · ${t("wifi_channel")} ${band.channel && band.channel !== 0 ? band.channel : t("channel_auto")}
        · <span class="mono">${iface.bssid}</span>
      </div>
      <div class="form">
        <label>${t("ssid")}
          <input class=${bad.ssid ? "bad" : ""} .value=${this.ssidOf(iface)} @input=${(ev: Event) => this.setEdit(iface.name, { ssid: value(ev) })} />
        </label>
        <label>${t("password")}
          <input class=${bad.key ? "bad" : ""} type="password" autocomplete="new-password" placeholder=${t("password_ph")} .value=${e.key ?? ""}
            @input=${(ev: Event) => this.setEdit(iface.name, { key: value(ev) })} />
          <span class="row">
            <button class="link" ?disabled=${busy} @click=${() => this.reveal(iface)}>${iface.name in this.revealed ? t("hide") : t("show_password")}</button>
            ${iface.name in this.revealed ? html`<span class="mono">${this.revealed[iface.name]}</span>` : nothing}
          </span>
        </label>
      </div>
      ${this.dirty(iface) && !iface.guest ? html`<div class="banner">${t("wifi_warn")}</div>` : nothing}
      ${this.errors[iface.name] ? html`<div class="error">${this.errors[iface.name]}</div>` : nothing}
      <div class="row">
        <span class="grow"></span>
        ${this.dirty(iface) ? html`<button @click=${() => { const { [iface.name]: _gone, ...rest } = this.edits; this.edits = rest; }}>${t("cancel")}</button>` : nothing}
        <button class="primary" ?disabled=${busy || !this.dirty(iface) || bad.ssid || bad.key} @click=${() => this.save(iface)}>${busy ? t("saving") : t("save")}</button>
      </div>
    </div>`;
  }

  render() {
    const bands = this.router.wifi;
    if (!bands.some((b) => b.ifaces.length)) return html`<div class="card"><div class="empty">${this.t("wifi_empty")}</div></div>`;
    return html`${bands.map((band) => band.ifaces.map((iface) => this.renderIface(band, iface)))}`;
  }
}

define("woow-glinet-wifi", WoowGlinetWifi);
