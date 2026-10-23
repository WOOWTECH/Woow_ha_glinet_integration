// Small helpers the views share: the confirm / toast events the panel root listens for, and labels.

import { Translate, isKey } from "./i18n";

export interface ConfirmRequest {
  title: string;
  text?: string;
  action: string; // the confirm button's label
  danger?: boolean;
  run: () => Promise<void>;
}

/** Ask the panel root to show a confirm dialog; `run` happens only after the user confirms. */
export function askConfirm(host: HTMLElement, request: ConfirmRequest): void {
  host.dispatchEvent(new CustomEvent<ConfirmRequest>("confirm", { detail: request, bubbles: true, composed: true }));
}

/** A short message at the bottom of the panel. */
export function notify(host: HTMLElement, text: string, ok = true): void {
  host.dispatchEvent(new CustomEvent("notify", { detail: { text, ok }, bubbles: true, composed: true }));
}

export function modeLabel(mode: string, t: Translate): string {
  const key = `mode_${mode}`;
  return isKey(key) ? t(key) : t("mode_other", { mode });
}

/** "wan" -> "WAN port", "tethering" -> "USB tethering"; unknown interface names are shown as they are. */
export function linkLabel(link: string, t: Translate): string {
  if (link === "wan" || link === "wan6") return t("link_wan");
  if (link === "wwan" || link === "wwan6") return t("link_wwan");
  if (link.startsWith("tethering")) return t("link_tethering");
  if (link.startsWith("modem")) return t("link_modem");
  return link;
}

/** "cable" -> "Wired"; the router's other interface names (2.4G, 5G ...) are shown as they are. */
export function ifaceLabel(iface: string, t: Translate): string {
  return iface === "cable" ? t("iface_cable") : iface;
}
