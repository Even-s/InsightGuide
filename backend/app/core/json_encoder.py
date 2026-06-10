"""Custom JSON encoder for datetime serialization."""

import json
from datetime import datetime, date
from typing import Any


class DateTimeEncoder(json.JSONEncoder):
    """JSON encoder that handles datetime objects with proper timezone info."""

    def default(self, obj: Any) -> Any:
        """Encode datetime objects to ISO 8601 format with 'Z' suffix for UTC."""
        if isinstance(obj, datetime):
            # Ensure UTC datetime is serialized with 'Z' suffix
            return obj.isoformat() + 'Z'
        elif isinstance(obj, date):
            return obj.isoformat()
        return super().default(obj)
