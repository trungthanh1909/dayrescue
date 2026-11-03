/* Standalone, hand-authored interaction study. No provider, Python bridge, storage or network calls. */
"use strict";
const $ = (id) => document.getElementById(id);
const sampleDate = "2026-11-03";
const originalActivities = [
  {id: "study", title: "Study Python", start: 540, duration: 90, fixed: false, priority: "High", minimum: null},
  {id: "meeting", title: "Team check-in", start: 630, duration: 30, fixed: true, priority: "High", minimum: null},
  {id: "project", title: "Project time", start: 780, duration: 120, fixed: false, priority: "High", minimum: null},
  {id: "run", title: "Go for a run", start: 900, duration: 60, fixed: false, priority: "Medium", minimum: 30},
  {id: "read", title: "Read a chapter", start: 990, duration: 30, fixed: false, priority: "Low", minimum: null}
];
const revisedActivities = [
  {...originalActivities[0], change: "Kept at the same time"},
  {...originalActivities[1], change: "Kept · Fixed time protected"},
  {...originalActivities[3], start: 675, duration: 30, change: "Moved from 15:00 · Shortened 60 → 30 min", adjusted: true},
  {id: "busy", title: "Family appointment", start: 780, duration: 120, busy: true, change: "New unavoidable commitment"},
  {...originalActivities[2], start: 900, change: "Moved from 13:00 to 15:00", adjusted: true}
];
const days = new Map([[sampleDate, structuredClone(originalActivities)]]);
const weekEntries = [
  [{title: "Attend class", time: "09:00–10:00", fixed: true}],
  [{title: "Study Python", time: "09:00–10:30", fixed: false}, {title: "Team check-in", time: "10:30–11:00", fixed: true}],
  [{title: "Project time", time: "10:00–11:30", fixed: false}],
  [{title: "Attend class", time: "09:00–10:00", fixed: true}, {title: "New appointment", time: "09:30–10:30", fixed: true, conflict: true}],
  [{title: "Team meeting", time: "14:00–15:00", fixed: true}],
  [{title: "Family lunch", time: "12:00–13:30", fixed: true}],
  []
];
const initialWeekEntries = structuredClone(weekEntries);
let currentDate = sampleDate;
let weekDay = 1;
let activityScope = "day";
let dialogReturnFocus;
let toastTimer;
let loadingTimer;
let hasEdits = false;
let activeRoute = "";
const dateFormatter = new Intl.DateTimeFormat("en-GB", {weekday: "long", day: "numeric", month: "long"});
const timeFormatter = new Intl.DateTimeFormat("en-GB", {hour: "2-digit", minute: "2-digit", hourCycle: "h23"});
const clock = (minutes) => timeFormatter.format(new Date(2026, 10, 3, Math.floor(minutes / 60), minutes % 60));
const minutes = (value) => { if (!/^\d{2}:\d{2}$/.test(value)) return NaN; const [h, m] = value.split(":").map(Number); return h < 24 && m < 60 ? h * 60 + m : NaN; };
const dateObject = (value) => new Date(`${value}T12:00:00`);
const escapeText = (value) => String(value).replace(/[&<>"']/g, (character) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[character]));
const activityBadge = (activity) => `<span class="badge ${activity.fixed ? "fixed" : "flexible"}">${activity.fixed ? "Fixed" : "Flexible"}</span>`;
function announce(message) {
  clearTimeout(toastTimer); $("announcement").textContent = message; $("announcement").hidden = false;
  toastTimer = setTimeout(() => { $("announcement").hidden = true; }, 6500);
}
function card(activity, comparison = false) {
  const meta = activity.busy ? "" : `<span class="priority ${activity.priority.toLowerCase()}">${activity.priority} priority</span>${activity.minimum ? `<span>Can shorten to ${activity.minimum} min</span>` : ""}`;
  return `<div class="${comparison ? "" : `activity-card ${activity.fixed ? "is-fixed" : ""}`}"><div class="activity-top"><h3>${escapeText(activity.title)}</h3>${activity.busy ? '<span class="badge interruption">Interruption</span>' : activityBadge(activity)}</div><div class="activity-meta"><span>${clock(activity.start)}–${clock(activity.start + activity.duration)}</span><span>${activity.duration} min</span>${meta}</div>${activity.change ? `<p class="change-label">${escapeText(activity.change)}</p>` : ""}</div>`;
}
function renderDay() {
  const activities = days.get(currentDate) || [];
  $("day-date").textContent = dateFormatter.format(dateObject(currentDate));
  $("day-timeline").innerHTML = [...activities].sort((a, b) => a.start - b.start).map((activity) => `<li><time>${clock(activity.start)}</time>${card(activity)}</li>`).join("");
  $("day-empty").hidden = activities.length !== 0;
  $("day-end").hidden = activities.length === 0;
  $("day-horizon").textContent = currentDate === sampleDate ? "Day window 09:00–17:00 · Demo current time 08:45" : "Date navigation concept · Activities live in this tab only";
}
function getEvent() {
  return {name: $("event-name").value.trim(), start: minutes($("event-start").value), end: minutes($("event-end").value), unavoidable: $("event-unavoidable").checked};
}
function eventIsSample() { const event = getEvent(); return event.name === "Family appointment" && event.start === 780 && event.end === 900 && event.unavoidable; }
function dayIsSample() { return JSON.stringify(days.get(sampleDate)) === JSON.stringify(originalActivities); }
function showFeedback(id, message) { $(id).textContent = message; $(id).hidden = !message; }
function updateOverlap() {
  const event = getEvent();
  const validTime = Number.isFinite(event.start) && Number.isFinite(event.end) && event.end > event.start;
  $("event-preview-name").textContent = event.name || "Your interruption";
  $("event-preview-time").textContent = validTime ? `${clock(event.start)}–${clock(event.end)}` : "Choose a start and a later end time";
  $("optional-event-note").hidden = event.unavoidable;
  const overlaps = (days.get(sampleDate) || []).filter((activity) => validTime && event.start < activity.start + activity.duration && activity.start < event.end);
  $("overlap-feedback").innerHTML = !validTime ? '<div class="overlap-item"><p>Add valid times to preview overlaps.</p></div>' : overlaps.length ? overlaps.map((activity) => `<div class="overlap-item"><h3>${activity.fixed ? "Fixed commitment conflict" : "Overlaps a flexible activity"}</h3><p>${escapeText(activity.title)} · ${clock(activity.start)}–${clock(activity.start + activity.duration)}</p><p class="helper">${activity.fixed ? "This activity cannot move. Change the interruption or your fixed commitment before seeking a plan." : "This activity can move. You’ll review any change in the proposed day."}</p></div>`).join("") : '<div class="overlap-item"><h3>No activity overlaps detected</h3><p class="helper">This alone does not establish full feasibility.</p></div>';
  renderResult();
}
function renderResult() {
  const matches = currentDate === sampleDate && dayIsSample() && eventIsSample();
  $("stale-result").hidden = matches; $("result-content").hidden = !matches;
  $("before-timeline").innerHTML = originalActivities.map((activity) => `<li>${card(activity, true)}</li>`).join("");
  $("after-timeline").innerHTML = revisedActivities.map((activity) => `<li class="${activity.busy ? "busy" : activity.adjusted ? "changed" : ""}">${card(activity, true)}</li>`).join("");
}
function renderWeek() {
  const dates = Array.from({length: 7}, (_, index) => new Date(2026, 10, index + 2, 12));
  const weekdayFormatter = new Intl.DateTimeFormat("en-GB", {weekday: "short"});
  const dayFormatter = new Intl.DateTimeFormat("en-GB", {day: "numeric"});
  $("week-grid").innerHTML = weekEntries.map((entries, index) => `<button class="week-day" data-week-day="${index}" aria-pressed="${index === weekDay}" aria-label="${escapeText(dateFormatter.format(dates[index]))}${index === 3 ? ", sample conflict" : ""}"><span class="weekday">${weekdayFormatter.format(dates[index])}</span><span class="day-number">${dayFormatter.format(dates[index])}</span>${entries.map((entry) => `<span class="week-chip ${entry.fixed ? "fixed-chip" : ""}"><small>${escapeText(entry.time)} · ${entry.fixed ? "Fixed" : "Flexible"}</small>${escapeText(entry.title)}</span>`).join("")}${index === 1 ? '<span class="helper">+ 3 more in My day</span>' : ""}${index === 3 ? '<span class="week-conflict">! 1 sample conflict</span>' : ""}${entries.length ? "" : '<span class="helper">Room to plan</span>'}</button>`).join("");
  $("week-selected-heading").textContent = dateFormatter.format(dates[weekDay]);
  const entries = weekDay === 1 ? (days.get(sampleDate) || []).map((activity) => ({title: activity.title, time: `${clock(activity.start)}–${clock(activity.start + activity.duration)}`, fixed: activity.fixed})).concat(weekEntries[1].slice(2)) : weekEntries[weekDay];
  $("week-selected-content").innerHTML = `${weekDay === 3 ? '<p class="feedback">Sample conflict: Attend class and New appointment overlap from 09:30 to 10:00. Both are marked Fixed. One commitment would need to change.</p>' : ""}${entries.map((entry) => `<div class="selected-activity"><div><strong>${escapeText(entry.title)}</strong><p>${escapeText(entry.time)}${entry.draft ? " · Draft preview only" : ""}</p></div><span class="badge ${entry.fixed ? "fixed" : "flexible"}">${entry.fixed ? "Fixed" : "Flexible"}</span></div>`).join("") || '<p class="helper">No commitments in this concept day. Try “Plan an activity” to explore a draft.</p>'}`;
}
function updateURL() {
  const url = new URL(location.href); url.searchParams.set("date", currentDate); url.searchParams.set("weekDay", String(weekDay)); history.replaceState(null, "", url);
}
function readURL() {
  const query = new URLSearchParams(location.search);
  const value = query.get("date");
  if (/^2026-11-0[2-8]$/.test(value || "")) currentDate = value;
  const selected = Number(query.get("weekDay")); if (query.has("weekDay") && Number.isInteger(selected) && selected >= 0 && selected <= 6) weekDay = selected;
}
function route() {
  const target = location.hash.slice(1);
  if (target === "main") { $("main").focus(); return; }
  const name = ["day", "interruption", "rescued", "week"].includes(target) ? target : "day";
  if (name !== activeRoute) { clearTimeout(loadingTimer); $("rescue-button").disabled = false; $("rescue-button").textContent = "Rescue my day"; $("interruption-form").removeAttribute("aria-busy"); showFeedback("rescue-feedback", ""); }
  document.querySelectorAll(".screen").forEach((screen) => { screen.hidden = screen.id !== `screen-${name}`; });
  document.querySelectorAll("[data-nav]").forEach((link) => { if (link.dataset.nav === (name === "interruption" ? "day" : name)) link.setAttribute("aria-current", "page"); else link.removeAttribute("aria-current"); });
  renderDay(); renderResult(); renderWeek();
  const heading = $(name === "day" ? "day-heading" : `${name}-heading`);
  document.title = `${heading.textContent} · DayRescue design prototype`;
  if (activeRoute && activeRoute !== name) { heading.focus({preventScroll: true}); window.scrollTo({top: 0, behavior: "instant"}); }
  activeRoute = name;
}
function changeDate(delta) {
  const next = dateObject(currentDate); next.setDate(next.getDate() + delta);
  if (next < dateObject("2026-11-02") || next > dateObject("2026-11-08")) { announce("This concept covers 2–8 November. Return to Demo today for the rescue example."); return; }
  currentDate = `2026-11-${String(next.getDate()).padStart(2, "0")}`;
  renderDay(); updateURL(); announce(`${dateFormatter.format(next)} selected. Date navigation is a concept.`);
}
function restoreEvent() {
  $("event-name").value = "Family appointment"; $("event-start").value = "13:00"; $("event-end").value = "15:00"; $("event-unavoidable").checked = true;
  ["event-name", "event-start", "event-end"].forEach((id) => { $(id).removeAttribute("aria-invalid"); $(id).removeAttribute("aria-describedby"); });
  $("event-time-error").hidden = true; showFeedback("rescue-feedback", ""); updateOverlap();
}
function resetDemo(confirmEdits = true) {
  if (confirmEdits && hasEdits && !confirm("Reset this demo and discard your tab-only changes?")) return false;
  days.clear(); days.set(sampleDate, structuredClone(originalActivities));
  initialWeekEntries.forEach((entries, index) => { weekEntries[index] = structuredClone(entries); });
  currentDate = sampleDate; weekDay = 1; hasEdits = false; $("activity-form").reset(); showFeedback("week-feedback", ""); restoreEvent(); updateURL(); renderDay(); renderWeek(); renderResult(); return true;
}
function openActivity(scope, trigger) {
  const count = scope === "day" ? (days.get(currentDate) || []).length : weekEntries[weekDay].length;
  if (count >= 8) { announce("This prototype allows up to 8 activities in a day."); return; }
  activityScope = scope; dialogReturnFocus = trigger; $("activity-form").reset(); $("activity-error").hidden = true;
  $("activity-dialog-heading").textContent = scope === "week" ? "Plan an activity" : "Add an activity";
  $("activity-scope").textContent = scope === "week" ? "Future concept: a draft for the selected day. This is not saved or connected to My day." : "Added to this demo tab only. Refreshing clears it. Custom activities have no rescue example.";
  $("activity-dialog").showModal();
}
function closeActivity() { $("activity-dialog").close(); dialogReturnFocus?.focus(); }
$("previous-day").addEventListener("click", () => changeDate(-1));
$("next-day").addEventListener("click", () => changeDate(1));
$("today-button").addEventListener("click", () => { currentDate = sampleDate; renderDay(); updateURL(); announce("Sample Tuesday selected."); });
$("add-activity").addEventListener("click", (event) => openActivity("day", event.currentTarget));
$("empty-add").addEventListener("click", (event) => openActivity("day", event.currentTarget));
$("week-add").addEventListener("click", (event) => openActivity("week", event.currentTarget));
$("close-dialog").addEventListener("click", closeActivity); $("cancel-dialog").addEventListener("click", closeActivity);
$("activity-form").addEventListener("submit", (event) => {
  event.preventDefault(); const form = event.currentTarget;
  if (!form.reportValidity()) return;
  const title = $("activity-name").value.trim(), start = minutes($("activity-start").value), duration = Number($("activity-duration").value);
  if (!title || !Number.isFinite(start) || !Number.isInteger(duration) || duration <= 0 || start < 540 || start + duration > 1020) {
    $("activity-error").textContent = "Add a name and a whole-minute duration within the demo day, 09:00–17:00."; $("activity-error").hidden = false; $("activity-name").focus(); return;
  }
  const activity = {id: `demo-${Date.now()}`, title, start, duration, fixed: $("activity-type").value === "fixed", priority: $("activity-priority").value, minimum: null};
  if (activityScope === "day") { const list = days.get(currentDate) || []; list.push(activity); days.set(currentDate, list); renderDay(); updateOverlap(); }
  else { weekEntries[weekDay].push({title, time: `${clock(start)}–${clock(start + duration)}`, fixed: activity.fixed, draft: true}); renderWeek(); }
  hasEdits = true; closeActivity(); announce(activityScope === "day" ? "Activity added to this demo tab. Custom inputs have no prewritten rescue outcome." : "Draft added to the weekly concept. It will not be saved or scheduled.");
});
$("interruption-form").addEventListener("input", () => {
  clearTimeout(loadingTimer); $("rescue-button").disabled = false; $("rescue-button").textContent = "Rescue my day"; $("interruption-form").removeAttribute("aria-busy");
  hasEdits = true; showFeedback("rescue-feedback", ""); updateOverlap();
});
$("interruption-form").addEventListener("submit", (event) => {
  event.preventDefault();
  if (!event.currentTarget.reportValidity()) return;
  const interruption = getEvent();
  const valid = interruption.name && Number.isFinite(interruption.start) && Number.isFinite(interruption.end) && interruption.end > interruption.start;
  ["event-name", "event-start", "event-end"].forEach((id) => { $(id).removeAttribute("aria-invalid"); $(id).removeAttribute("aria-describedby"); });
  $("event-time-error").hidden = valid;
  if (!valid) {
    $("event-time-error").textContent = "Add an event name and an end time later than the start, within the same day.";
    const field = !interruption.name ? $("event-name") : $("event-end"); field.setAttribute("aria-invalid", "true"); field.setAttribute("aria-describedby", "event-time-error"); field.focus(); return;
  }
  const fixedOverlap = (days.get(sampleDate) || []).some((activity) => activity.fixed && interruption.start < activity.start + activity.duration && activity.start < interruption.end);
  if (fixedOverlap) { showFeedback("rescue-feedback", "This interruption overlaps a fixed activity. Change one commitment before seeking a revised plan. No proposal is shown."); return; }
  if (!dayIsSample() || !eventIsSample()) { showFeedback("rescue-feedback", "This prototype only previews the original sample day with Family appointment, 13:00–15:00, marked unavoidable. Use Reset demo to restore it. Custom inputs are not sent anywhere."); return; }
  $("rescue-button").disabled = true; $("rescue-button").textContent = "Opening demo proposal…"; $("interruption-form").setAttribute("aria-busy", "true"); showFeedback("rescue-feedback", "Loading the hand-authored example. No AI request is made.");
  loadingTimer = setTimeout(() => { $("rescue-button").disabled = false; $("rescue-button").textContent = "Rescue my day"; $("interruption-form").removeAttribute("aria-busy"); showFeedback("rescue-feedback", ""); location.hash = "rescued"; }, 650);
});
$("restore-event").addEventListener("click", () => { restoreEvent(); announce("Sample interruption restored."); });
$("reset-demo").addEventListener("click", () => { if (resetDemo()) { location.hash = "day"; announce("Demo reset. No saved data was changed."); } });
$("restore-result").addEventListener("click", () => { if (resetDemo()) { renderResult(); $("rescued-heading").focus(); announce("Sample day and interruption restored."); } });
$("week-grid").addEventListener("click", (event) => { const button = event.target.closest("[data-week-day]"); if (!button) return; weekDay = Number(button.dataset.weekDay); renderWeek(); updateURL(); $("week-grid").querySelector(`[data-week-day="${weekDay}"]`).focus(); showFeedback("week-feedback", ""); });
$("week-interruption").addEventListener("click", () => {
  if (weekDay === 1) { currentDate = sampleDate; updateURL(); location.hash = "interruption"; }
  else showFeedback("week-feedback", "Only Tuesday connects to the sample interruption flow. Other days illustrate future weekly planning; they cannot be rescued here.");
});
document.querySelectorAll('a[href="#interruption"]').forEach((link) => link.addEventListener("click", (event) => {
  if (currentDate !== sampleDate) { event.preventDefault(); announce("The rescue example uses Tuesday, 3 November. Select Demo today first."); }
}));
window.addEventListener("hashchange", route);
window.addEventListener("popstate", () => { readURL(); route(); });
window.addEventListener("beforeunload", (event) => { if (hasEdits || ($("activity-dialog").open && $("activity-name").value.trim())) { event.preventDefault(); event.returnValue = ""; } });
readURL(); updateOverlap(); route();
