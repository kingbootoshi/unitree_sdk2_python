"""
" service name
"""
AUDIO_SERVICE_NAME = "voice"

"""
" service api version
"""
AUDIO_API_VERSION = "1.0.0.0"

"""
" api id
"""
ROBOT_API_ID_AUDIO_TTS = 1001
ROBOT_API_ID_AUDIO_ASR = 1002
ROBOT_API_ID_AUDIO_START_PLAY = 1003
ROBOT_API_ID_AUDIO_STOP_PLAY = 1004
ROBOT_API_ID_AUDIO_GET_VOLUME = 1005
ROBOT_API_ID_AUDIO_SET_VOLUME = 1006 
ROBOT_API_ID_AUDIO_SET_RGB_LED = 1010

"""
" error code
"""

"""
" topic name for ASR results
"""
AUDIO_ASR_TOPIC_NAME = "rt/audio_msg"

"""
" UDP multicast configuration for raw microphone stream
"""
AUDIO_MIC_GROUP_IP = "239.168.123.161"
AUDIO_MIC_PORT = 5555