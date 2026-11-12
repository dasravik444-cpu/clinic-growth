/* Clinic front-desk demo: the logic behind the page. No network, no real patients.
   Works in the browser (window.ClinicEngine) and in Node (module.exports) so it can be tested. */
(function (root) {
  "use strict";

  var DAY = 24 * 60, MS = 60000;
  var WEEKDAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
  var MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

  // ---- time helpers (all local time) --------------------------------------------------------
  function pad(n) { return (n < 10 ? "0" : "") + n; }
  function iso(d) { return d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate()); }
  function hm(d) { return pad(d.getHours()) + ":" + pad(d.getMinutes()); }
  function at(dateISO, time) {
    var p = dateISO.split("-"), t = time.split(":");
    return new Date(+p[0], +p[1] - 1, +p[2], +t[0], +t[1], 0, 0);
  }
  function addMin(d, m) { return new Date(d.getTime() + m * MS); }
  function addDays(dateISO, n) { var d = at(dateISO, "12:00"); d.setDate(d.getDate() + n); return iso(d); }
  function nice12(time) {
    var t = time.split(":"), h = +t[0], m = t[1];
    return ((h + 11) % 12 + 1) + (m === "00" ? "" : ":" + m) + (h < 12 ? " am" : " pm");
  }
  function niceDay(dateISO, now) {
    var d = at(dateISO, "12:00"), today = iso(now);
    var label = WEEKDAYS[d.getDay()] + " " + d.getDate() + " " + MONTHS[d.getMonth()];
    if (dateISO === today) return "today, " + label;
    if (dateISO === addDays(today, 1)) return "tomorrow, " + label;
    return label;
  }
  function niceWhen(d, now) { return niceDay(iso(d), now) + " at " + nice12(hm(d)); }

  // ---- the example clinic -------------------------------------------------------------------
  var CLINIC = {
    name: "Dr. Sen's Dental Clinic",
    doctor: "Dr. A. Sen",
    address: "14 Example Road, Salt Lake, Kolkata",
    fee: "Rs 600 for a consultation",
    slotMin: 20,
    cc: "IN",
    // OPD sessions per weekday (0 = Sunday): morning and evening, as most Indian clinics run
    sessions: { 0: [], 1: [["10:00", "13:00"], ["17:00", "20:20"]], 2: [["10:00", "13:00"], ["17:00", "20:20"]],
                3: [["10:00", "13:00"], ["17:00", "20:20"]], 4: [["10:00", "13:00"], ["17:00", "20:20"]],
                5: [["10:00", "13:00"], ["17:00", "20:20"]], 6: [["10:00", "13:00"], ["17:00", "20:20"]] },
    hoursText: "Monday to Saturday, 10 am to 1 pm and 5 pm to 8:20 pm. Closed on Sunday."
  };

  // Whether a clinic may ask patients for public reviews. From reported rules as of Nov 2026;
  // every entry needs checking against the regulator's own text before use with a real clinic.
  var REVIEW_RULES = {
    IN: { label: "India", allowed: false,
          why: "The National Medical Commission's guidelines of 6 October 2026 are reported to bar doctors, and agencies acting for them, from requesting patient reviews for promotion. A National Dental Commission advisory of 14 October 2026 warns dentists about patient solicitation." },
    US: { label: "United States", allowed: true,
          why: "Allowed under Google's rules: every patient gets the same request, nobody is filtered by how happy they were, and nothing is offered in return. The message must not reveal anything about the visit." },
    GB: { label: "United Kingdom", allowed: true,
          why: "No ban was found for doctors or dentists. Google's rules apply: ask everyone the same way, no reward, and nothing misleading." },
    AU: { label: "Australia", allowed: false,
          why: "Testimonials about clinical care are banned in health advertising under the national law AHPRA enforces." },
    SG: { label: "Singapore", allowed: false,
          why: "Testimonials are barred in healthcare advertising, and the medical council has cautioned doctors about rating platforms." },
    AE: { label: "United Arab Emirates", allowed: null,
          why: "Not confirmed either way. Dubai's health authority restricts some testimonials; check the licence rules first." }
  };
  function reviewPolicy(cc) { return REVIEW_RULES[cc] || REVIEW_RULES.AE; }

  // ---- messages -----------------------------------------------------------------------------
  var TEMPLATES = {
    confirm: function (s, a) {
      return "Your appointment with " + s.clinic.doctor + " is booked for " + niceWhen(a.start, s.now) +
        ". Token " + a.token + ". " + s.clinic.address + ". Reply C to cancel or R to change the time.";
    },
    reminder: function (s, a) {
      return "Reminder: you see " + s.clinic.doctor + " " + niceWhen(a.start, s.now) +
        ". Reply 1 to confirm, R to change the time.";
    },
    postvisit: function (s, a) {
      return "Hello " + first(a.name) + ", this is " + s.clinic.name + ". How are you feeling after your visit? " +
        "Reply 1 if all is well, or 2 if you would like the clinic to call you.";
    },
    followup: function (s, f) {
      return "Hello " + first(f.name) + ", " + s.clinic.doctor + " asked to see you again for your " + f.reason +
        " around " + niceDay(f.due, s.now) + ". Reply with a day that suits you and we will book it.";
    },
    followup2: function (s, f) {
      return "Hello " + first(f.name) + ", a gentle reminder that your " + f.reason + " with " + s.clinic.doctor +
        " is due. Reply with a day that suits you, or STOP to end these reminders.";
    },
    missed: function (s, a) {
      return "Hello " + first(a.name) + ", we missed you at " + s.clinic.name + " on " + niceDay(iso(a.start), s.now) +
        ". Reply with a day that suits you and we will find a new time.";
    },
    review: function (s, a) {
      return "Thank you for visiting " + s.clinic.name + ". If you would like to share your experience, " +
        "you can leave a Google review here: g.page/r/your-clinic-link/review";
    },
    feedback: function (s, a) {
      return "Thank you for visiting " + s.clinic.name + ". How was your visit, from 1 (poor) to 5 (excellent)? " +
        "Your reply goes only to the clinic and is never published.";
    }
  };
  function first(name) { return String(name).split(" ")[0]; }
  function digits(phone) { return String(phone).replace(/\D/g, "").slice(-8); }

  function queue(s, kind, subject, when, channel) {
    var m = { id: "m" + (++s.seq), kind: kind, to: subject.name, phone: subject.phone, channel: channel || "WhatsApp",
              at: when, status: "scheduled", ref: subject };
    s.messages.push(m);
    if (when <= s.now) m.status = "sent";
    return m;
  }
  function messageText(s, m) {
    var kind = m.kind;
    if (kind === "aftervisit") kind = reviewPolicy(s.clinic.cc).allowed === true ? "review" : "feedback";
    return TEMPLATES[kind](s, m.ref);
  }
  function messageLabel(s, m) {
    var map = { confirm: "Booking confirmation", reminder: "Appointment reminder", postvisit: "Post-visit check",
                followup: "Follow-up due", followup2: "Follow-up, second reminder", missed: "Missed appointment" };
    if (m.kind === "aftervisit") return reviewPolicy(s.clinic.cc).allowed === true ? "Review request" : "Private feedback";
    return map[m.kind];
  }

  // ---- diary --------------------------------------------------------------------------------
  function slotsFor(s, dateISO) {
    var day = at(dateISO, "12:00").getDay(), out = [];
    (s.clinic.sessions[day] || []).forEach(function (sess) {
      for (var t = at(dateISO, sess[0]); t < at(dateISO, sess[1]); t = addMin(t, s.clinic.slotMin)) out.push(hm(t));
    });
    return out;
  }
  function taken(s, dateISO, time) {
    return s.appointments.some(function (a) {
      return a.status !== "cancelled" && iso(a.start) === dateISO && hm(a.start) === time;
    });
  }
  function freeSlots(s, dateISO) {
    return slotsFor(s, dateISO).filter(function (t) { return at(dateISO, t) > s.now && !taken(s, dateISO, t); });
  }
  function nextOpenDay(s, fromISO) {
    for (var i = 0, d = fromISO; i < 14; i++, d = addDays(d, 1)) if (freeSlots(s, d).length) return d;
    return null;
  }

  function book(s, req) {
    var name = String(req.name || "").trim(), phone = String(req.phone || "").replace(/[^\d+]/g, "");
    var date = String(req.date || ""), time = String(req.time || "");
    if (name.length < 2) throw new Error("The caller's name is missing.");
    if (phone.replace(/\D/g, "").length < 8) throw new Error("A phone number with at least 8 digits is needed.");
    if (!/^\d{4}-\d{2}-\d{2}$/.test(date) || !/^\d{2}:\d{2}$/.test(time)) throw new Error("Give the date as YYYY-MM-DD and the time as HH:MM (24-hour).");
    var slots = slotsFor(s, date);
    if (!slots.length) throw new Error("The clinic is closed on " + niceDay(date, s.now) + ".");
    if (slots.indexOf(time) < 0) throw new Error(nice12(time) + " is not an appointment time. Free times that day: " + (freeSlots(s, date).slice(0, 6).map(nice12).join(", ") || "none"));
    if (at(date, time) <= s.now) throw new Error("That time has already passed.");
    if (taken(s, date, time)) throw new Error(nice12(time) + " is already taken. Free times that day: " + (freeSlots(s, date).slice(0, 6).map(nice12).join(", ") || "none"));
    var a = { id: "a" + (++s.seq), name: name, phone: phone, start: at(date, time), reason: String(req.reason || "consultation").trim(),
              source: req.source || "Phone call", status: "booked", bookedAt: s.now, afterHours: !isOpenNow(s),
              token: slots.indexOf(time) + 1 };
    s.appointments.push(a);
    queue(s, "confirm", a, s.now);
    var mins = (a.start - s.now) / MS;
    if (mins > DAY + 60) queue(s, "reminder", a, addMin(a.start, -DAY));
    else if (mins > 180) queue(s, "reminder", a, addMin(a.start, -120));
    return a;
  }
  function cancel(s, id) {
    var a = s.appointments.filter(function (x) { return x.id === id; })[0];
    if (!a || a.status !== "booked") throw new Error("No such booked appointment.");
    a.status = "cancelled";
    s.messages = s.messages.filter(function (m) { return !(m.ref === a && m.status === "scheduled"); });
    return a;
  }
  function findAppointments(s, q) {
    var phone = String(q.phone || "").replace(/\D/g, "").slice(-8), name = String(q.name || "").toLowerCase().trim();
    return s.appointments.filter(function (a) {
      if (a.status !== "booked" || a.start < s.now) return false;
      return (phone && a.phone.replace(/\D/g, "").slice(-8) === phone) || (name && a.name.toLowerCase().indexOf(name) >= 0);
    });
  }
  function takeMessage(s, req) {
    var note = { id: "n" + (++s.seq), name: String(req.name || "Caller"), phone: String(req.phone || ""), note: String(req.note || ""), at: s.now };
    s.notes.push(note);
    return note;
  }
  function isOpenNow(s) {
    var d = iso(s.now);
    return (s.clinic.sessions[s.now.getDay()] || []).some(function (x) { return s.now >= at(d, x[0]) && s.now < at(d, x[1]); });
  }

  // ---- the clock: what the system does by itself as time passes ------------------------------
  function advance(s, minutes) {
    var events = [];
    s.now = addMin(s.now, minutes);
    s.appointments.forEach(function (a) {
      if (a.status !== "booked" || addMin(a.start, s.clinic.slotMin) > s.now) return;
      if (a.willMiss) {
        a.status = "missed";
        queue(s, "missed", a, addMin(a.start, 120));
        events.push(a.name + " did not come; a rebooking message is queued.");
      } else {
        a.status = "seen";
        var next = addDays(iso(a.start), 1);
        queue(s, "postvisit", a, at(next, "10:00"));
        queue(s, "aftervisit", a, at(next, "18:00"));
        if (a.reviewInDays) {
          var f = { id: "f" + (++s.seq), name: a.name, phone: a.phone, reason: a.reviewReason || "review visit",
                    advised: iso(a.start), due: addDays(iso(a.start), a.reviewInDays), status: "waiting" };
          s.followups.push(f);
          queue(s, "followup", f, at(addDays(f.due, -2), "10:00"));
          events.push(s.clinic.doctor + " asked to see " + a.name + " again in " + a.reviewInDays + " days; the reminder is scheduled.");
        }
        events.push(a.name + " was seen; the post-visit check is scheduled.");
      }
    });
    s.messages.forEach(function (m) {
      if (m.status === "scheduled" && m.at <= s.now) {
        m.status = "sent";
        if (m.kind === "followup" || m.kind === "followup2") m.ref.status = "reminded";
        events.push(messageLabel(s, m) + " sent to " + m.to + ".");
      }
    });
    s.followups.forEach(function (f) {
      var bookedAgain = s.appointments.some(function (a) { return digits(a.phone) === digits(f.phone) && a.status === "booked" && a.start > s.now; });
      if (bookedAgain) f.status = "booked";
      else if (f.status !== "booked" && addDays(f.due, 3) < iso(s.now)) f.status = "overdue";
    });
    return events;
  }

  function stats(s) {
    var today = iso(s.now), weekEnd = addDays(today, 7);
    var todays = s.appointments.filter(function (a) { return iso(a.start) === today && a.status !== "cancelled"; });
    return {
      today: todays.length,
      seen: todays.filter(function (a) { return a.status === "seen"; }).length,
      byAssistant: s.appointments.filter(function (a) { return a.source === "Phone call" && iso(a.bookedAt) === today; }).length,
      afterHours: s.appointments.filter(function (a) { return a.afterHours && (s.now - a.bookedAt) < DAY * MS; }).length,
      followupsDue: s.followups.filter(function (f) { return f.status !== "booked" && f.due <= weekEnd; }).length,
      followupsOverdue: s.followups.filter(function (f) { return f.status === "overdue"; }).length,
      missed: s.appointments.filter(function (a) { return a.status === "missed"; }).length,
      sentToday: s.messages.filter(function (m) { return m.status === "sent" && iso(m.at) === today; }).length,
      callbacks: s.notes.length
    };
  }

  // ---- example data (invented people) -------------------------------------------------------
  function createState(realNow) {
    var start = new Date(realNow.getFullYear(), realNow.getMonth(), realNow.getDate(), 9, 30, 0, 0);
    if (start.getDay() === 0) start.setDate(start.getDate() + 1);          // never open the demo on a closed Sunday
    var s = { clinic: JSON.parse(JSON.stringify(CLINIC)), now: start, seq: 0, appointments: [], followups: [], messages: [], notes: [] };
    var today = iso(start);
    function past(daysAgo, time) {                                           // the nearest working day that many days back
      var d = addDays(today, -daysAgo);
      while (!slotsFor(s, d).length) d = addDays(d, -1);
      return at(d, time);
    }
    function appt(name, phone, when, reason, source, extra) {
      var a = { id: "a" + (++s.seq), name: name, phone: phone, start: when, reason: reason, source: source, status: "booked",
                bookedAt: addMin(when, -2 * DAY), afterHours: false, token: slotsFor(s, iso(when)).indexOf(hm(when)) + 1 };
      for (var k in extra || {}) a[k] = extra[k];
      s.appointments.push(a);
      return a;
    }
    function sent(kind, ref, when) { var m = queue(s, kind, ref, when); m.status = "sent"; return m; }

    // today
    var meera = appt("Meera Iyer", "98300 00105", at(today, "11:00"), "tooth sensitivity", "WhatsApp");
    sent("reminder", meera, addMin(meera.start, -DAY));
    var arjun = appt("Arjun Nair", "98300 00106", at(today, "17:20"), "chipped tooth", "Phone call",
                     { bookedAt: addMin(start, -11 * 60 - 16), afterHours: true });
    sent("confirm", arjun, arjun.bookedAt);
    queue(s, "reminder", arjun, addMin(arjun.start, -120));
    var priya = appt("Priya Sharma", "98300 00107", at(today, "10:00"), "filling", "Front desk", { reviewInDays: 14, reviewReason: "filling check" });
    sent("reminder", priya, addMin(priya.start, -DAY));
    appt("Kabir Malhotra", "98300 00108", at(today, "18:00"), "consultation", "Front desk");

    // earlier visits
    var rahul = appt("Rahul Mehra", "98300 00102", past(1, "18:20"), "extraction", "Front desk", { status: "seen" });
    queue(s, "postvisit", rahul, at(today, "10:00"));
    queue(s, "aftervisit", rahul, at(today, "18:00"));
    var joseph = appt("Joseph D'Souza", "98300 00104", past(1, "17:40"), "braces adjustment", "WhatsApp", { status: "missed" });
    sent("missed", joseph, addMin(joseph.start, 120));
    appt("Ananya Bose", "98300 00101", past(5, "11:20"), "root canal, first sitting", "Front desk", { status: "seen" });

    // follow-ups the doctor advised
    var ananya = { id: "f" + (++s.seq), name: "Ananya Bose", phone: "98300 00101", reason: "root canal second sitting",
                   advised: iso(past(5, "11:20")), due: addDays(today, 2), status: "waiting" };
    var farida = { id: "f" + (++s.seq), name: "Farida Khan", phone: "98300 00103", reason: "six-month cleaning and check",
                   advised: addDays(today, -182), due: addDays(today, 1), status: "reminded" };
    var dsouza = { id: "f" + (++s.seq), name: "Joseph D'Souza", phone: "98300 00104", reason: "monthly braces adjustment",
                   advised: addDays(today, -31), due: iso(joseph.start), status: "reminded" };
    s.followups.push(ananya, farida, dsouza);
    queue(s, "followup", ananya, at(today, "10:00"));
    sent("followup", farida, at(addDays(today, -3), "10:00"));
    queue(s, "followup2", farida, at(today, "18:00"));
    return s;
  }

  // ---- the assistant: instructions and tools for Claude --------------------------------------
  function rules(s) {
    var c = s.clinic, today = iso(s.now);
    return [
      "You are the phone receptionist of " + c.name + " in a product demonstration. All patients and details are invented.",
      "The caller HEARS your words. Speak the way a warm, efficient receptionist talks on the phone: one or two short sentences, one question at a time. No lists, no markdown, no emojis, no stage directions. Reply in the language the caller uses (English, Hindi or Bengali).",
      "Clinic facts: doctor " + c.doctor + ". Address: " + c.address + ". Fee: " + c.fee + ". Hours: " + c.hoursText + " Appointments are " + c.slotMin + " minutes.",
      "Right now it is " + WEEKDAYS[s.now.getDay()] + " " + today + ", " + hm(s.now) + ". The clinic is " + (isOpenNow(s) ? "open" : "closed at this moment, and you are answering so that no call is missed") + ".",
      "What you can do: tell callers the facts above; look up free times (get_free_slots); book (book_appointment); find and cancel a caller's booking (find_appointment, cancel_appointment); note a message for the staff to call back (take_message).",
      "To book you need the caller's full name, phone number, the day, the time and a few words on why they are coming. Always check free times with the tool before offering any. Offer at most three times. Say the details back and get a yes before you book. After booking, tell them the day, time and token number, and that a confirmation message is on its way.",
      "Never give medical advice: no diagnosis, no medicines, no doses, no home remedies. If asked, say the doctor will advise at the visit and offer the earliest time.",
      "If the caller describes an emergency (heavy bleeding that will not stop, trouble breathing or swallowing, a swollen face with fever, a knocked-out tooth, chest pain, a serious injury), tell them to go to the nearest emergency department or call the local emergency number now, then offer to note a callback.",
      "If you do not know something, do not guess: take a message for the staff."
    ].join("\n");
  }
  function tools(s, onChange) {
    function changed() { if (onChange) onChange(); }
    return [
      { name: "get_free_slots",
        description: "Free appointment times on one day. Returns {date, day, closed, free: [HH:MM, ...]} with at most 12 times, earliest first, and next_open_day when the day is closed or full.",
        inputSchema: { type: "object", properties: { date: { type: "string", description: "YYYY-MM-DD" } }, required: ["date"] },
        execute: function (i) {
          var d = String(i.date), free = freeSlots(s, d);
          return { date: d, day: niceDay(d, s.now), closed: !slotsFor(s, d).length, free: free.slice(0, 12),
                   next_open_day: free.length ? null : nextOpenDay(s, addDays(d, 1)) };
        } },
      { name: "book_appointment",
        description: "Books one appointment after the caller has confirmed the details. Returns {id, token, day, time}. Throws with the reason, and the free times, if it cannot.",
        inputSchema: { type: "object", properties: { name: { type: "string" }, phone: { type: "string" },
          date: { type: "string", description: "YYYY-MM-DD" }, time: { type: "string", description: "HH:MM, 24-hour" },
          reason: { type: "string", description: "why they are coming, in the caller's words" } }, required: ["name", "phone", "date", "time"] },
        execute: function (i) {
          var a = book(s, { name: i.name, phone: i.phone, date: i.date, time: i.time, reason: i.reason, source: "Phone call" });
          changed();
          return { id: a.id, token: a.token, day: niceDay(iso(a.start), s.now), time: nice12(hm(a.start)) };
        } },
      { name: "find_appointment",
        description: "Upcoming bookings for a caller, by phone number or name. Returns a list of {id, name, day, time, reason}.",
        inputSchema: { type: "object", properties: { phone: { type: "string" }, name: { type: "string" } } },
        execute: function (i) {
          return findAppointments(s, { phone: i.phone, name: i.name }).map(function (a) {
            return { id: a.id, name: a.name, day: niceDay(iso(a.start), s.now), time: nice12(hm(a.start)), reason: a.reason };
          });
        } },
      { name: "cancel_appointment",
        description: "Cancels a booking by its id (from find_appointment) once the caller has confirmed. Returns {cancelled: true}.",
        inputSchema: { type: "object", properties: { id: { type: "string" } }, required: ["id"] },
        execute: function (i) { cancel(s, String(i.id)); changed(); return { cancelled: true }; } },
      { name: "take_message",
        description: "Leaves a note for the clinic staff to call the caller back. Returns {noted: true}.",
        inputSchema: { type: "object", properties: { name: { type: "string" }, phone: { type: "string" }, note: { type: "string" } }, required: ["note"] },
        execute: function (i) { takeMessage(s, i); changed(); return { noted: true }; } }
    ];
  }

  // ---- a scripted stand-in, used where Claude is not available to the viewer -----------------
  var EMERGENCY = /(bleed(ing)? (a lot|heavily|won'?t stop)|can'?t breathe|breathing|chest pain|unconscious|knocked.?out|accident|swollen face|swelling.*fever)/i;
  function parseDay(text, now) {
    var t = text.toLowerCase(), today = iso(now);
    if (/\btoday\b/.test(t)) return today;
    if (/\bday after tomorrow\b/.test(t)) return addDays(today, 2);
    if (/\btomorrow\b/.test(t)) return addDays(today, 1);
    for (var i = 0; i < 7; i++) {
      if (t.indexOf(WEEKDAYS[i].toLowerCase()) >= 0 || new RegExp("\\b" + WEEKDAYS[i].slice(0, 3).toLowerCase() + "\\b").test(t)) {
        var n = (i - now.getDay() + 7) % 7;
        return addDays(today, n === 0 ? 7 : n);
      }
    }
    return null;
  }
  function parseTime(text) {
    var m = /\b(\d{1,2})(?:[:.](\d{2}))?\s*(am|pm|a\.m\.|p\.m\.)/i.exec(text);
    if (m) { var h = +m[1] % 12 + (/p/i.test(m[3]) ? 12 : 0); return pad(h) + ":" + (m[2] || "00"); }
    m = /\b([01]?\d|2[0-3])[:.]([0-5]\d)\b/.exec(text);
    if (m) return pad(+m[1]) + ":" + m[2];
    if (/\bmorning\b/i.test(text)) return "morning";
    if (/\b(evening|afternoon|after work)\b/i.test(text)) return "evening";
    return null;
  }
  function Scripted(s, onChange) {
    var f = { step: "open", date: null, time: null, name: null, phone: null, reason: null };
    function offer() {
      var free = freeSlots(s, f.date);
      if (f.time === "morning") free = free.filter(function (t) { return t < "13:00"; });
      if (f.time === "evening") free = free.filter(function (t) { return t >= "13:00"; });
      f.time = null;
      if (!free.length) {
        var next = nextOpenDay(s, addDays(f.date, 1));
        var was = f.date; f.date = next;
        return "We have nothing free " + niceDay(was, s.now) + ". The next opening is " + niceDay(next, s.now) + " at " + nice12(freeSlots(s, next)[0]) + ". Shall I take that, or would another time suit you?";
      }
      f.step = "time";
      return "On " + niceDay(f.date, s.now) + " I have " + free.slice(0, 3).map(nice12).join(", ").replace(/, ([^,]*)$/, " or $1") + ". Which would you like?";
    }
    function next() {
      if (!f.date) { f.step = "day"; return "Of course. Which day would you like to come in?"; }
      if (!f.time || f.time === "morning" || f.time === "evening") return offer();
      if (freeSlots(s, f.date).indexOf(f.time) < 0) { var t = f.time; f.time = null; return nice12(t) + " is not free. " + offer(); }
      if (!f.name) { f.step = "name"; return "May I have your full name?"; }
      if (!f.phone) { f.step = "phone"; return "And a phone number for the confirmation message?"; }
      if (!f.reason) { f.step = "reason"; return "Briefly, what would you like the doctor to look at?"; }
      f.step = "confirm";
      return "So that is " + f.name + ", " + niceDay(f.date, s.now) + " at " + nice12(f.time) + ", for " + f.reason + ". Shall I book it?";
    }
    this.reply = function (text) {
      var t = String(text).trim(), low = t.toLowerCase();
      if (EMERGENCY.test(t)) return "That sounds urgent. Please go to the nearest emergency department or call your local emergency number now. I can also leave a note for the doctor to call you back.";
      if (/\b(pain ?killer|medicine|tablet|antibiotic|what should i take|home remedy)\b/i.test(t) && f.step === "open")
        return "I am not able to advise on treatment, but the doctor will at your visit. Shall I find you the earliest appointment?";
      if (f.step === "confirm") {
        if (/\b(yes|yeah|yep|ok|okay|sure|please|book|correct|right)\b/.test(low)) {
          try {
            var a = book(s, { name: f.name, phone: f.phone, date: f.date, time: f.time, reason: f.reason, source: "Phone call" });
            if (onChange) onChange();
            f = { step: "open" };
            return "Done. You are booked for " + niceWhen(a.start, s.now) + ", token " + a.token + ". A confirmation message is on its way. Is there anything else?";
          } catch (e) { f.time = null; return e.message + " " + offer(); }
        }
        if (/\b(no|not|wrong|change)\b/.test(low)) { f.time = null; f.step = "time"; return "No problem. Which day and time would you prefer?"; }
      }
      var day = parseDay(t, s.now), time = parseTime(t);
      var nameM = /(?:my name is|this is|i am|i'm|name's)\s+([a-z][a-z .'-]{1,40}?)(?=[,.]|\s+and\b|\s+my\b|$)/i.exec(t);
      var phoneM = /(\+?\d[\d\s-]{7,}\d)/.exec(t);
      if (day) f.date = day;
      if (time) f.time = time;
      if (nameM && !/\b(calling|looking|having|in pain)\b/i.test(nameM[1])) f.name = nameM[1].trim().replace(/\b\w/g, function (c) { return c.toUpperCase(); });
      if (phoneM) f.phone = phoneM[1].trim();
      var wantsBooking = /\b(appointment|book|see the doctor|come in|visit|check.?up|slot|schedule)\b/.test(low);
      if (f.step === "name" && !f.name && !phoneM && t.length < 50) f.name = t.replace(/[.,!]/g, "").replace(/\b\w/g, function (c) { return c.toUpperCase(); });
      else if (f.step === "reason" && !f.reason) f.reason = t.replace(/[.!]$/, "").toLowerCase();
      else if (f.step === "time" && !time && !day) return "Sorry, I did not catch a time. " + offer();
      if (f.step === "open" && !wantsBooking && !day && !time) {
        if (/\b(open|hours?|timings?|closed?|when)\b/.test(low)) return "We are open " + s.clinic.hoursText + " Would you like an appointment?";
        if (/\b(fee|cost|charge|price|how much)\b/.test(low)) return "It is " + s.clinic.fee + ". Treatment costs depend on what the doctor finds. Would you like an appointment?";
        if (/\b(where|address|location|located)\b/.test(low)) return "We are at " + s.clinic.address + ". Would you like an appointment?";
        if (/\b(cancel)\b/.test(low)) return "I can help with that. Could you tell me the phone number the booking is under? In this simple version, please use the Diary to cancel.";
        if (/\b(thanks|thank you|bye|nothing|no)\b/.test(low)) return "Thank you for calling " + s.clinic.name + ". Take care.";
        return "I can book an appointment, or tell you our hours, fee and address. How can I help?";
      }
      if (!f.reason) {
        var r = /\b(tooth ?ache|pain|cleaning|scaling|filling|braces|check.?up|root canal|extraction|cavity|bleeding gums|sensitivity|crown|implant|whitening)\b/i.exec(t);
        if (r) f.reason = r[1].toLowerCase();
      }
      return next();
    };
  }

  var api = {
    createState: createState, slotsFor: slotsFor, freeSlots: freeSlots, nextOpenDay: nextOpenDay, book: book, cancel: cancel,
    findAppointments: findAppointments, takeMessage: takeMessage, advance: advance, stats: stats, isOpenNow: isOpenNow,
    reviewPolicy: reviewPolicy, REVIEW_RULES: REVIEW_RULES, messageText: messageText, messageLabel: messageLabel,
    rules: rules, tools: tools, Scripted: Scripted, parseDay: parseDay, parseTime: parseTime,
    iso: iso, hm: hm, at: at, addDays: addDays, addMin: addMin, nice12: nice12, niceDay: niceDay, niceWhen: niceWhen,
    WEEKDAYS: WEEKDAYS
  };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.ClinicEngine = api;
})(typeof window !== "undefined" ? window : globalThis);
