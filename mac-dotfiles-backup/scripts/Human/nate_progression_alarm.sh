#!/bin/zsh

today="$(/bin/date +%F)"
hm="$(/bin/date +%H:%M)"
sound="/System/Library/Sounds/Glass.aiff"
title="Nate Progression"

stage="W5"
if [[ "$today" < "2026-05-13" ]]; then
  stage="W1"
elif [[ "$today" < "2026-05-20" ]]; then
  stage="W2"
elif [[ "$today" < "2026-05-27" ]]; then
  stage="W3"
elif [[ "$today" < "2026-06-03" ]]; then
  stage="W4"
fi

notify() {
  local subtitle="$1"
  local message="$2"
  local rings="${3:-1}"
  local speak="${4:-false}"

  for _ in $(seq 1 "$rings"); do
    /usr/bin/afplay "$sound"
  done

  /usr/bin/osascript -e "display notification \"${message}\" with title \"${title}\" subtitle \"${subtitle}\" sound name \"Glass\""

  if [[ "$speak" == "true" ]]; then
    /usr/bin/say "$message" >/dev/null 2>&1 &
  fi
}

case "${stage}:${hm}" in
  W1:07:30)
    notify "Week 1 Wake" "Wake up now. Prayer, shower, workout, food, and dress by 8:45." 4 true
    ;;
  W1:07:50)
    notify "Week 1 Backup" "Backup alarm. Feet on floor. No snooze." 5 true
    ;;
  W1:21:45)
    notify "Night Score" "Score the day out of 10. Seven is a good day." 1 false
    ;;
  W1:23:00)
    notify "Wind Down" "Night prayer and wind down. Screens down soon." 1 false
    ;;
  W1:23:30)
    notify "Screens Down" "Screens down. Bed by midnight." 1 false
    ;;

  W2:07:15)
    notify "Week 2 Wake" "Wake up. Prayer first, then shower, workout, food, dress, ready by 8:45." 4 true
    ;;
  W2:07:35)
    notify "Week 2 Backup" "Backup alarm. Get out of bed." 5 true
    ;;
  W2:21:45)
    notify "Night Score" "Score the day out of 10. Repeat the week if mornings slipped." 1 false
    ;;
  W2:23:00)
    notify "Wind Down" "Night prayer and wind down. Protect tomorrow morning." 1 false
    ;;
  W2:23:30)
    notify "Screens Down" "Screens down. Bed by midnight." 1 false
    ;;

  W3:07:00)
    notify "Week 3 Wake" "Wake up. Prayer, shower, workout, food, dress, ready by 8:45." 4 true
    ;;
  W3:07:20)
    notify "Week 3 Backup" "Backup alarm. Get moving now." 5 true
    ;;
  W3:21:30)
    notify "Night Score" "Score the day. Keep sleep and movement stable before adding more work." 1 false
    ;;
  W3:22:45)
    notify "Wind Down" "Night prayer and wind down. Lights-out target is 11:45." 1 false
    ;;
  W3:23:30)
    notify "Bed Check" "Bed check. Do not fix the day by staying up later." 1 false
    ;;

  W4:06:45|W5:06:30)
    notify "Baseline Wake" "Wake up. Finish prayer, shower, workout, food, and dressing before 8:45." 4 true
    ;;
  W4:07:05|W5:06:50)
    notify "Backup Wake" "Backup alarm. Feet on floor now." 5 true
    ;;
  W4:21:30|W5:21:30)
    notify "Night Score" "Score the day. Review the anchor habits honestly." 1 false
    ;;
  W4:22:30|W5:22:30)
    notify "Wind Down" "Night prayer and wind down. Protect the next morning." 1 false
    ;;
  W4:23:15|W5:23:15)
    notify "Bed Check" "Bed check. Screens away." 1 false
    ;;
esac
