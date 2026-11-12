// Run:  node --test demo/
const test = require("node:test");
const assert = require("node:assert/strict");
const E = require("./engine.js");

const WED = new Date(2026, 10, 11, 15, 45);          // a Wednesday; the demo clock starts that day at 09:30
const fresh = () => E.createState(WED);
const tomorrow = (s) => E.addDays(E.iso(s.now), 1);

test("the demo opens on a working morning with example data", () => {
  const s = fresh();
  assert.equal(E.hm(s.now), "09:30");
  assert.equal(E.createState(new Date(2026, 10, 15, 12, 0)).now.getDay(), 1);     // Sunday -> Monday
  assert.equal(E.stats(s).today, 4);
  assert.equal(s.followups.length, 3);
  assert.ok(s.messages.some((m) => m.status === "scheduled") && s.messages.some((m) => m.status === "sent"));
  assert.equal(E.stats(s).afterHours, 1);                                          // last night's call was caught
});

test("diary: sessions, free times, closed Sunday", () => {
  const s = fresh();
  const slots = E.slotsFor(s, E.iso(s.now));
  assert.equal(slots[0], "10:00");
  assert.equal(slots[slots.length - 1], "20:00");
  assert.equal(slots.length, 19);
  assert.ok(!slots.includes("13:00") && !slots.includes("14:00"));
  assert.ok(!E.freeSlots(s, E.iso(s.now)).includes("11:00"));                      // Meera has it
  assert.deepEqual(E.slotsFor(s, "2026-11-15"), []);
  assert.equal(E.nextOpenDay(s, "2026-11-15"), "2026-11-16");
});

test("booking sends a confirmation, schedules a reminder and refuses bad requests", () => {
  const s = fresh();
  const day = tomorrow(s);
  const a = E.book(s, { name: "Test Caller", phone: "98300 00199", date: day, time: "17:00", reason: "toothache" });
  assert.equal(a.token, 10);
  assert.equal(a.afterHours, true);                                                // 09:30 is before opening
  const mine = s.messages.filter((m) => m.ref === a);
  assert.deepEqual(mine.map((m) => [m.kind, m.status]), [["confirm", "sent"], ["reminder", "scheduled"]]);
  assert.match(E.messageText(s, mine[0]), /booked for tomorrow, Thursday 12 Nov at 5 pm\. Token 10/);
  assert.throws(() => E.book(s, { name: "B", phone: "98300 00198", date: day, time: "17:00" }), /name is missing/);
  assert.throws(() => E.book(s, { name: "Bo Two", phone: "98300 00198", date: day, time: "17:00" }), /already taken\. Free times/);
  assert.throws(() => E.book(s, { name: "Bo Two", phone: "98300 00198", date: day, time: "14:00" }), /not an appointment time/);
  assert.throws(() => E.book(s, { name: "Bo Two", phone: "98300 00198", date: "2026-11-15", time: "10:00" }), /closed/);
  assert.throws(() => E.book(s, { name: "Bo Two", phone: "123", date: day, time: "10:00" }), /phone number/);
  assert.throws(() => E.book(s, { name: "Bo Two", phone: "98300 00198", date: "2026-11-10", time: "10:00" }), /already passed/);
  assert.equal(E.findAppointments(s, { phone: "+91 98300-00199" })[0].id, a.id);
  E.cancel(s, a.id);
  assert.equal(s.messages.filter((m) => m.ref === a && m.status === "scheduled").length, 0);
  assert.ok(E.freeSlots(s, day).includes("17:00"));
});

test("as the day passes the system sends what is due and follows up visits", () => {
  const s = fresh();
  let ev = E.advance(s, 60);                                                        // 10:30
  assert.ok(ev.some((e) => /Post-visit check sent to Rahul Mehra/.test(e)));
  assert.ok(ev.some((e) => /Follow-up due sent to Ananya Bose/.test(e)));
  assert.ok(ev.some((e) => /asked to see Priya Sharma again in 14 days/.test(e)));
  assert.equal(s.followups.find((f) => f.name === "Ananya Bose").status, "reminded");
  const priya = s.followups.find((f) => f.name === "Priya Sharma");
  assert.equal(priya.due, E.addDays(E.iso(s.now), 14));
  ev = E.advance(s, 9 * 60);                                                        // 19:30
  assert.ok(ev.some((e) => /second reminder sent to Farida Khan/.test(e)));
  assert.equal(E.stats(s).seen, 4);
  E.book(s, { name: "Farida Khan", phone: "98300 00103", date: tomorrow(s), time: "10:20", reason: "cleaning" });
  E.advance(s, 1);
  assert.equal(s.followups.find((f) => f.name === "Farida Khan").status, "booked");
  E.advance(s, 6 * 24 * 60);
  assert.equal(s.followups.find((f) => f.name === "Joseph D'Souza").status, "overdue");
  assert.ok(E.stats(s).followupsOverdue >= 1);
});

test("a patient who does not come gets a rebooking message", () => {
  const s = fresh();
  const a = E.book(s, { name: "No Show", phone: "98300 00190", date: E.iso(s.now), time: "12:00" });
  a.willMiss = true;
  E.advance(s, 5 * 60);
  assert.equal(a.status, "missed");
  const m = s.messages.find((x) => x.ref === a && x.kind === "missed");
  assert.equal(m.status, "sent");
  assert.match(E.messageText(s, m), /we missed you/);
});

