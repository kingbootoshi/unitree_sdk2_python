import time
import sys
import struct
import wave
from unitree_sdk2py.core.channel import ChannelFactoryInitialize
from unitree_sdk2py.g1.audio.g1_audio_client import AudioClient


class AudioRecorder:
    """Helper class to record raw audio stream to a WAV file."""
    
    def __init__(self, filename="recording.wav", sample_rate=16000, channels=1, sample_width=2):
        self.filename = filename
        self.sample_rate = sample_rate
        self.channels = channels
        self.sample_width = sample_width
        self.audio_data = bytearray()
        self.packet_count = 0
        
    def add_audio_data(self, data: bytes):
        """Add raw audio data to the buffer."""
        self.audio_data.extend(data)
        self.packet_count += 1
        
    def save_to_file(self):
        """Save the recorded audio to a WAV file."""
        with wave.open(self.filename, 'wb') as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(self.sample_width)
            wf.setframerate(self.sample_rate)
            wf.writeframes(self.audio_data)
        print(f"Audio saved to {self.filename}")


def analyze_audio_packet(data: bytes):
    """Analyze raw audio packet and print statistics."""
    # Convert bytes to 16-bit signed integers
    samples = struct.unpack(f"{len(data)//2}h", data)
    
    # Calculate statistics
    max_val = max(samples) if samples else 0
    min_val = min(samples) if samples else 0
    avg_val = sum(samples) / len(samples) if samples else 0
    
    # Simple volume indicator (RMS)
    rms = int((sum(s**2 for s in samples) / len(samples)) ** 0.5) if samples else 0
    volume_bar = "#" * min(50, rms // 100)
    
    return len(samples), max_val, min_val, avg_val, volume_bar


def main():
    if len(sys.argv) < 2:
        print(f"Usage: python3 {sys.argv[0]} networkInterface [record]")
        print("  networkInterface: Network interface name (e.g., eth0)")
        print("  record: Optional flag to record audio to file")
        sys.exit(-1)

    # Initialize the channel factory
    ChannelFactoryInitialize(0, sys.argv[1])
    
    # Create audio client
    audio_client = AudioClient()
    audio_client.SetTimeout(10.0)
    audio_client.Init()
    
    # Check if recording is requested
    record_audio = len(sys.argv) > 2 and sys.argv[2].lower() == "record"
    recorder = AudioRecorder() if record_audio else None
    
    # Statistics
    total_packets = 0
    total_bytes = 0
    start_time = time.time()
    
    def audio_callback(data: bytes):
        """Callback function for processing raw audio data."""
        nonlocal total_packets, total_bytes
        
        total_packets += 1
        total_bytes += len(data)
        
        # Analyze the audio packet
        num_samples, max_val, min_val, avg_val, volume_bar = analyze_audio_packet(data)
        
        # Print statistics every 10th packet to avoid flooding console
        if total_packets % 10 == 0:
            elapsed = time.time() - start_time
            print(f"\rPackets: {total_packets} | "
                  f"Time: {elapsed:.1f}s | "
                  f"Data rate: {total_bytes/elapsed/1024:.1f} KB/s | "
                  f"Volume: {volume_bar}", end="", flush=True)
        
        # Record if requested
        if recorder:
            recorder.add_audio_data(data)
    
    try:
        print("Starting raw microphone listener...")
        print("Audio format: 16-bit PCM, 16kHz, Mono")
        print("Press Ctrl+C to stop\n")
        
        # Start the raw microphone listener
        audio_client.StartRawMicListener(audio_callback)
        
        # Keep the program running
        while True:
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        print("\n\nStopping microphone listener...")
        
        # Stop the listener
        audio_client.StopRawMicListener()
        
        # Save recording if enabled
        if recorder and recorder.audio_data:
            print(f"\nRecorded {recorder.packet_count} packets")
            print(f"Total audio data: {len(recorder.audio_data)} bytes")
            print(f"Duration: {len(recorder.audio_data) / (16000 * 2):.2f} seconds")
            recorder.save_to_file()
        
        # Print final statistics
        elapsed = time.time() - start_time
        print(f"\nFinal statistics:")
        print(f"  Total packets: {total_packets}")
        print(f"  Total data: {total_bytes / 1024:.1f} KB")
        print(f"  Duration: {elapsed:.1f} seconds")
        print(f"  Average data rate: {total_bytes/elapsed/1024:.1f} KB/s")


if __name__ == "__main__":
    main()