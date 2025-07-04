import json
import socket
import struct
import threading
from typing import List, Callable, Optional

from ...rpc.client import Client
from .g1_audio_api import *
from ...core.channel import ChannelSubscriber
from ...idl.std_msgs.msg.dds_ import String_  # DDS String message for ASR results

"""
" class SportClient
"""
class AudioClient(Client):
    def __init__(self):
        super().__init__(AUDIO_SERVICE_NAME, False)
        self.tts_index = 0
        # ASR subscriber will be created lazily when StartAsrListener is called
        self.__asr_subscriber: ChannelSubscriber | None = None
        # Raw microphone listener state
        self.__mic_socket: Optional[socket.socket] = None
        self.__mic_listener_thread: Optional[threading.Thread] = None
        self.__mic_listener_stop_event: Optional[threading.Event] = None

    def Init(self):
        # set api version
        self._SetApiVerson(AUDIO_API_VERSION)

        # regist api
        self._RegistApi(ROBOT_API_ID_AUDIO_TTS, 0)
        self._RegistApi(ROBOT_API_ID_AUDIO_ASR, 0)
        self._RegistApi(ROBOT_API_ID_AUDIO_START_PLAY, 0)
        self._RegistApi(ROBOT_API_ID_AUDIO_STOP_PLAY, 0)
        self._RegistApi(ROBOT_API_ID_AUDIO_GET_VOLUME, 0)
        self._RegistApi(ROBOT_API_ID_AUDIO_SET_VOLUME, 0) 
        self._RegistApi(ROBOT_API_ID_AUDIO_SET_RGB_LED, 0) 

    ## API Call ##
    def TtsMaker(self, text: str, speaker_id: int):
        self.tts_index += self.tts_index
        p = {}
        p["index"] = self.tts_index
        p["text"] = text
        p["speaker_id"] = speaker_id
        parameter = json.dumps(p)
        code, data = self._Call(ROBOT_API_ID_AUDIO_TTS, parameter)
        return code

    def GetVolume(self):
        p = {}
        parameter = json.dumps(p)
        code, data = self._Call(ROBOT_API_ID_AUDIO_GET_VOLUME, parameter)
        if code == 0 and data is not None:
            return code, json.loads(data)
        else:
            return code, None

    def SetVolume(self, volume: int):
        p = {}
        p["volume"] = volume
        # p["name"] = 'volume'
        parameter = json.dumps(p)
        code, data = self._Call(ROBOT_API_ID_AUDIO_SET_VOLUME, parameter)
        return code

    def PlayStream(self, app_name: str, stream_id: str, pcm_data: List[int]):
        p = {}
        p["app_name"] = app_name
        p["stream_id"] = stream_id
        parameter = json.dumps(p)
        code, data = self._CallData(ROBOT_API_ID_AUDIO_START_PLAY, parameter, pcm_data)
        return code
    
    def PlayStop(self, app_name: str):
        p = {}
        p["app_name"] = app_name
        parameter = json.dumps(p)
        code, data = self._Call(ROBOT_API_ID_AUDIO_STOP_PLAY, parameter)
        return code

    def LedControl(self, R: int, G: int, B: int):
        p = {}
        p["R"] = R
        p["G"] = G
        p["B"] = B
        parameter = json.dumps(p)
        code, data = self._Call(ROBOT_API_ID_AUDIO_SET_RGB_LED, parameter)
        return code

    # ======================= ASR LISTENER =======================
    def StartAsrListener(self, handler: Callable[[dict], None], queueLen: int = 10):
        """Start listening to ASR results published by the robot.

        Parameters
        ----------
        handler : Callable[[dict], None]
            User callback invoked for every ASR message. The raw DDS String data
            is parsed as JSON and converted to a Python dict before being passed
            to this handler.
        queueLen : int, optional
            Length of the internal queue buffering incoming messages. Defaults
            to 10.
        """
        # Avoid re-initialisation if already running
        if self.__asr_subscriber is not None:
            return

        def _internal_handler(sample: String_):
            """Wrap raw DDS sample into dict and delegate to user handler."""
            try:
                payload = json.loads(sample.data)
            except Exception:
                # Malformed payload – forward raw string
                payload = {"raw": sample.data}
            handler(payload)

        # Lazily import topic constant to avoid circular deps in unit tests
        from .g1_audio_api import AUDIO_ASR_TOPIC_NAME

        self.__asr_subscriber = ChannelSubscriber(AUDIO_ASR_TOPIC_NAME, String_)
        self.__asr_subscriber.Init(_internal_handler, queueLen)

    def StopAsrListener(self):
        """Stop the ASR listener and release DDS resources."""
        if self.__asr_subscriber is not None:
            self.__asr_subscriber.Close()
            self.__asr_subscriber = None

    # ======================= RAW MIC LISTENER =======================
    def _get_local_ip_for_multicast(self) -> Optional[str]:
        """Find the local IP address on the robot's network (192.168.123.x).
        
        Returns
        -------
        Optional[str]
            The local IP address string, or None if no matching interface found.
        """
        target_subnet = "192.168.123."
        
        # Method 1: Try socket.getaddrinfo for all interfaces
        try:
            import socket
            for info in socket.getaddrinfo(socket.gethostname(), None):
                ip = info[4][0]
                if ip.startswith(target_subnet):
                    return ip
        except Exception:
            pass
        
        # Method 2: Get all IPs via gethostbyname_ex
        try:
            hostname = socket.gethostname()
            _, _, all_ips = socket.gethostbyname_ex(hostname)
            
            for ip in all_ips:
                if ip.startswith(target_subnet):
                    return ip
        except Exception:
            pass
                    
        # Method 3: Try to connect to robot's typical gateway
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                # Try connecting to robot's typical gateway address
                s.connect(("192.168.123.1", 80))
                local_ip = s.getsockname()[0]
                if local_ip.startswith(target_subnet):
                    return local_ip
        except Exception:
            pass
            
        # Method 4: General fallback - connect to external host
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                local_ip = s.getsockname()[0]
                if local_ip.startswith(target_subnet):
                    return local_ip
        except Exception:
            pass
            
        return None

    def StartRawMicListener(self, handler: Callable[[bytes], None]):
        """Start listening to the raw microphone UDP multicast stream.
        
        The audio data is 16-bit PCM, 16kHz sample rate, mono channel.
        
        Parameters
        ----------
        handler : Callable[[bytes], None]
            User callback invoked for each UDP packet containing raw audio data.
        """
        # Avoid re-initialization if already running
        if self.__mic_listener_thread is not None:
            return
            
        # Initialize stop event
        self.__mic_listener_stop_event = threading.Event()
        
        # Start listener thread
        self.__mic_listener_thread = threading.Thread(
            target=self._mic_listener_loop,
            args=(handler,),
            daemon=True
        )
        self.__mic_listener_thread.start()

    def StopRawMicListener(self):
        """Stop the raw microphone listener and release resources."""
        if self.__mic_listener_thread is None:
            return
            
        # Signal thread to stop
        if self.__mic_listener_stop_event is not None:
            self.__mic_listener_stop_event.set()
            
        # Close socket to interrupt blocking recv
        if self.__mic_socket is not None:
            try:
                self.__mic_socket.close()
            except Exception:
                pass
                
        # Wait for thread to finish
        if self.__mic_listener_thread is not None:
            self.__mic_listener_thread.join(timeout=5.0)
            
        # Reset state
        self.__mic_socket = None
        self.__mic_listener_thread = None
        self.__mic_listener_stop_event = None

    def _mic_listener_loop(self, handler: Callable[[bytes], None]):
        """Internal method to run the UDP multicast receiver loop.
        
        Parameters
        ----------
        handler : Callable[[bytes], None]
            User callback for audio data.
        """
        sock = None
        try:
            # Find local IP on robot's network
            local_ip = self._get_local_ip_for_multicast()
            if local_ip is None:
                raise RuntimeError(
                    "Could not find local IP on robot network (192.168.123.x). "
                    "Please ensure you are connected to the robot's network."
                )
                
            # Create UDP socket
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            except socket.error as e:
                raise RuntimeError(f"Failed to create UDP socket: {e}")
            
            # Bind to multicast port
            try:
                sock.bind(('', AUDIO_MIC_PORT))
            except socket.error as e:
                raise RuntimeError(f"Failed to bind to port {AUDIO_MIC_PORT}: {e}")
            
            # Join multicast group
            try:
                mreq = struct.pack("4s4s", 
                                  socket.inet_aton(AUDIO_MIC_GROUP_IP),
                                  socket.inet_aton(local_ip))
                sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
            except socket.error as e:
                raise RuntimeError(
                    f"Failed to join multicast group {AUDIO_MIC_GROUP_IP} "
                    f"on interface {local_ip}: {e}"
                )
            
            # Store socket reference
            self.__mic_socket = sock
            
            # Receive loop
            while not self.__mic_listener_stop_event.is_set():
                try:
                    # Set timeout for periodic stop check
                    sock.settimeout(1.0)
                    data, addr = sock.recvfrom(4096)
                    if data:
                        try:
                            handler(data)
                        except Exception as e:
                            # User handler error - log but continue
                            print(f"Error in user audio handler: {e}")
                except socket.timeout:
                    # Timeout is expected - check stop event and continue
                    continue
                except (socket.error, OSError) as e:
                    # Socket closed or error - exit loop
                    if self.__mic_listener_stop_event.is_set():
                        # Expected shutdown
                        break
                    else:
                        # Unexpected error
                        print(f"Socket error in mic listener: {e}")
                        break
                    
        except RuntimeError as e:
            # Configuration/setup errors
            print(f"Mic listener setup error: {e}")
        except Exception as e:
            # Unexpected errors
            print(f"Unexpected error in mic listener: {e}")
        finally:
            # Socket cleanup handled in StopRawMicListener
            pass
