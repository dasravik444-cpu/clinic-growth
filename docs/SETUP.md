# Setting up Clinic Growth on the tablet (about 40 minutes, once)

It runs in **Termux**, in its own small Ubuntu, next to your other robots (WorldReach `wr`, Plant Parlour `pp`, the
India review robot). They are not touched: Clinic Growth has its own folder, its own memory, its own Google Sheet,
and one command of its own: `cg`.

## Accounts: keep this project apart from the others

Make new accounts for Clinic Growth; share none with WorldReach or the other robots:

| Account | What it is for |
|---|---|
| **1 new Google account** (the "admin" one) | Owns the Google Sheet and the Google Cloud project with the key file. It never sends e-mails, so a spam complaint can never touch your Sheet or key. |
| **2 or 3 new Gmail accounts** | Only for writing to clinics. Each warms up by itself (50, 100, 200 a day ...). Give each a real name and photo, and send a few normal e-mails from it first. |
| **1 Outlook account** (optional) | A fourth mailbox later; docs/OUTLOOK.md. |

The key file for this project comes from the admin account: console.cloud.google.com → new project
"clinic-growth" → APIs: enable "Google Sheets API" → Service accounts → Create → Keys → Add key → JSON.

Have ready:

| You need | Where it comes from |
|---|---|
| A new, empty **Google Sheet** | sheets.new in the browser. Name it "Clinic Growth". |
| Your **Google key file** (.json) | From the new admin account (above), not the one WorldReach uses. |
| **2 or 3 mailboxes** | Gmail accounts with an app password each, and/or an Outlook address (docs/OUTLOOK.md). Use mailboxes made for this project: not your personal one, and not the ones WorldReach sends from (a spam complaint here would slow those down too). |
| Your **business name** | What doctors should see as the sender, e.g. the name on your overview PDF. |
| Your **postal address** | One line. Needed once you write to the US or Canada; fill it in anyway. |
| Your **WhatsApp Business number** | Shown under every e-mail. |

## Step 1 - One paste installs everything

Open Termux, paste this line (long-press → Paste), press Enter:

```
curl -fsSL https://raw.githubusercontent.com/dasravik444-cpu/clinic-growth/main/android/setup.sh | bash
```

Wait until it says **Done** (10-20 minutes). If it stops with an error (the internet dropped), paste the same
line again: it carries on where it stopped.

## Step 2 - The Google key and the Sheet

1. Download the key file (table above); it lands in the tablet's Download folder. Then type:
   ```
   cg getkey
   ```
   It prints an address ending in `gserviceaccount.com`.
2. Open your new Sheet → **Share** → paste that address → **Editor** → untick "Notify people" → **Share**.

## Step 3 - Your settings

```
cg settings
```

A text editor opens. Move with the arrow keys and type after each `=`:

- `WR_SHEET_ID` - from the Sheet's address, the long part between `/d/` and `/edit`
- `SENDER_NAME` - your name as doctors should see it
- `SENDER_BUSINESS` - your business name
- `SENDER_PHONE` - your WhatsApp number with +91
- `POSTAL_ADDRESS` - your address on one line
- `MAILBOX_1_ADDRESS` and `MAILBOX_1_PASSWORD` - the first Gmail and its 16-letter app password
  (made at myaccount.google.com/apppasswords **while signed in to that Gmail**, 2-Step Verification on)
- the same for `MAILBOX_2` and `MAILBOX_3` (leave a mailbox you do not have empty)
- `MAILBOX_4_ADDRESS` and `MAILBOX_5_ADDRESS` - your two Outlook addresses; they need the steps in docs/OUTLOOK.md
  (you can add them a day later: the Gmail mailboxes work without them)

Leave `LIVE=no` for now. Save: **CTRL** then **o**, Enter. Close: **CTRL** then **x**.

## Step 4 - Check

```
cg check
```

Every line should say `[OK]`. A line with `[!!]` says what to fix (then `cg settings` again).

