// Access tab: the MAC blocklist and the fixed IP addresses (DHCP reservations).

import { LitElement, css, html, nothing } from "lit";
import { property, state } from "lit/decorators.js";

import { Api, Router, clientName, define } from "../api";
import { Translate, explain } from "../i18n";
import { shared } from "../styles";
import { askConfirm, notify } from "../ui";

const value = (e: Event) => (e.target as HTMLInputElement).value;

export class WoowGlinetAccess extends LitElement {
  @property({ attribute: false }) router!: Router;
  @property({ attribute: false }) t!: Translate;
  @property({ attribute: false }) api!: Api;

  @state() private blockMac = "";
  @state() private blockError = "";
  @state() private busy = false;
  @state() private fixMac = "";
  @state() private fixIp = "";
  @state() private fixName = "";
  @state() private fixError = "";

  static styles = [
    shared,
    css`
      .item {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 6px 12px;
        padding: 8px 0;
        border-top: 1px solid var(--divider-color, #eee);
      }
      .item:first-of-type {
        border-top: none;
      }
      .who {
        flex: 1 1 200px;
        min-width: 0;
      }
      .add {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        margin-top: 12px;
      }
      .add input {
        flex: 1 1 160px;
      }
      details {
        margin-top: 10px;
        font-size: 0.9em;
        color: var(--secondary-text-color);
      }
      summary {
        cursor: pointer;
      }
      details p {
        margin: 6px 0 0;
        line-height: 1.5;
      }
    `,
  ];

  /** What the router knows this MAC as: a device, a fixed-IP entry, or nothing. */
  private nameOf(mac: string): string {
    const up = mac.toUpperCase();
    const client = this.router.clients.find((c) => c.mac.toUpperCase() === up);
    if (client) return clientName(client);
    const bound = this.router.static_binds.find((b) => (b.mac ?? "").toUpperCase() === up);
    return bound?.name || this.t("unknown_device");
  }

  private async setBlocked(mac: string, blocked: boolean): Promise<void> {
    const t = this.t;
    this.busy = true;
    this.blockError = "";
    try {
      await this.api.block(this.router.entry_id, mac, blocked);
      notify(this, t(blocked ? "blocked_toast" : "unblocked_toast", { name: this.nameOf(mac) }));
      if (blocked) this.blockMac = "";
    } catch (err) {
      this.blockError = explain(err, t);
    } finally {
      this.busy = false;
    }
  }

  private block(mac: string): void {
    const t = this.t;
    askConfirm(this, {
      title: t("block_title", { name: this.nameOf(mac) }),
      text: t("block_text"),
      action: t("act_block"),
      danger: true,
      run: () => this.setBlocked(mac, true),
    });
  }

  private pickBlock(mac: string): void {
    this.blockMac = mac;
  }

  private pickFix(mac: string): void {
    const c = this.router.clients.find((x) => x.mac === mac);
    this.fixMac = mac;
    if (c) {
      this.fixIp = c.ip;
      this.fixName = clientName(c) === c.mac ? "" : clientName(c);
    }
  }

  private async addFix(): Promise<void> {
    this.busy = true;
    this.fixError = "";
    try {
      await this.api.addStaticIp(this.router.entry_id, this.fixMac.trim(), this.fixIp.trim(), this.fixName.trim());
      notify(this, this.t("static_saved", { ip: this.fixIp.trim() }));
      this.fixMac = this.fixIp = this.fixName = "";
    } catch (err) {
      this.fixError = explain(err, this.t);
    } finally {
      this.busy = false;
    }
  }

