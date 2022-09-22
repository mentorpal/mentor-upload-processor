from dataclasses import dataclass
from typing import List


@dataclass
class Supported_Video_Type:
    mime: str
    extension: str
    codecs: str = None


WEBM_VP9: Supported_Video_Type = Supported_Video_Type(
    mime="video/webm", extension="webm", codecs="vp9"
)
MP4: Supported_Video_Type = Supported_Video_Type(mime="video/mp4", extension="mp4")
supported_video_types: List[Supported_Video_Type] = [WEBM_VP9, MP4]
