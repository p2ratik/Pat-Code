from __future__ import annotations
from enum import Enum
from dataclasses import dataclass

class StreamEventType(str, Enum):
    # To indicate ki type er response AI dicche

    TEXT_DELTA = "text_delta"
    MESSAGE_COMPLETE = "message_complete"
    ERROR = "error"

# Ei class ta e store ache ki type er response asbe , stream / non-stream

@dataclass
class TextDelta:

    # Ei data class ta text delta handle kore for streaming response
    content : str
    def __str__(self):
        return self.content

@dataclass
class TokenUsage:
    prompt_tokens: int = 0
    completion_token: int = 0
    total_tokens: int = 0
    cached_tokens: int = 0

    # 2 to token usage add koarr jonno ei function . Multiple step-> Multiple token uage -> add to get total usage
    def __add__(self, other: TokenUsage):
        return TokenUsage(
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            completion_tokens=self.completion_tokens + other.completion_tokens,
            total_tokens=self.total_tokens + other.total_tokens,
            cached_tokens=self.cached_tokens + other.cached_tokens,
        )       
        

@dataclass
class StreamEvent:
    # Ei class ta handle kore all response related things , tools , content, usage . EI different different things alada alada data class handle korbe
    type : StreamEventType    
    text_delta : TextDelta | None = None
    usage : TokenUsage | None = None
    finish_reason : str | None = None
    error : str | None = None