test("review requests follow the country's rules", () => {
  const s = fresh();
  const m = s.messages.find((x) => x.kind === "aftervisit");
  assert.equal(E.reviewPolicy("IN").allowed, false);
  assert.equal(E.messageLabel(s, m), "Private feedback");
  assert.match(E.messageText(s, m), /never published/);
  for (const cc of ["US", "GB"]) {
    s.clinic.cc = cc;
    assert.equal(E.messageLabel(s, m), "Review request");
    assert.match(E.messageText(s, m), /Google review/);
    assert.doesNotMatch(E.messageText(s, m), /extraction|discount|free/i);          // nothing about the visit, no reward
  }
  for (const cc of ["AU", "SG", "AE"]) { s.clinic.cc = cc; assert.equal(E.messageLabel(s, m), "Private feedback"); }
});

test("the assistant's tools read and change the diary", () => {
  const s = fresh();
  let changes = 0;
  const tools = Object.fromEntries(E.tools(s, () => changes++).map((t) => [t.name, t]));
  const day = tomorrow(s);
  const free = tools.get_free_slots.execute({ date: day });
  assert.equal(free.closed, false);
  assert.equal(free.free.length, 12);
  const sun = tools.get_free_slots.execute({ date: "2026-11-15" });
  assert.deepEqual([sun.closed, sun.free.length, sun.next_open_day], [true, 0, "2026-11-16"]);
  const b = tools.book_appointment.execute({ name: "Tool Caller", phone: "9830000188", date: day, time: free.free[0], reason: "check-up" });
  assert.deepEqual([b.token, b.time], [1, "10 am"]);
  assert.throws(() => tools.book_appointment.execute({ name: "Tool Caller", phone: "9830000188", date: day, time: free.free[0] }), /already taken/);
  const found = tools.find_appointment.execute({ phone: "9830000188" });
  assert.equal(found.length, 1);
  assert.deepEqual(tools.cancel_appointment.execute({ id: found[0].id }), { cancelled: true });
  tools.take_message.execute({ name: "X", phone: "1", note: "asks about implants" });
  assert.equal(changes, 3);
  assert.equal(E.stats(s).callbacks, 1);
  const rules = E.rules(s);
  assert.match(rules, /Never give medical advice/);
  assert.match(rules, /emergency department/);
  assert.match(rules, /closed at this moment/);
  for (const t of E.tools(s)) assert.ok(/^[A-Za-z0-9_-]{1,128}$/.test(t.name) && t.description.length < 1000);
});

test("the scripted stand-in books a visit through a normal conversation", () => {
  const s = fresh();
  const bot = new E.Scripted(s);
  assert.match(bot.reply("Hi, what are your timings?"), /Monday to Saturday/);
  assert.match(bot.reply("I have a toothache, can I get an appointment tomorrow evening?"), /On tomorrow, Thursday 12 Nov I have 5 pm, 5:20 pm or 5:40 pm/);
  assert.match(bot.reply("5:20 pm please"), /full name/);
  assert.match(bot.reply("Rohan Verma"), /phone number/);
  assert.match(bot.reply("it's 98300 00177"), /So that is Rohan Verma, tomorrow, Thursday 12 Nov at 5:20 pm, for toothache/);
  assert.match(bot.reply("yes please"), /Done\. You are booked .* token 11/);
  const a = s.appointments.find((x) => x.name === "Rohan Verma");
  assert.equal(E.hm(a.start), "17:20");
  assert.equal(a.reason, "toothache");
});

test("the scripted stand-in handles one-line requests, taken times, emergencies and advice", () => {
  const s = fresh();
  let bot = new E.Scripted(s);
  assert.match(bot.reply("My name is Sana Ali and I want to book a cleaning today at 11 am"), /11 am is not free\. On today.* I have/);
  assert.match(bot.reply("11:20 am"), /phone number/);
  assert.match(bot.reply("9830000166"), /Shall I book it/);
  assert.match(bot.reply("no, change it"), /Which day and time/);
  bot = new E.Scripted(s);
  assert.match(bot.reply("my face is swollen and I can't breathe properly"), /emergency department/);
  assert.match(bot.reply("which painkiller should I take?"), /not able to advise on treatment/);
  assert.match(bot.reply("how much is the fee"), /Rs 600/);
  assert.match(bot.reply("appointment on Sunday"), /nothing free Sunday 15 Nov\. The next opening is Monday 16 Nov at 10 am/);
});

test("day and time parsing", () => {
  assert.equal(E.parseDay("day after tomorrow", WED), "2026-11-13");
  assert.equal(E.parseDay("next friday morning", WED), "2026-11-13");
  assert.equal(E.parseDay("on wednesday", WED), "2026-11-18");
  assert.equal(E.parseDay("hello", WED), null);
  assert.equal(E.parseTime("at 6 pm"), "18:00");
  assert.equal(E.parseTime("10.40 a.m."), "10:40");
  assert.equal(E.parseTime("17:20"), "17:20");
  assert.equal(E.parseTime("12 pm"), "12:00");
  assert.equal(E.parseTime("in the evening"), "evening");
  assert.equal(E.parseTime("my number is 98300 00177"), null);
});
