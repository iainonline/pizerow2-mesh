# Meshtastic ChatBot Setup Guide

## Overview
This guide explains how to set up and use the LLM-powered chatbot feature in Meshtastic Terminal Monitor.

## What is the ChatBot Feature?

The chatbot feature adds an optional AI assistant that can respond to messages from your mesh network using the TinyLlama language model. When enabled, the bot automatically responds to incoming messages (except keyword commands) with helpful, conversational replies.

### Key Features
- ✅ Responds to messages automatically when enabled
- ✅ Uses TinyLlama 1.1B - runs efficiently on Raspberry Pi 5
- ✅ Only responds to selected target nodes (secure)
- ✅ Keywords still work (STOP, START, FREQ, etc.)
- ✅ Responses limited to 200 characters (Meshtastic compatible)
- ✅ Can be turned on/off remotely via mesh commands
- ✅ Fully open source (Apache 2.0 licensed)

## Requirements

### Hardware
- **Raspberry Pi 5** (8GB recommended, 4GB minimum)
- **Storage**: 1GB free space for model
- **USB**: Meshtastic device connected

### Software
- Python 3.9+
- Virtual environment (recommended)
- Internet connection for initial model download

## Installation Steps

### Step 1: Install LLM Backend

From your Meshtastic directory with virtual environment activated:

```bash
# Activate virtual environment
source venv/bin/activate

# Install llama-cpp-python (builds from source, takes 5-10 minutes)
pip install llama-cpp-python

# Or alternatively, use ctransformers (lighter, faster install)
pip install ctransformers
```

**Note**: `llama-cpp-python` build may take time on Pi5. This is normal!

### Step 2: Download Model

Use the included download utility:

```bash
# Run the download script
python download_model.py
```

Or manually:

```bash
# Create models directory
mkdir -p models

# Download TinyLlama (Q4_K_M quantized, ~670MB)
cd models
wget https://huggingface.co/TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF/resolve/main/tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf

cd ..
```

### Step 3: Test the ChatBot

Test that everything works:

```bash
# Run chatbot test
python mesh_chatbot.py
```

You should see:
- Backend detected
- Model loading (takes 5-10 seconds)
- Test responses generated
- Model unloaded

### Step 4: Configure in Terminal Monitor

The chatbot is now available! It will appear in the main menu once you start the terminal monitor.

## Usage

### Enabling the ChatBot

**Method 1: From Menu**
1. Start mesh terminal: `./start_terminal.sh`
2. Go to menu option for ChatBot Configuration
3. Enable chatbot and set model path
4. Save configuration

**Method 2: Via Mesh Command (Remote)**
From a target node, send the message:
```
CHATBOTON
```

The station will:
- Load the model (~5-10 seconds)
- Enable chatbot mode
- Reply with confirmation: "✅ CHATBOT ENABLED"

### Using the ChatBot

