/**
 * Calendar helpers.
 *
 * Why this exists: the API returns event dates in two shapes - ISO
 * ("2026-09-05") and human ("05 August 2026"). Both `new Date("05 August
 * 2026T00:00:00")` and FullCalendar's parser choke on the second one, which
 * made seeded events vanish from the grid and printed "Invalid Date" in the UI.
 * Everything entering or leaving the calendar screen goes through
 * `toISODate()` first, so a bad value degrades gracefully instead of
 * exploding the month view.
 */

const MONTHS = [
  "jan", "feb", "mar", "apr", "may", "jun",
  "jul", "aug", "sep", "oct", "nov", "dec",
];

const pad = (value: number) => String(value).padStart(2, "0");

/** Local (timezone-safe) YYYY-MM-DD for a Date object. */
export function dayKey(date: Date): string {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

export function todayISO(): string {
  return dayKey(new Date());
}

/** Parse whatever the API or a form gives us into a strict ISO date string. */
export function toISODate(raw?: string | Date | null): string {
  if (!raw) return "";
  if (raw instanceof Date) return Number.isNaN(raw.getTime()) ? "" : dayKey(raw);

  const value = String(raw).trim();
  if (!value) return "";

  // ISO, optionally with a time component
  const iso = value.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (iso) return `${iso[1]}-${iso[2]}-${iso[3]}`;

  // "05 August 2026" / "05 Aug 2026" / "5 Aug, 2026"
  const human = value.match(/^(\d{1,2})\s*([A-Za-z]{3,9})\.?,?\s*(\d{4})$/);
  if (human) {
    const monthIndex = MONTHS.indexOf(human[2].slice(0, 3).toLowerCase());
    if (monthIndex >= 0) {
      const day = Number(human[1]);
      const year = Number(human[3]);
      const probe = new Date(year, monthIndex, day);
      if (probe.getMonth() === monthIndex && probe.getDate() === day) {
        return `${year}-${pad(monthIndex + 1)}-${pad(day)}`;
      }
    }
  }

  // Anything the platform agrees on ("2026/09/05", "Sep 5, 2026", ...)
  const parsed = new Date(value);
  if (!Number.isNaN(parsed.getTime())) return dayKey(parsed);

  return "";
}

/** "2026-09-05" -> "05 Sep 2026" (falls back to an em dash, never "Invalid Date"). */
export function formatDate(iso?: string | null): string {
  const key = toISODate(iso);
  if (!key) return "—";
  const [y, m, d] = key.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

export function weekdayShort(iso?: string | null): string {
  const key = toISODate(iso);
  if (!key) return "—";
  const [y, m, d] = key.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString("en-IN", { weekday: "short" });
}

/** Whole-day difference between today and an ISO date (negative = in the past). */
export function daysFromToday(iso?: string | null): number | null {
  const key = toISODate(iso);
  if (!key) return null;
  const [y, m, d] = key.split("-").map(Number);
  const target = Date.UTC(y, m - 1, d);
  const now = new Date();
  const today = Date.UTC(now.getFullYear(), now.getMonth(), now.getDate());
  return Math.round((target - today) / 86_400_000);
}

export function relativeDay(iso?: string | null): string {
  const diff = daysFromToday(iso);
  if (diff === null) return "No date";
  if (diff === 0) return "Today";
  if (diff === 1) return "Tomorrow";
  if (diff === -1) return "Yesterday";
  if (diff > 1 && diff <= 6) return `In ${diff} days`;
  if (diff < -1 && diff >= -6) return `${Math.abs(diff)} days ago`;
  if (diff > 6) return `In ${diff} days`;
  return `${Math.abs(diff)} days ago`;
}

export const isUpcoming = (iso?: string | null) => {
  const diff = daysFromToday(iso);
  return diff !== null && diff >= 0;
};

export const isOverdue = (iso?: string | null, status?: string) => {
  if ((status ?? "").toLowerCase() === "completed") return false;
  const diff = daysFromToday(iso);
  return diff !== null && diff < 0;
};

/** "14:30" -> "02:30 PM"; empty or invalid input returns "". */
export function formatTime(time?: string | null): string {
  if (!time) return "";
  const match = String(time).match(/^(\d{1,2}):(\d{2})/);
  if (!match) return String(time);
  const hours = Number(match[1]);
  const suffix = hours >= 12 ? "PM" : "AM";
  const hour12 = hours % 12 === 0 ? 12 : hours % 12;
  return `${pad(hour12)}:${match[2]} ${suffix}`;
}

export function minutesOf(time?: string | null): number | null {
  if (!time) return null;
  const match = String(time).match(/^(\d{1,2}):(\d{2})/);
  if (!match) return null;
  return Number(match[1]) * 60 + Number(match[2]);
}

/** True when two timed events on the same day overlap (missing end = +60 min). */
export function timesOverlap(
  a: { start_time?: string; end_time?: string },
  b: { start_time?: string; end_time?: string }
): boolean {
  const aStart = minutesOf(a.start_time);
  const bStart = minutesOf(b.start_time);
  if (aStart === null || bStart === null) return false;
  const aEnd = minutesOf(a.end_time) ?? aStart + 60;
  const bEnd = minutesOf(b.end_time) ?? bStart + 60;
  return aStart < bEnd && bStart < aEnd;
}

const icsEscape = (value: string) =>
  value
    .replace(/\\/g, "\\\\")
    .replace(/;/g, "\\;")
    .replace(/,/g, "\\,")
    .replace(/\n/g, "\\n");

const icsDate = (iso: string, time?: string, allDay = true) => {
  const key = toISODate(iso);
  if (!key) return "";
  const compact = key.replace(/-/g, "");
  if (allDay || !time) return compact;
  const match = time.match(/^(\d{1,2}):(\d{2})/);
  return match ? `${compact}T${pad(Number(match[1]))}${match[2]}00` : compact;
};

/** RFC 5545: no line may be longer than 75 octets - longer ones are folded
 *  with a CRLF plus a single space. Descriptions get long in real semesters. */
export function foldICSLine(line: string, limit = 74): string {
  if (line.length <= limit + 1) return line;
  const out: string[] = [line.slice(0, limit)];
  let rest = line.slice(limit);
  while (rest.length > limit) {
    out.push(` ${rest.slice(0, limit)}`);
    rest = rest.slice(limit);
  }
  if (rest) out.push(` ${rest}`);
  return out.join("\r\n");
}

/** Whole-day DTEND must be exclusive (the day after), or strict clients show a
 *  zero-length event. */
export function nextDayISO(iso: string): string {
  const key = toISODate(iso);
  if (!key) return "";
  const [y, m, d] = key.split("-").map(Number);
  const date = new Date(y, m - 1, d);
  date.setDate(date.getDate() + 1);
  return dayKey(date);
}

export interface IcsEvent {
  id: string | number;
  title: string;
  date: string;
  person?: string;
  type?: string;
  start_time?: string;
  end_time?: string;
  location?: string;
  description?: string;
  all_day?: boolean;
}

/** Build a downloadable .ics feed client-side - no backend needed. */
export function buildICS(events: IcsEvent[], productId = "hiera-sync"): string {
  const stamp = new Date().toISOString().replace(/[-:]/g, "").replace(/\.\d{3}Z$/, "Z");

  const lines = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//HieraSync AI//Academic Calendar//EN",
    "CALSCALE:GREGORIAN",
    "METHOD:PUBLISH",
  ];

  events.forEach((event) => {
    const allDay = event.all_day !== false && !event.start_time;
    const start = icsDate(event.date, event.start_time, allDay);
    const end = allDay
      ? nextDayISO(event.date)
      : icsDate(event.date, event.end_time || event.start_time, false);

    lines.push(
      "BEGIN:VEVENT",
      `UID:${event.id}@${productId}`,
      `DTSTAMP:${stamp}`,
      allDay ? `DTSTART;VALUE=DATE:${start}` : `DTSTART:${start}`,
      allDay ? `DTEND;VALUE=DATE:${end.replace(/-/g, "")}` : `DTEND:${end}`,
      `SUMMARY:${icsEscape(event.title)}`,
      `DESCRIPTION:${icsEscape(
        [event.description, event.person ? `Owner: ${event.person}` : "", event.type ? `Type: ${event.type}` : ""]
          .filter(Boolean)
          .join(" · ")
      )}`,
      event.location ? `LOCATION:${icsEscape(event.location)}` : ""
    );
    lines.push("END:VEVENT");
  });

  lines.push("END:VCALENDAR");
  return lines
    .filter((line) => line !== "")
    .map((line) => foldICSLine(line))
    .join("\r\n");
}

const csvCell = (value: unknown) => `"${String(value ?? "").replace(/"/g, '""')}"`;

export function buildCSV(
  events: Array<Record<string, any>>,
  columns: Array<{ key: string; label: string }>
): string {
  const header = columns.map((column) => csvCell(column.label)).join(",");
  const rows = events.map((event) =>
    columns.map((column) => csvCell(event[column.key])).join(",")
  );
  return `${[header, ...rows].join("\r\n")}\r\n`;
}

export function downloadFile(filename: string, content: string, mime: string) {
  const blob = new Blob([content], { type: `${mime};charset=utf-8` });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
