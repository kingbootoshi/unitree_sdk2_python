import sys
import time

from unitree_sdk2py.core.channel import ChannelFactoryInitialize
from unitree_sdk2py.g1.audio.g1_audio_client import AudioClient


def asr_callback(msg: dict):
    """Print ASR result in a human-friendly format."""
    try:
        index = msg.get("index")
        text = msg.get("text")
        confidence = msg.get("confidence")
        is_final = msg.get("is_final")
        print(f"[ASR] #{index}: '{text}' (conf={confidence:.2f}, final={is_final})")
    except Exception:
        # Fallback for raw messages
        print(f"[ASR] Raw message: {msg}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: python3 {sys.argv[0]} <networkInterface>")
        sys.exit(-1)

    # Initialize DDS communication
    ChannelFactoryInitialize(0, sys.argv[1])

    # Instantiate AudioClient
    audio_client = AudioClient()
    audio_client.SetTimeout(10.0)
    audio_client.Init()

    # Start ASR listener
    audio_client.StartAsrListener(asr_callback, queueLen=100)
    print("ASR listener started. Press Ctrl+C to exit.")

    # Keep the script alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        audio_client.StopAsrListener() 