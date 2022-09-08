from dataclasses import dataclass
from typing import List


@dataclass
class Supported_Video_Type:
    mime: str
    extension: str


WEBM: Supported_Video_Type = Supported_Video_Type(mime="video/webm", extension="webm")
MP4: Supported_Video_Type = Supported_Video_Type(mime="video/mp4", extension="mp4")
X_MATROSKA: Supported_Video_Type = Supported_Video_Type(mime="video/x-matroska", extension="mp4") #we convert from x-matroska to mp4
supported_video_types: List[Supported_Video_Type] = [WEBM, MP4]
