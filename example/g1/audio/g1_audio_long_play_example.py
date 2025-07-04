import sys
import os
import time
import wave
import datetime
from unitree_sdk2py.core.channel import ChannelFactoryInitialize
from unitree_sdk2py.g1.audio.g1_audio_client import AudioClient

"""
Example: python3 g1_audio_long_play_example.py <networkInterface> [chunk_ms]

Plays the file "OVERTAKEN_16k_mono.wav" located in the same directory as this
script.  The audio is sent to the robot in small chunks so that very large
files (minutes long) can be streamed without hitting the RPC payload limit.

Parameters
----------
networkInterface : str
    Network interface name (e.g. "eno1", "wlan0") used to reach the robot.
chunk_ms : int, optional
    Length of each audio chunk in milliseconds.  Defaults to 1000 ms (1 s).
"""

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def read_wave(file_path: str):
    """Read a 16-kHz / 16-bit PCM mono WAV file.

    Returns
    -------
    bytes
        Raw PCM bytes.
    int
        Sample rate (should be 16000).
    int
        Number of channels (should be 1).
    int
        Number of frames (samples).
    """
    with wave.open(file_path, "rb") as wf:
        sample_rate = wf.getframerate()
        num_channels = wf.getnchannels()
        n_frames = wf.getnframes()
        pcm_bytes = wf.readframes(n_frames)
    return pcm_bytes, sample_rate, num_channels, n_frames


def main():
    if len(sys.argv) < 2:
        print(f"Usage: python3 {sys.argv[0]} <networkInterface> [chunk_ms]")
        sys.exit(-1)

    net_if = sys.argv[1]
    chunk_ms = int(sys.argv[2]) if len(sys.argv) > 2 else 1000  # default 1 s

    # -------------------------------------------------------------------
    # Initialise SDK
    # -------------------------------------------------------------------
    ChannelFactoryInitialize(0, net_if)

    audio_client = AudioClient()
    audio_client.SetTimeout(10.0)
    audio_client.Init()

    # -------------------------------------------------------------------
    # Load audio file
    # -------------------------------------------------------------------
    audio_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "OVERTAKEN_16k_mono.wav")
    if not os.path.isfile(audio_file):
        print(f"Audio file not found: {audio_file}")
        sys.exit(-1)

    pcm_bytes, sample_rate, num_channels, n_frames = read_wave(audio_file)

    if sample_rate != 16000 or num_channels != 1:
        print("Error: WAV must be 16-kHz mono PCM!")
        sys.exit(-1)

    print(f"Loaded {audio_file}")
    total_duration = n_frames / sample_rate
    print(f"Duration: {total_duration:.2f} s")

    # -------------------------------------------------------------------
    # Prepare chunking parameters
    # -------------------------------------------------------------------
    bytes_per_sample = 2  # 16-bit PCM
    bytes_per_sec = sample_rate * bytes_per_sample  # 32 kB
    chunk_bytes = int(bytes_per_sec * (chunk_ms / 1000.0))

    if chunk_bytes <= 0:
        print("chunk_ms too small!")
        sys.exit(-1)

    # -------------------------------------------------------------------
    # Stream audio
    # -------------------------------------------------------------------
    start_ts = int(time.time() * 1000)
    stream_id = str(start_ts)  # keep the same stream id for all chunks

    num_chunks = (len(pcm_bytes) + chunk_bytes - 1) // chunk_bytes

    print(f"Streaming in {num_chunks} chunks of {chunk_ms} ms …")

    start_wall = time.time()

    for idx in range(num_chunks):
        offset = idx * chunk_bytes
        buf = pcm_bytes[offset: offset + chunk_bytes]
        if not buf:
            break

        # Convert to list[int] as required by PlayStream
        pcm_list = list(buf)

        # Send chunk – use constant stream_id so robot recognises it as one stream
        ret = audio_client.PlayStream("longplay", stream_id, pcm_list)
        if ret != 0:
            print(f"PlayStream error at chunk {idx}: code={ret}")
            break

        # Accurate pacing – wait until (idx+1)*chunk_duration since start
        chunk_duration = len(buf) / bytes_per_sec  # normally 1-s or user chosen
        next_target = start_wall + (idx + 1) * chunk_duration
        sleep_time = next_target - time.time()
        if sleep_time > 0:
            time.sleep(sleep_time)

    print("Finished streaming.  Sending PlayStop …")
    audio_client.PlayStop("longplay")


if __name__ == "__main__":
    main() 