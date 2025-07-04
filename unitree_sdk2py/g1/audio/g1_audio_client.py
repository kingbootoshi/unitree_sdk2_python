import json
from typing import List, Callable

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
