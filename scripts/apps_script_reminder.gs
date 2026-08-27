/**
 * Tipovačka PL — deadline reminder, jako Google Apps Script.
 *
 * Běží přímo pod záložním Gmail účtem (ten, co má přístup omezený jen
 * na tuhle tipovačku) — obchází nutnost jakéhokoli API klíče pro Gmail
 * i síťová omezení cloudového sandboxu, kde běžela Claude rutina.
 *
 * Nastavení (jednorázově, v prohlížeči, přihlášený jako záložní účet):
 *   1. https://script.google.com/ → Nový projekt.
 *   2. Smaž výchozí obsah, vlož celý tenhle soubor.
 *   3. Spusť funkci `setupTrigger` (rozbalovací nabídka nahoře → vyber
 *      "setupTrigger" → Spustit). Google se poprvé zeptá na oprávnění
 *      (odesílat e-maily, přistupovat k internetu) — odsouhlas je (žádáš
 *      je sám sobě, ne mně).
 *   4. Hotovo — od teď se `checkAndSendReminder` spouští sama každé 4 hodiny.
 *      Průběh/chyby uvidíš v Apps Script → Spuštění (Executions).
 */

const SUPABASE_URL = "https://zftqaeorhqdbbxeifaqf.supabase.co";
const SUPABASE_API_KEY = "sb_publishable_PtyVgzUa-lYR38rgDC2GOA_1x41H-rV";
const RECIPIENTS = [
  "petr@polakzceska.cz",
  "chajda69@gmail.com",
  "Nespervojtech@seznam.cz",
  "Alexandr.pola@gmail.com",
];
const APP_URL = "https://tipovacka-pl-2ijcvjbfsw3acptvkjbzi9.streamlit.app/tipy";
const REMINDER_HOURS_BEFORE = 12;

function supabaseGet(path, params) {
  const qs = Object.keys(params)
    .map((k) => encodeURIComponent(k) + "=" + encodeURIComponent(params[k]))
    .join("&");
  const res = UrlFetchApp.fetch(SUPABASE_URL + "/rest/v1/" + path + "?" + qs, {
    headers: { apikey: SUPABASE_API_KEY, Authorization: "Bearer " + SUPABASE_API_KEY },
    muteHttpExceptions: true,
  });
  if (res.getResponseCode() !== 200) {
    throw new Error("Supabase GET " + path + " selhalo: " + res.getResponseCode() + " " + res.getContentText());
  }
  return JSON.parse(res.getContentText());
}

function supabasePatch(path, params, body) {
  const qs = Object.keys(params)
    .map((k) => encodeURIComponent(k) + "=" + encodeURIComponent(params[k]))
    .join("&");
  const res = UrlFetchApp.fetch(SUPABASE_URL + "/rest/v1/" + path + "?" + qs, {
    method: "patch",
    headers: {
      apikey: SUPABASE_API_KEY,
      Authorization: "Bearer " + SUPABASE_API_KEY,
      "Content-Type": "application/json",
      Prefer: "return=representation",
    },
    payload: JSON.stringify(body),
    muteHttpExceptions: true,
  });
  if (res.getResponseCode() >= 300) {
    throw new Error("Supabase PATCH " + path + " selhalo: " + res.getResponseCode() + " " + res.getContentText());
  }
  return JSON.parse(res.getContentText());
}

function checkAndSendReminder() {
  const unfinished = supabaseGet("fixtures", {
    select: "gameweek_id,kickoff_at",
    is_finished: "eq.false",
    order: "gameweek_id.asc,kickoff_at.asc.nullslast",
  });
  if (!unfinished.length) return;

  const gwId = unfinished[0].gameweek_id;
  const kickoffs = unfinished
    .filter((r) => r.gameweek_id === gwId && r.kickoff_at)
    .map((r) => new Date(r.kickoff_at));
  if (!kickoffs.length) return;

  const kickoff = new Date(Math.min.apply(null, kickoffs));

  const gwRows = supabaseGet("gameweeks", { select: "number,reminder_sent_at", id: "eq." + gwId });
  if (!gwRows.length) return;
  const gw = gwRows[0];
  if (gw.reminder_sent_at) return;

  const now = new Date();
  const windowStart = new Date(kickoff.getTime() - REMINDER_HOURS_BEFORE * 3600 * 1000);
  if (!(now >= windowStart && now < kickoff)) return;

  const kickoffPrague = Utilities.formatDate(kickoff, "Europe/Prague", "d.M. HH:mm");

  const subject = "⏰ Tipovačka PL — Kolo " + gw.number + " začíná za 12 hodin!";
  const body =
    "Ahoj,\n\nprvní zápas Kola " +
    gw.number +
    " Premier League tipovačky začíná " +
    kickoffPrague +
    " — tipy a nominace střelců se pak hodinu před výkopem zamknou.\n\nZkontrolujte/zadejte svoje tipy: " +
    APP_URL +
    "\n\nHodně štěstí!\n🏆⚽ Tipovačka PL";

  GmailApp.sendEmail(RECIPIENTS.join(","), subject, body);

  supabasePatch("gameweeks", { number: "eq." + gw.number }, { reminder_sent_at: new Date().toISOString() });
}

function setupTrigger() {
  ScriptApp.getProjectTriggers().forEach((t) => {
    if (t.getHandlerFunction() === "checkAndSendReminder") ScriptApp.deleteTrigger(t);
  });
  ScriptApp.newTrigger("checkAndSendReminder").timeBased().everyHours(4).create();
}
