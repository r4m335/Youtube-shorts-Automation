from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

@dataclass
class Tweet:
    id: str
    username: str
    text: str
    url: str
    created_at: Optional[datetime]

    reply_count: int = 0
    repost_count: int = 0
    like_count: int = 0
    view_count: int = 0

    is_repost: bool = False
    media: list = field(default_factory=list)
    
    # Internal metric for backward compatibility with the existing orchestrator
    story_count: int = 1

    def to_dict(self):
        """Converts to the unified dictionary format expected by the orchestrator."""
        return {
            "tweet_id": self.id,
            "text": self.text,
            "author": self.username,
            "category": getattr(self, "category", "unknown"),  # Set dynamically during fetching
            "url": self.url,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "retweets": self.repost_count,
            "likes": self.like_count,
            "replies": self.reply_count,
            "views": self.view_count,
            "is_retweet": self.is_repost,
            "media": self.media,
            "importance": self.like_count + self.repost_count,  # Simple proxy for importance
            "story_count": self.story_count
        }
