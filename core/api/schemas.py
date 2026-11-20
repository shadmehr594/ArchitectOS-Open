"""
API request/response schemas
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class ChatRequest:

    message: str
    session_id: str = "default"


@dataclass
class ChatResponse:

    status: str
    session_id: str
    response: str

    tool: Optional[str] = None

    metadata: Dict[str, Any] = field(
        default_factory=dict
    )