## Step 5 - Look at what clinics will get

```
cg preview dental
```

shows the first e-mail and the two follow-ups a dental clinic would get (`cg preview skin`, `eye`, `doctor`, ...
for the others). No e-mail offers reviews: in India a doctor may not ask patients for them. To change the words:
tell me, or edit `[texts]` in `config/outreach.toml`.

The overview PDF that answers a doctor's "yes" is `marketing/brochure.pdf`. It carries the business name
Aurenflow and no prices; change `marketing/brochure.json` and type `cg brochure` for your own.

## Step 6 - Find the first clinics

```
cg leads
```

takes the first half of the first city (Kolkata), about 2 hours: it finds the clinics, then reads each clinic's own
website for e-mail addresses. Keep the tablet charging and on Wi-Fi. When it is done, the **Clinics IN** tab of
your Sheet has them. (The robot does this every evening by itself once it is on: one half of a city a day.)

Hospitals appear in that tab too. They are there for the hospital-doctor search and are never written to.

## Step 7 - The spam test (do not skip it)

```
cg emails --dry-run
```

fills the **Email Preview** tab with the exact e-mails that would go out now. Read a few. Then send the real first
e-mail from each of your mailboxes to **your own** addresses only:

```
cg test yourprivate@gmail.com yourother@outlook.com
```

Open both and look where each landed: **Primary** is what we want; **Spam** means that mailbox is not ready
(docs/DELIVERABILITY.md says what to do). Send me a screenshot if unsure.

## Step 8 - Go live

1. `cg settings` → change `LIVE=no` to `LIVE=yes` → save.
2. Two real e-mails with a copy to you, to see everything works:
   ```
   cg emails --max 2 --copy-to yourprivate@gmail.com
   ```
3. Switch the robot on:
   ```
   cg on
   ```

From now on it works by itself. Three Android settings keep it alive (the same as for your other robots):
**Settings → Apps → Termux → Battery → Unrestricted**, the Termux notification stays (never tap Exit), and the
tablet stays charging on Wi-Fi.

## Every day (15 minutes)

| When | What |
|---|---|
| An alert e-mail arrives | A clinic answered. Reply **within the hour** from the mailbox it wrote to: suggest a 15-minute call and show the demo. |
| Once a day | `cg report` (or the **Replies** tab): anyone still waiting for your answer? |
| Once a day | `cg status`: is every mailbox sending? A line "SENDING PAUSED" says why and until when. |
| When the WhatsApp queue has messages | `cg whatsapp` |

## What the robot does, and when (India time)

| Time | Job |
|---|---|
| every hour at :35 | e-mails: replies and bounces read, follow-ups and new e-mails sent - only while it is working hours (9:30-17:30, Monday to Friday) at the clinics |
| 18:30 | lead search: the next half of a city, about 2 hours, then the e-mail hunt |
| 21:15 | more e-mail hunting in earlier cities |
| 07:30, 07:45 | newest version (kept only if it starts cleanly); backup of the memory |

## If something is wrong

| You see | Do this |
|---|---|
| `cg: command not found` | paste the setup line of step 1 again |
| `cg status` says "not running" | `cg on`; check the battery setting |
| `[!!] Google Sheet ... 403` | share the Sheet with the key's address as Editor (step 2) |
| `the login was refused` | make a new app password for that Gmail, put it in `cg settings` |
| `SENDING PAUSED` | read the reason. It restarts by itself; `cg resume` ends it now (only if you know why it paused) |
| Anything else | `cg log 80` and send me what it shows |

## Before you switch LIVE to yes

The e-mails offer a receptionist on the clinic's phone line and WhatsApp reminders. Today those exist as the demo
only (docs/SERVICES.md, "What each service needs"). A doctor who says yes will want it within weeks, so go live
with a small number of e-mails first (`cg emails --max 20`) and treat the first clinics as pilots.
