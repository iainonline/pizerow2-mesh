#!/usr/bin/env python3
"""
Model Download Utility for Meshtastic ChatBot
Downloads TinyLlama model for chatbot functionality
"""
import os
import sys
import urllib.request
from pathlib import Path

MODEL_INFO = {
    'name': 'TinyLlama-1.1B-Chat-v1.0 (Q4_K_M)',
    'url': 'https://huggingface.co/TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF/resolve/main/tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf',
    'filename': 'tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf',
    'size': '669 MB',
    'license': 'Apache 2.0'
}


def download_with_progress(url, destination):
    """Download file with progress bar"""
    
    def report_progress(block_num, block_size, total_size):
        downloaded = block_num * block_size
        percent = min(downloaded * 100 / total_size, 100)
        mb_downloaded = downloaded / (1024 * 1024)
        mb_total = total_size / (1024 * 1024)
        
        bar_length = 50
        filled = int(bar_length * percent / 100)
        bar = '=' * filled + '-' * (bar_length - filled)
        
        sys.stdout.write(f'\r[{bar}] {percent:.1f}% ({mb_downloaded:.1f}/{mb_total:.1f} MB)')
        sys.stdout.flush()
    
    print(f"Downloading {os.path.basename(destination)}...")
    print(f"URL: {url}")
    print()
    
    urllib.request.urlretrieve(url, destination, report_progress)
    print("\n✅ Download complete!")


def main():
    """Main download function"""
    print("=" * 70)
    print("  MESHTASTIC CHATBOT - MODEL DOWNLOAD UTILITY")
    print("=" * 70)
    print()
    print(f"Model: {MODEL_INFO['name']}")
    print(f"Size: {MODEL_INFO['size']}")
    print(f"License: {MODEL_INFO['license']}")
    print()
    
    # Create models directory
    models_dir = Path(__file__).parent / "models"
    models_dir.mkdir(exist_ok=True)
    
    model_path = models_dir / MODEL_INFO['filename']
    
    # Check if already exists
    if model_path.exists():
        print(f"⚠️  Model already exists at: {model_path}")
        response = input("\nDownload again? (yes/no): ").strip().lower()
        if response != 'yes':
            print("Cancelled.")
            return
        print()
    
    # Confirm download
    print(f"Download destination: {model_path}")
    print()
    response = input("Start download? (yes/no): ").strip().lower()
    
    if response != 'yes':
        print("Cancelled.")
        return
    
    print()
    
    try:
        # Download
        download_with_progress(MODEL_INFO['url'], str(model_path))
        
        print()
        print("=" * 70)
        print("  DOWNLOAD SUCCESSFUL")
        print("=" * 70)
        print()
        print(f"Model saved to: {model_path}")
        print(f"File size: {model_path.stat().st_size / (1024*1024):.1f} MB")
        print()
        print("Next steps:")
        print("  1. Enable chatbot in terminal configuration")
        print("  2. Send CHATBOTON from a target node")
        print("  3. Start chatting!")
        print()
        
    except KeyboardInterrupt:
        print("\n\n❌ Download cancelled by user")
        if model_path.exists():
            print(f"Removing incomplete file: {model_path}")
            model_path.unlink()
    except Exception as e:
        print(f"\n\n❌ Download failed: {e}")
        if model_path.exists():
            print(f"Removing incomplete file: {model_path}")
            model_path.unlink()


if __name__ == "__main__":
    main()
