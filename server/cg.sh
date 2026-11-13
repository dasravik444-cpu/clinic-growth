#!/usr/bin/env bash
# The  cg  command on a server (installed by server/setup.sh as /usr/local/bin/cg). Type  cg  alone for this list.
#
#   cg on / cg off        start the robot (it then works by itself, also after a restart) / stop it
#   cg status             is it running, the mailboxes' warm-up, leads, e-mails, replies
#   cg log [LINES]        the end of today's log
#   cg settings           open your settings (settings.txt)
#   cg check              test the settings, the Sheet, every mailbox and our own e-mails
#   cg preview [KIND]     show the e-mails a clinic would get (dental, skin, eye, doctor ...)
#   cg test A@x B@y       spam test: the next first e-mail from every mailbox, only to your own addresses
#   cg emails --dry-run   prepare the e-mails into the Sheet's "Email Preview" tab, send nothing
#   cg report             e-mails per day, bounces, replies and who is waiting for your answer
#   cg resume             end a sending pause now
#   cg outlook-login N    sign an Outlook mailbox in, once
#   cg leads / cg hunt    run the lead search / the e-mail hunt now
#   cg run JOB            one of the robot's jobs now: emails, leads, hunt, update or backup
#   cg update             the newest version
DIR=/opt/clinicgrowth
cd "$DIR" || { echo "Clinic Growth is not installed in $DIR (server/setup.sh)."; exit 1; }
case "${1:-help}" in
  on|start)   rm -f data/robot.stop; systemctl enable --now clinicgrowth >/dev/null 2>&1 &&
              echo "The robot is on. It works by itself from now on, also after a restart of the server." ;;
  off|stop)   touch data/robot.stop; systemctl disable --now clinicgrowth >/dev/null 2>&1
              echo "The robot is off. It stays off until:  cg on" ;;
  status)     if systemctl is-active --quiet clinicgrowth; then echo "Switch: ON"; else echo "Switch: OFF (cg on starts it)"; fi
              exec bash scripts/run.sh robot status ;;
  log|logs)   shift; exec bash scripts/run.sh robot log "$@" ;;
  run)        shift; exec bash scripts/run.sh robot run "$@" ;;
  settings)   [ -f settings.txt ] || cp settings-example.txt settings.txt
              chmod 600 settings.txt; exec nano settings.txt ;;
  getkey)     echo "On a server, copy the Google key file into $DIR/secrets/ (docs/HOSTING.md, step 4)." ;;
  whatsapp)   echo "The WhatsApp queue is worked from the tablet or the Sheet (the WhatsApp Queue tab): a server has no WhatsApp." ;;
  update)     curl -fsSL https://raw.githubusercontent.com/dasravik444-cpu/clinic-growth/main/server/setup.sh | bash &&
              { systemctl is-active --quiet clinicgrowth && systemctl restart clinicgrowth; echo "Updated."; } ;;
  help|-h|--help|"") sed -n '2,19p' "$0" | sed 's/^# \{0,1\}//' ;;
  *)          exec bash scripts/run.sh "$@" ;;
esac
