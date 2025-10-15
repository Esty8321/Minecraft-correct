from typing import Dict, Any
from datetime import datetime

class Message:
    def __init__(self, content: str, author: str, chunk_id: str, position: tuple[int, int]):
        self.content = content
        self.author = author
        self.chunk_id = chunk_id
        self.position = position  # (row, col)
        self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "content": self.content,
            "author": self.author,
            "chunk_id": self.chunk_id,
            "position": self.position,
            "timestamp": self.timestamp
        }