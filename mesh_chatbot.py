#!/usr/bin/env python3
"""
Meshtastic ChatBot Module
Integrates TinyLlama LLM for responding to mesh messages
"""
import logging
import os
from typing import Optional
import time

# Try importing llama-cpp-python (primary choice)
try:
    from llama_cpp import Llama
    BACKEND = "llama-cpp-python"
except ImportError:
    try:
        # Fallback to ctransformers
        from ctransformers import AutoModelForCausalLM
        BACKEND = "ctransformers"
    except ImportError:
        BACKEND = None


class MeshChatBot:
    """
    LLM-powered chatbot for Meshtastic mesh network
    Uses TinyLlama for generating responses to messages
    """
    
    def __init__(self, model_path: Optional[str] = None, logger: Optional[logging.Logger] = None):
        """
        Initialize the chatbot
        
        Args:
            model_path: Path to GGUF model file
            logger: Logger instance for debugging
        """
        self.model = None
        self.model_path = model_path or "./models/tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf"
        self.enabled = False
        self.logger = logger or logging.getLogger(__name__)
        self.max_response_length = 200  # Meshtastic message limit
        self.backend = BACKEND
        
        # Performance settings for Pi5
        self.n_ctx = 512  # Context window (keep small for speed)
        self.n_threads = 4  # Use 4 cores on Pi5
        self.temperature = 0.7  # Creativity level
        
        self.logger.info(f"ChatBot initialized with backend: {self.backend}")
        
    def is_available(self) -> bool:
        """Check if LLM backend is available"""
        return self.backend is not None
    
    def is_loaded(self) -> bool:
        """Check if model is loaded"""
        return self.model is not None
    
    def model_exists(self) -> bool:
        """Check if model file exists"""
        return os.path.exists(self.model_path)
    
    def load_model(self) -> bool:
        """
        Load the TinyLlama model
        
        Returns:
            True if successful, False otherwise
        """
        if not self.is_available():
            self.logger.error(f"No LLM backend available. Install llama-cpp-python or ctransformers")
            return False
            
        if not self.model_exists():
            self.logger.error(f"Model file not found: {self.model_path}")
            return False
        
        try:
            self.logger.info(f"Loading model from {self.model_path}...")
            start_time = time.time()
            
            if self.backend == "llama-cpp-python":
                self.model = Llama(
                    model_path=self.model_path,
                    n_ctx=self.n_ctx,
                    n_threads=self.n_threads,
                    verbose=False
                )
            elif self.backend == "ctransformers":
                self.model = AutoModelForCausalLM.from_pretrained(
                    self.model_path,
                    model_type="llama",
                    context_length=self.n_ctx,
                    threads=self.n_threads
                )
            
            load_time = time.time() - start_time
            self.logger.info(f"Model loaded successfully in {load_time:.1f}s")
            self.enabled = True
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to load model: {e}")
            self.model = None
            self.enabled = False
            return False
    
    def unload_model(self):
        """Unload model and free memory"""
        if self.model:
            self.logger.info("Unloading model...")
            self.model = None
            self.enabled = False
            self.logger.info("Model unloaded, memory freed")
    
    def _format_prompt(self, user_message: str) -> str:
        """
        Format message in TinyLlama chat format
        
        Args:
            user_message: User's message
            
        Returns:
            Formatted prompt for the model
        """
        # TinyLlama chat format
        system_prompt = (
            "You are a helpful assistant on a mesh radio network. "
            "Keep responses brief (under 200 characters), friendly, and informative. "
            "You are helping users with questions about their mesh network, devices, or general topics."
        )
        
        prompt = f"""<|system|>
{system_prompt}</s>
<|user|>
{user_message}</s>
<|assistant|>
"""
        return prompt
    
    def generate_response(self, message: str, context: Optional[str] = None, timeout: int = 30) -> Optional[str]:
        """
        Generate a response to a message
        
        Args:
            message: Incoming message to respond to
            context: Optional conversation context
            timeout: Maximum time to generate (seconds)
            
        Returns:
            Generated response string, or None on error
        """
        if not self.enabled or not self.model:
            self.logger.warning("ChatBot not enabled or model not loaded")
            return None
        
        try:
            self.logger.info(f"Generating response to: {message[:50]}...")
            start_time = time.time()
            
            # Format prompt
            prompt = self._format_prompt(message)
            
            # Generate response
            if self.backend == "llama-cpp-python":
                output = self.model(
                    prompt,
                    max_tokens=100,  # Keep responses short
                    temperature=self.temperature,
                    stop=["</s>", "<|", "\n\n"],  # Stop tokens
                    echo=False
                )
                response = output['choices'][0]['text'].strip()
                
            elif self.backend == "ctransformers":
                response = self.model(
                    prompt,
                    max_new_tokens=100,
                    temperature=self.temperature,
                    stop=["</s>", "<|", "\n\n"]
                ).strip()
            
            # Truncate to Meshtastic limit
            if len(response) > self.max_response_length:
                response = response[:self.max_response_length-3] + "..."
            
            gen_time = time.time() - start_time
            self.logger.info(f"Generated response in {gen_time:.1f}s: {response[:50]}...")
            
            return response
            
        except Exception as e:
            self.logger.error(f"Error generating response: {e}")
            return None
    
    def get_status(self) -> dict:
        """
        Get chatbot status information
        
        Returns:
            Dictionary with status details
        """
        return {
            'backend': self.backend,
            'available': self.is_available(),
            'loaded': self.is_loaded(),
            'enabled': self.enabled,
            'model_path': self.model_path,
            'model_exists': self.model_exists()
        }


# Test function for standalone testing
def test_chatbot():
    """Test the chatbot functionality"""
    print("=== MeshChatBot Test ===")
    
    # Initialize
    chatbot = MeshChatBot()
    
    # Check availability
    print(f"\nBackend: {chatbot.backend}")
    print(f"Available: {chatbot.is_available()}")
    print(f"Model exists: {chatbot.model_exists()}")
    
    if not chatbot.is_available():
        print("\n❌ No LLM backend available!")
        print("Install with: pip install llama-cpp-python")
        return
    
    if not chatbot.model_exists():
        print(f"\n❌ Model not found: {chatbot.model_path}")
        print("Download with:")
        print("  mkdir -p models")
        print("  cd models")
        print("  wget https://huggingface.co/TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF/resolve/main/tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf")
        return
    
    # Load model
    print("\nLoading model...")
    if chatbot.load_model():
        print("✅ Model loaded successfully")
        
        # Test messages
        test_messages = [
            "Hello, how are you?",
            "What is a mesh network?",
            "Tell me about Meshtastic"
        ]
        
        for msg in test_messages:
            print(f"\n📩 User: {msg}")
            response = chatbot.generate_response(msg)
            if response:
                print(f"🤖 Bot: {response}")
            else:
                print("❌ No response generated")
        
        # Unload
        chatbot.unload_model()
        print("\n✅ Model unloaded")
    else:
        print("❌ Failed to load model")


if __name__ == "__main__":
    # Setup logging for standalone test
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    test_chatbot()
