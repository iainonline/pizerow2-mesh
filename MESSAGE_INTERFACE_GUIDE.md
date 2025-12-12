# Message Interface Feature Guide

## Overview
The message interface provides a complete messaging system for your Meshtastic terminal, allowing you to send and receive messages from the Raspberry Pi.

## Accessing the Message Interface

From the main dashboard, press **S** to open the message interface.

```
💡 Press (M) for Menu | (S) to Send Message | Ctrl+C to Exit
```

## Features

### 1. Node List View
When you press 'S', you'll see a list of all available nodes:

```
================================================================================
    💬 MESSAGE INTERFACE
================================================================================

📱 NODES:
--------------------------------------------------------------------------------
  1. Yang     Yang's Meshtastic         (2 msgs) ⭐
  2. Ying     Ying's Device              (5 msgs) ⭐
  3. WDZ3     Neighbor Node              (0 msgs)
  4. PlcS     Another Node               (1 msgs)
--------------------------------------------------------------------------------

Options:
  [Number] - View conversation with node
  [N]      - Send message to new node
  [B]      - Back to dashboard
```

- **Message counts** show how many messages you've exchanged with each node
- **⭐ Star indicator** shows your target/favorite nodes
- **Node names** display both short and long names

### 2. Conversation View
Select a node number to view the full conversation:

```
================================================================================
    💬 CONVERSATION WITH: Yang (Yang's Meshtastic)
================================================================================

📝 MESSAGE HISTORY:
--------------------------------------------------------------------------------
[14:23:15] 📥 Yang (SNR:6.2): Hello from the mesh!
[14:24:01] 📤 You: Hi Yang! Testing the new interface
[14:25:30] 📥 Yang (SNR:6.5): Great to hear from you
[14:26:15] 📤 You: Signal looks good today
--------------------------------------------------------------------------------

📡 Last heard: 2m ago
📶 Signal: SNR 6.5dB, RSSI -41dBm

Options:
  [R] - Send Reply
  [C] - Clear conversation history
  [B] - Back to node list
```

Features:
- **Last 20 messages** displayed per conversation
- **Timestamps** for every message
- **Signal quality** shown for received messages (SNR/RSSI)
- **Direction indicators**: 📥 received, 📤 sent
- **Node status**: Last heard time and current signal strength

### 3. Sending Messages

#### Send Reply (from conversation view)
Press **R** to reply in an active conversation:

```
📝 Message to Yang (max 200 chars, or 'cancel' to abort):
> Your message here
✅ Message sent to Yang
```

#### Send to New Node
From the node list, press **N** to send to any node:

```
Available nodes:
  1. Yang
  2. Ying
  3. WDZ3

Select node number (or B to go back): 1

📝 Message to Yang (max 200 chars, or 'cancel' to abort):
> Your message here
✅ Message sent to Yang
```

### 4. Message Management

#### Clear Conversation
From any conversation view, press **C** to clear the message history:

```
Clear all messages with this node? (yes/no): yes
✅ Conversation cleared
```

This removes the message history locally but doesn't affect messages stored on the mesh devices.

## Message Features

### Automatic Tracking
- All received messages are automatically added to conversations
- Sent messages are tracked with timestamps
- Signal quality (SNR/RSSI) recorded for received messages
- Messages appear in both the conversation view and the dashboard's "RECENT MESSAGES" panel

### Message Limits
- **Maximum message length**: 200 characters
- Messages longer than 200 chars are automatically truncated
- Last **20 messages** shown per conversation
- **10 messages** shown in dashboard panel

### Integration with Dashboard
- Sent messages appear in "RECENT ACTIVITY" feed
- New received messages show in "RECENT MESSAGES" panel
- Message statistics tracked in packet counts

## Navigation Tips

1. **Quick Send**: Press 'S' from dashboard, select node, type message
2. **View History**: Press 'S', select node number to see full conversation
3. **Reply Fast**: From conversation view, press 'R' to reply immediately
4. **Return Anytime**: Press 'B' to go back to previous screen
5. **Dashboard**: After sending, you return to the conversation view automatically

## Use Cases

### 1. Quick Status Check
```
S → 1 → R → "Status?" → Enter
```

### 2. Send to Multiple Nodes
```
S → 1 → R → "Message 1" → B → 2 → R → "Message 2" → B → B
```

### 3. Review Conversation History
```
S → 1 → (scroll through last 20 messages) → B
```

### 4. Clean Up Old Messages
```
S → 1 → C → yes → B
```

## Technical Details

### Message Storage
- **In-memory storage**: Conversations stored in RAM (lost on restart)
- **Per-node organization**: Each node has separate conversation thread
- **Direction tracking**: Sent vs received messages clearly marked
- **Signal data**: SNR and RSSI captured for received messages

### Message Flow
1. **Outgoing**: You type → Interface validates → Sends to mesh → Logs to conversation
2. **Incoming**: Mesh receives → Packet handler processes → Adds to conversation → Shows on dashboard

### Acknowledgments
- Messages sent with `wantAck=True` for delivery confirmation
- ACK/NAK tracking separate from conversation storage
- Packet statistics updated for all messages

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| **S** | Open message interface (from dashboard) |
| **M** | Open menu (from dashboard) |
| **B** | Back to previous screen |
| **R** | Reply to current conversation |
| **N** | Send to new node |
| **C** | Clear conversation |
| **Ctrl+C** | Exit program |

## Example Workflow

### Morning Check-In
1. Start terminal: `./start_terminal.sh`
2. Wait for dashboard to load
3. Press **S** to open messages
4. Check for new messages (numbers next to nodes)
5. Select node with messages to read
6. Press **R** to reply if needed
7. Press **B** twice to return to dashboard

### Send Status Update
1. From dashboard, press **S**
2. Press **N** for new message
3. Select target node (e.g., 1)
4. Type: "Battery 85%, all good here"
5. Message sent and logged
6. Return to dashboard automatically

## Tips & Best Practices

1. **Keep messages concise**: 200 char limit encourages brief, clear communication
2. **Check signal**: View conversation to see signal quality before sending
3. **Use short names**: Node short names (4-8 chars) make identification easier
4. **Regular cleanup**: Clear old conversations periodically to reduce clutter
5. **Target nodes**: Star (⭐) indicates frequently-used nodes from auto-send config

## Troubleshooting

### "No nodes available"
- Wait for mesh to discover nodes
- Check Meshtastic device connection
- Verify nodes are online and in range

### Message not sending
- Check connection status on dashboard
- Verify target node is online (Last heard time)
- Check signal strength (low SNR/RSSI may cause failures)

### Messages not appearing
- Ensure receiving node has correct channel config
- Check encryption settings match
- Verify firmware compatibility (2.5.0+ recommended)

## Future Enhancements (Planned)

- Persistent message storage (save to disk)
- Message search/filter
- Bulk message operations
- Message export to file
- Custom message templates
- Scheduled messages
- Group messaging support
- Message priority flags
- Delivery status indicators

## Related Features

- **Auto-send telemetry**: Separate from manual messaging
- **Keyword commands**: STOP/START/FREQ## still work
- **Activity feed**: Shows all packet activity including messages
- **Node tracking**: Signal and online status for all nodes
