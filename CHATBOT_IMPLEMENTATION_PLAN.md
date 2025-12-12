# LLM Chatbot Feature Implementation Plan

## Overview
Add an optional LLM chatbot feature to the Meshtastic Terminal Monitor that responds to incoming messages using Tiny LLama.

## Architecture Design

### 1. Chatbot Control
- **Keywords**: `CHATBOTON` and `CHATBOTOFF` to enable/disable
- **State Persistence**: Save chatbot state in `terminal_config.json`
- **Scope**: Only responds to messages from selected target nodes
- **Safety**: Keywords take precedence over chatbot responses

### 2. Message Flow
```
Incoming Message
    ├─> Check if from target node
    ├─> Check if keyword command
    │   └─> Execute keyword (STOP, START, FREQ, etc.)
    └─> If chatbot enabled AND not keyword
        ├─> Pass to LLM
        ├─> Generate response
        └─> Send as Direct Message
```

### 3. Technical Stack (Pi5 Compatible)

#### Option A: llama-cpp-python (RECOMMENDED)
- **Library**: `llama-cpp-python`
- **Model Format**: GGUF (quantized)
- **Model**: TinyLlama-1.1B-Chat-v1.0-GGUF
- **Quantization**: Q4_K_M (4-bit, ~700MB)
- **Performance**: Fast inference on Pi5 CPU
- **Installation**: Builds C++ bindings from source

#### Option B: ctransformers
- **Library**: `ctransformers`
- **Model Format**: GGUF
- **Same models as Option A**
- **Pre-built wheels available**

### 4. Model Selection
**TinyLlama-1.1B-Chat-v1.0** (Recommended for Pi5)
- Size: ~700MB (Q4_K_M quantization)
- Speed: 2-5 tokens/sec on Pi5
- Memory: ~1GB RAM usage
- License: Apache 2.0 (fully open source)
- Model Hub: https://huggingface.co/TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF

### 5. Implementation Components

#### A. ChatBot Class (`mesh_chatbot.py`)
```python
class MeshChatBot:
    def __init__(self, model_path=None):
        self.model = None
        self.model_path = model_path
        self.enabled = False
        self.max_response_length = 200  # Meshtastic limit
        
    def load_model(self):
        # Load TinyLlama GGUF model
        
    def unload_model(self):
        # Free memory when disabled
        
    def generate_response(self, message, context=None):
        # Generate response with proper prompt format
        # Trim to 200 chars for Meshtastic
        
    def is_loaded(self):
        # Check if model is ready
```

#### B. Integration Points in `mesh_terminal.py`
1. Add chatbot instance to `MeshtasticTerminal.__init__`
2. Add `chatbot_enabled` to config
3. Add keyword handlers for CHATBOTON/CHATBOTOFF
4. Modify `on_receive` to pass non-keyword messages to chatbot
5. Add menu option to configure chatbot settings
6. Add model download/setup utility

#### C. Configuration (`terminal_config.json`)
```json
{
  "auto_send_enabled": true,
  "auto_send_interval": 60,
  "selected_nodes": ["!9e757a8c"],
  "chatbot_enabled": false,
  "chatbot_model_path": "./models/tinyllama-1.1b-chat-q4_k_m.gguf"
}
```

### 6. Installation Steps

#### Model Download
```bash
# Create models directory
mkdir -p ~/Meshtastic/models

# Download TinyLlama GGUF (Q4_K_M quantization)
cd ~/Meshtastic/models
wget https://huggingface.co/TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF/resolve/main/tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf
```

#### Python Dependencies
```bash
# Install llama-cpp-python (builds from source on Pi5)
pip install llama-cpp-python

# Or use ctransformers (lighter)
pip install ctransformers
```

### 7. User Flow

#### Enabling Chatbot
1. Download model (one-time setup)
2. Configure model path in menu
3. Target node sends `CHATBOTON`
4. System loads model and enables chatbot
5. Confirmation sent: "✅ CHATBOT ENABLED"

#### Using Chatbot
1. Target node sends regular message (not keyword)
2. Message passed to LLM
3. LLM generates response (max 200 chars)
4. Response sent as Direct Message
5. Conversation logged