Once enabled, simply send any message (that's not a keyword command) and the bot will respond!

**Example Conversation:**
```
You:  "What's the weather like?"
Bot:  "I don't have real-time weather data, but you can use 
       WEATHERCHECK to get sensor readings from this station!"

You:  "How does mesh networking work?"
Bot:  "Mesh networks allow devices to communicate without 
       infrastructure by relaying messages through multiple nodes."

You:  "STOP"
System: "✅ AUTO-SEND STOPPED"
(Keywords still work normally)
```

### Disabling the ChatBot

**Method 1: From Menu**
1. Access menu (press M during auto-send)
2. Go to ChatBot Configuration
3. Disable chatbot

**Method 2: Via Mesh Command (Remote)**
Send:
```
CHATBOTOFF
```

The station will:
- Unload model and free memory
- Disable chatbot mode  
- Reply with: "✅ CHATBOT DISABLED"

## Keyword Commands

The following commands **always** bypass the chatbot and execute immediately:

- `STOP` - Pause auto-send
- `START` - Resume auto-send
- `FREQ##` - Change frequency (e.g., FREQ60)
- `RADIOCHECK` - Get signal strength
- `WEATHERCHECK` - Get telemetry data
- `KEYWORDS` - List available commands
- `CHATBOTON` - Enable chatbot
- `CHATBOTOFF` - Disable chatbot

## Configuration

ChatBot settings are stored in `terminal_config.json`:

```json
{
  "auto_send_enabled": true,
  "auto_send_interval": 60,
  "selected_nodes": ["!9e757a8c", "!9e761374"],
  "chatbot_enabled": false,
  "chatbot_model_path": "./models/tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf"
}
```

## Performance

### On Raspberry Pi 5

**Model Loading:**
- First load: 5-10 seconds
- Memory usage: ~1GB

**Response Generation:**
- Speed: 2-5 seconds per response
- Varies with message complexity
- Uses 4 CPU cores

**Resource Usage:**
- CPU: High during generation
- RAM: ~1GB when loaded
- Disk: ~670MB for model file

### Tips for Best Performance
- Use powered Pi5 (not battery)
- Ensure adequate cooling
- Don't load other heavy applications
- Consider increasing swap if using 4GB Pi5

## Troubleshooting

### "No LLM backend available"
**Solution:**
```bash
source venv/bin/activate
pip install llama-cpp-python
```

### "Model file not found"
**Solution:**
```bash
python download_model.py
```
Or check the model path in configuration.

### Model won't load
**Possible causes:**
1. Insufficient memory (need 2GB+ free)
2. Corrupted model file (re-download)
3. Wrong model format (must be GGUF)

**Check logs:**
```bash
tail -f mesh_terminal.log
```

### Responses are too slow
**Solutions:**
1. Use Q4_K_M quantization (already default)
2. Reduce context window in `mesh_chatbot.py`
3. Consider Q3 quantization (smaller but less accurate)

### Bot responds to everything
**Check:**
- Is chatbot enabled? (Should only enable when you want it)
- Are you a selected target node?
- Keywords should always bypass chatbot

## Advanced Configuration

### Changing Model Settings

Edit `mesh_chatbot.py`:

```python
# Line ~39-42
self.n_ctx = 512        # Context window (lower = faster)
self.n_threads = 4      # CPU threads (adjust for Pi model)
self.temperature = 0.7  # Creativity (0.0-1.0)
```

### Using Different Models

You can use other GGUF models:

1. Download model to `models/` directory
2. Update model path in configuration
3. Ensure model is GGUF format
4. Smaller models = faster, less capable
5. Larger models = slower, more capable

**Recommended alternatives:**
- `phi-2-Q4_K_M.gguf` (2.7B parameters, ~1.6GB)
- `mistral-7b-instruct-Q4_K_M.gguf` (7B parameters, ~4GB, slow on Pi5)

### Customizing Personality

Edit the system prompt in `mesh_chatbot.py` (line ~130):

```python
system_prompt = (
    "You are a helpful assistant on a mesh radio network. "
    "Keep responses brief (under 200 characters), friendly, and informative. "
    # Add your custom instructions here
)
```

## Security Considerations

### Who Can Use the ChatBot?
- Only **selected target nodes** can trigger chatbot responses
- Non-target nodes are ignored
- Keyword commands only work from target nodes

### Privacy
- All conversations logged to `mesh_terminal.log`
- Messages are encrypted via PKC (firmware 2.5.0+)
- Model runs locally (no cloud/internet)
- No data sent outside your mesh network

### Best Practices
- Only select trusted nodes as targets
- Monitor logs for unexpected behavior
- Keep firmware updated
- Use strong encryption (PKC)

## FAQ

**Q: Does the chatbot work offline?**  
A: Yes! Model runs entirely on your Pi5, no internet needed after download.

**Q: How much does it cost?**  
A: Free! All components are open source.

**Q: Will it drain my battery?**  
A: Yes, significantly. Use with powered Pi5 only.

**Q: Can multiple stations have chatbots?**  
A: Yes! Each station can run its own chatbot independently.

**Q: Does it remember conversations?**  
A: Currently no, each response is independent. Context awareness is a future feature.

**Q: Can I use it with Pi Zero 2 W?**  
A: Not recommended. Insufficient RAM and CPU power. Pi 4/5 only.

**Q: How accurate are the responses?**  
A: TinyLlama is a 1.1B parameter model. Good for simple questions, not an expert system. May occasionally produce incorrect information.

## Uninstalling

To remove chatbot feature:

```bash
# Remove model files
rm -rf models/

# Uninstall Python package
pip uninstall llama-cpp-python

# Remove chatbot module
rm mesh_chatbot.py download_model.py

# Remove from requirements
# (Edit requirements.txt and remove llama-cpp-python line)
```

Your terminal monitor will continue to work without chatbot features.

## Support

**Issues?**
- Check `mesh_terminal.log` for errors
- Review this guide carefully
- Test with `python mesh_chatbot.py`
- Ensure Pi5 has adequate cooling and power

**Not Implemented Yet:**
- This is a feature branch implementation plan
- Full integration pending testing
- See `CHATBOT_IMPLEMENTATION_PLAN.md` for details

## Credits

- **TinyLlama**: Zhang et al. (Apache 2.0)
- **llama.cpp**: Georgi Gerganov (MIT)
- **TheBloke**: For quantized model conversions
- **Meshtastic**: For the mesh networking platform

## License

Apache 2.0 License (same as TinyLlama model)
