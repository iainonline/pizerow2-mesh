#!/bin/bash
# Launch terminal maximized using xdotool

# Start the terminal with large geometry
lxterminal --geometry=240x60 -e /home/iain/Meshtastic/start_terminal.sh &
TERM_PID=$!

# Wait for window to appear
sleep 1

# Find and maximize the window
WINDOW_ID=$(xdotool search --pid $TERM_PID --class lxterminal 2>/dev/null | head -1)

if [ -n "$WINDOW_ID" ]; then
    # Activate and maximize the window
    xdotool windowactivate $WINDOW_ID
    xdotool key --window $WINDOW_ID F11
fi
