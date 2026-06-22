#!/bin/bash
# Focus Companion — runs when the agent FINISHES thinking.
# Plays a soft chime and brings the Claude window back to the front,
# so you snap straight back instead of drifting into the feed.

# soft chime (any of these system sounds works — swap if you like)
afplay /System/Library/Sounds/Glass.aiff >/dev/null 2>&1 &

# bring the agent window forward.
# If your agent runs somewhere else, change "Claude" to that app's name
# (e.g. "Google Chrome", "Terminal", "Cursor").
osascript -e 'tell application "Claude" to activate' >/dev/null 2>&1

exit 0