#### Disabling Chatbot
1. Target node sends `CHATBOTOFF`
2. System unloads model and disables chatbot
3. Confirmation sent: "✅ CHATBOT DISABLED"
4. Memory freed

### 8. Safety Features
- **Keyword Priority**: All existing keywords bypass chatbot
- **Target Node Only**: Only responds to selected target nodes
- **Response Length**: Hard limit at 200 characters
- **Timeout**: 30-second timeout for LLM generation
- **Error Handling**: Graceful fallback on model errors
- **Memory Management**: Unload model when disabled

### 9. Performance Considerations
- **First Load**: 5-10 seconds to load model
- **Response Time**: 2-5 seconds per message (Pi5)
- **Memory Usage**: ~1GB when active
- **Battery Impact**: High CPU usage during generation
- **Recommendation**: Use with powered Pi5, not battery

### 10. Testing Plan
1. Test model loading/unloading
2. Test CHATBOTON/CHATBOTOFF keywords
3. Test response generation with various inputs
4. Test 200-char truncation
5. Test keyword priority (keywords always work)
6. Test memory usage over time
7. Test with multiple consecutive messages
8. Test graceful degradation on errors

### 11. Future Enhancements
- Context awareness (remember last N messages)
- Personality customization via system prompt
- Multiple model support
- Response caching for common queries
- Temperature/creativity controls

## Implementation Phases

### Phase 1: Core Infrastructure (This Branch)
- Create `mesh_chatbot.py` module
- Integrate llama-cpp-python
- Add basic load/unload functionality
- Add CHATBOTON/CHATBOTOFF keywords
- Update configuration handling

### Phase 2: Response Generation
- Implement message routing to chatbot
- Add prompt engineering for TinyLlama format
- Implement response truncation
- Add response sending via DM

### Phase 3: Menu & Configuration
- Add chatbot configuration menu
- Add model path configuration
- Add download helper script
- Update documentation

### Phase 4: Testing & Optimization
- Performance testing on Pi5
- Memory optimization
- Error handling improvements
- Documentation completion

## Files to Create/Modify

### New Files
- `mesh_chatbot.py` - ChatBot class implementation
- `download_model.py` - Model download utility
- `CHATBOT_SETUP.md` - User setup guide

### Modified Files
- `mesh_terminal.py` - Integration points
- `terminal_config.json` - Add chatbot config
- `requirements.txt` - Add llama-cpp-python
- `README.md` - Document chatbot feature

## Command Reference

### New Keywords
- `CHATBOTON` - Enable chatbot (loads model)
- `CHATBOTOFF` - Disable chatbot (unloads model)

### Existing Keywords (Unchanged)
- `STOP`, `START`, `FREQ##`, `RADIOCHECK`, `WEATHERCHECK`, `KEYWORDS`

## Resource Requirements

### Disk Space
- Model file: ~700MB
- Python packages: ~200MB
- Total: ~1GB

### Memory
- Base system: ~500MB
- Model loaded: ~1GB
- Peak usage: ~1.5GB
- Recommended: 4GB+ RAM (Pi5 has 8GB)

### CPU
- Model loading: 5-10 seconds
- Response generation: 2-5 seconds per message
- Impact: High during generation, idle when not responding

## License Compliance
- **TinyLlama**: Apache 2.0 License ✅
- **llama-cpp-python**: MIT License ✅
- **ctransformers**: MIT License ✅
- **All dependencies**: Open source ✅

## Questions to Address
1. Should chatbot have conversation context (memory)?
2. Should chatbot work for all nodes or only target nodes?
3. Should there be a rate limit on responses?
4. Should responses be logged separately?
5. Should there be a "personality" configuration?

## Current Decision: Keep It Simple
- No conversation context (stateless)
- Only target nodes (security)
- No explicit rate limit (mesh natural rate limits)
- Use existing logging
- Simple helpful personality via system prompt

## Next Steps
1. ✅ Create feature branch
2. ✅ Document implementation plan
3. ⏳ Create mesh_chatbot.py module
4. ⏳ Add llama-cpp-python to requirements
5. ⏳ Implement model loading
6. ⏳ Add keyword handlers
7. ⏳ Integrate message routing
8. ⏳ Test on Pi5
9. ⏳ Document setup process
10. ⏳ Merge to main when stable
