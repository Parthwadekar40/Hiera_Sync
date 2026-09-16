/**
 * Calendar utility tests — zero dependencies, native Node TypeScript loading.
 *
 *   npm run test:utils        (needs Node >= 22.18)
 *
 * These helpers used to be the silent source of calendar bugs: dates stored as
 * "05 August 2026" produced "Invalid Date" cells, and a folded ICS file that
 * broke strict importers. The assertions below lock the behaviour in place.
 */
import test from "node:test";
import assert from "node:assert/strict";

import {
  buildCSV,
  buildICS,
  dayKey,
  daysFromToday,
  foldICSLine,
  formatDate,
  formatTime,
  isOverdue,
  isUpcoming,
  minutesOf,
  nextDayISO,
  relativeDay,
  timesOverlap,
  toISODate,
  weekdayShort,
} from "../src/utils/calendar.ts";

const shift = (offset) => {
  const date = new Date();
  date.setDate(date.getDate() + offset);
  return dayKey(date);
};

test("toISODate accepts ISO and human formats, rejects junk", () => {
  assert.equal(toISODate("2026-08-05"), "2026-08-05");
  assert.equal(toISODate("2026-08-05T18:30"), "2026-08-05");
  assert.equal(toISODate("05 August 2026"), "2026-08-05");
  assert.equal(toISODate("5 Aug, 2026"), "2026-08-05");
  assert.equal(toISODate("not a date"), "");
  assert.equal(toISODate(""), "");
  assert.equal(toISODate(undefined), "");
});

test("formatting never renders Invalid Date", () => {
  assert.equal(formatDate("2026-08-05"), "05 Aug 2026");
  assert.equal(formatDate("nope"), "—");
  assert.equal(weekdayShort("2026-08-05"), "Wed");
  assert.equal(formatTime("14:30"), "02:30 PM");
  assert.equal(formatTime("00:05"), "12:05 AM");
  assert.equal(formatTime(""), "");
});

test("relative day labels read like English", () => {
  assert.equal(daysFromToday(shift(3)), 3);
  assert.equal(relativeDay(shift(0)), "Today");
  assert.equal(relativeDay(shift(1)), "Tomorrow");
  assert.equal(relativeDay(shift(-1)), "Yesterday");
  assert.equal(relativeDay(shift(5)), "In 5 days");
  assert.equal(relativeDay(shift(-5)), "5 days ago");
  assert.equal(relativeDay("garbage"), "No date");
});

test("upcoming / overdue respect the status", () => {
  assert.equal(isUpcoming(shift(1)), true);
  assert.equal(isUpcoming(shift(-1)), false);
  assert.equal(isOverdue(shift(-1), "Planned"), true);
  assert.equal(isOverdue(shift(-1), "Completed"), false);
});

test("double-booking detection", () => {
  assert.equal(minutesOf("14:30"), 870);
  assert.deepEqual(timesOverlap({ start_time: "09:00", end_time: "10:00" }, { start_time: "09:30" }), true);
  assert.deepEqual(timesOverlap({ start_time: "09:00", end_time: "10:00" }, { start_time: "10:00" }), false);
  assert.deepEqual(timesOverlap({}, {}), false);
});

test("all-day events end the next day (RFC 5545 is exclusive)", () => {
  assert.equal(nextDayISO("2026-08-31"), "2026-09-01");
  const ics = buildICS([{ id: "e2", title: "All day", date: "2026-08-07" }]);
  assert.match(ics, /DTSTART;VALUE=DATE:20260807/);
  assert.match(ics, /DTEND;VALUE=DATE:20260808/);
});

test("ICS output is escaped, CRLF-terminated and foldable", () => {
  const ics = buildICS(
    [
      {
        id: "e1",
        title: "Review, Part A; final",
        date: "2026-08-05",
        start_time: "10:00",
        end_time: "13:00",
        person: "Dr. Tayal",
        type: "Meeting",
        description: "A description long enough that it has to be folded across two lines for the parser",
        location: "Seminar Hall",
      },
    ],
    "hiera-sync"
  );
  const lines = ics.split("\r\n");

  assert.equal(lines[0], "BEGIN:VCALENDAR");
  assert.equal(lines.at(-1), "END:VCALENDAR");
  assert.ok(!/(?<!\r)\n/.test(ics), "no bare LF");
  assert.ok(lines.some((line) => line === "SUMMARY:Review\\, Part A\\; final"));
  assert.ok(lines.some((line) => line === "DTSTART:20260805T100000"));
  assert.ok(lines.some((line) => line === "DTEND:20260805T130000"));
  assert.ok(lines.some((line) => line === "UID:e1@hiera-sync"));
  assert.match(lines.find((line) => line.startsWith("DTSTAMP")), /^DTSTAMP:\d{8}T\d{6}Z$/);
  assert.ok(lines.every((line) => line.length <= 75), "every line within 75 octets");
  assert.ok(ics.replace(/\r\n /g, "").includes("Owner: Dr. Tayal"));
});

test("foldICSLine only folds what it must", () => {
  assert.equal(foldICSLine("SHORT"), "SHORT");
  const folded = foldICSLine("X".repeat(200));
  assert.ok(folded.split("\r\n").length > 2);
  assert.equal(folded.replace(/\r\n /g, "").length, 200);
});

test("CSV quotes separators and embedded quotes", () => {
  const columns = [
    { key: "title", label: "Title" },
    { key: "date", label: "Date" },
    { key: "person", label: "Owner" },
  ];
  const csv = buildCSV([{ title: "A,B", date: "2026-08-05", person: 'Dr. "T"' }], columns);
  const [header, row] = csv.split("\r\n");
  assert.equal(header, '"Title","Date","Owner"');
  assert.equal(row, '"A,B","2026-08-05","Dr. ""T"""');
});