  private renderBlocklist() {
    const t = this.t;
    const list = this.router.blocklist;
    if (list.mode !== "black") {
      return html`<div class="card">
        <h2>${t("allowed_title")}</h2>
        <div class="banner">${t("mode_not_black")}</div>
        ${list.white.length === 0
          ? html`<div class="muted">${t("blocked_empty")}</div>`
          : list.white.map((mac) => html`<div class="item"><div class="who"><b>${this.nameOf(mac)}</b><div class="mono muted">${mac}</div></div></div>`)}
      </div>`;
    }
    const blockable = this.router.clients.filter((c) => !c.blocked);
    return html`<div class="card">
      <h2>${t("blocked_title")}</h2>
      ${list.black.length === 0
        ? html`<div class="muted">${t("blocked_empty")}</div>`
        : list.black.map(
            (mac) => html`<div class="item">
              <span class="dot bad"></span>
              <div class="who"><b>${this.nameOf(mac)}</b><div class="mono muted">${mac}</div></div>
              <button ?disabled=${this.busy} @click=${() => this.setBlocked(mac, false)}>${t("act_unblock")}</button>
            </div>`,
          )}
      <div class="muted" style="margin-top:14px">${t("block_by_mac")}</div>
      <div class="add">
        <select @change=${(e: Event) => this.pickBlock(value(e))} aria-label=${t("pick_client")}>
          <option value="">${t("pick_client")}</option>
          ${blockable.map((c) => html`<option value=${c.mac} ?selected=${c.mac === this.blockMac}>${clientName(c)} · ${c.ip}</option>`)}
        </select>
        <input class="mono" placeholder=${t("mac_ph")} .value=${this.blockMac} @input=${(e: Event) => (this.blockMac = value(e))}
          @keydown=${(e: KeyboardEvent) => e.key === "Enter" && this.blockMac.trim() && this.block(this.blockMac.trim())} />
        <button class="danger" ?disabled=${this.busy || !this.blockMac.trim()} @click=${() => this.block(this.blockMac.trim())}>${t("act_block")}</button>
      </div>
      ${this.blockError ? html`<div class="error" style="margin-top:8px">${this.blockError}</div>` : nothing}
    </div>`;
  }

  private renderStatic() {
    const t = this.t;
    const binds = this.router.static_binds;
    const taken = new Set(binds.map((b) => (b.mac ?? "").toUpperCase()));
    const candidates = this.router.clients.filter((c) => !taken.has(c.mac.toUpperCase()));
    return html`<div class="card">
      <h2>${t("static_list_title")}</h2>
      ${binds.length === 0
        ? html`<div class="muted">${t("static_empty")}</div>`
        : binds.map(
            (b) => html`<div class="item">
              <span class="dot on"></span>
              <div class="who"><b>${b.name || this.nameOf(b.mac)}</b><div class="muted"><span class="mono">${b.ip}</span> · <span class="mono">${b.mac}</span></div></div>
            </div>`,
          )}
      <details>
        <summary>${t("static_remove_why")}</summary>
        <p>${t("static_remove_text")}</p>
      </details>
      <div class="muted" style="margin-top:14px">${t("static_add_title")}</div>
      <div class="add">
        <select @change=${(e: Event) => this.pickFix(value(e))} aria-label=${t("pick_client")}>
          <option value="">${t("pick_client")}</option>
          ${candidates.map((c) => html`<option value=${c.mac} ?selected=${c.mac === this.fixMac}>${clientName(c)} · ${c.ip}</option>`)}
        </select>
        <input class="mono" placeholder=${t("mac_ph")} .value=${this.fixMac} @input=${(e: Event) => (this.fixMac = value(e))} />
        <input class="mono" placeholder=${t("ip_address")} .value=${this.fixIp} @input=${(e: Event) => (this.fixIp = value(e))} />
        <input placeholder=${t("device_name")} .value=${this.fixName} @input=${(e: Event) => (this.fixName = value(e))}
          @keydown=${(e: KeyboardEvent) => e.key === "Enter" && this.addFix()} />
        <button class="primary" ?disabled=${this.busy || !this.fixMac.trim() || !this.fixIp.trim() || !this.fixName.trim()} @click=${() => this.addFix()}>${t("add")}</button>
      </div>
      ${this.fixError ? html`<div class="error" style="margin-top:8px">${this.fixError}</div>` : nothing}
    </div>`;
  }

  render() {
    return html`${this.renderBlocklist()}${this.renderStatic()}`;
  }
}

define("woow-glinet-access", WoowGlinetAccess);
