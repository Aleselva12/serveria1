import assert from "node:assert/strict";
import { test } from "node:test";
import { readFile } from "node:fs/promises";
import ts from "typescript";
const source = await readFile(
  new URL("../src/services/calendarTime.ts", import.meta.url),
  "utf8",
);
const compiled = ts.transpileModule(source, {
  compilerOptions: {
    target: ts.ScriptTarget.ES2022,
    module: ts.ModuleKind.ES2022,
  },
}).outputText;
const time = await import(
  "data:text/javascript;base64," + Buffer.from(compiled).toString("base64")
);
const event = (id, start, end, all_day = false) => ({
  id,
  start,
  end,
  all_day,
  title: id,
});
test("Italian wall time is independent of device timezone and tracks seasonal offsets", () => {
  assert.equal(time.romeISO("2026-01-02T09:00"), "2026-01-02T08:00:00.000Z");
  assert.equal(time.romeISO("2026-07-02T09:00"), "2026-07-02T07:00:00.000Z");
  assert.equal(time.romeLocal("2026-07-02T07:00:00Z"), "2026-07-02T09:00");
});
test("DST skip is rejected and repeated hour selects first occurrence", () => {
  assert.throws(() => time.romeISO("2026-03-29T02:30"), /non esiste/);
  assert.equal(time.romeISO("2026-10-25T02:30"), "2026-10-25T00:30:00.000Z");
  assert.equal(
    Date.parse(time.dayStart("2026-03-30")) -
      Date.parse(time.dayStart("2026-03-29")),
    23 * 3600000,
  );
  assert.equal(
    Date.parse(time.dayStart("2026-10-26")) -
      Date.parse(time.dayStart("2026-10-25")),
    25 * 3600000,
  );
});
test("date navigation crosses year and leap-day boundaries", () => {
  assert.equal(time.shiftMonth("2026-12-31", 1), "2027-01-01");
  assert.equal(time.shiftDay("2028-02-28", 1), "2028-02-29");
});
test("cross-midnight events appear on both days and midnight end is exclusive", () => {
  const events = [
    event("night", "2026-10-02T23:00:00+02:00", "2026-10-03T01:00:00+02:00"),
    event("midnight", "2026-10-02T22:00:00+02:00", "2026-10-03T00:00:00+02:00"),
  ];
  assert.equal(time.eventsOnDay(events, "2026-10-02").length, 2);
  assert.deepEqual(
    time.eventsOnDay(events, "2026-10-03").map((e) => e.id),
    ["night"],
  );
});
test("connected overlap groups share lanes; adjacent independent event uses full width", () => {
  const list = [
    event("a", "2026-10-02T09:00:00+02:00", "2026-10-02T10:00:00+02:00"),
    event("b", "2026-10-02T09:30:00+02:00", "2026-10-02T11:00:00+02:00"),
    event("c", "2026-10-02T10:30:00+02:00", "2026-10-02T12:00:00+02:00"),
    event("d", "2026-10-02T12:00:00+02:00", "2026-10-02T13:00:00+02:00"),
    event(
      "all",
      "2026-10-02T00:00:00+02:00",
      "2026-10-03T00:00:00+02:00",
      true,
    ),
  ];
  const result = time.layoutDay(list, "2026-10-02");
  assert.equal(result.length, 4);
  assert.deepEqual(
    result.map((i) => i.lanes),
    [2, 2, 2, 1],
  );
  assert.deepEqual(
    result.map((i) => i.lane),
    [0, 1, 0, 0],
  );
});
