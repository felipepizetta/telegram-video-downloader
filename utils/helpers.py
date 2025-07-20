import re
from datetime import datetime
from dateutil.parser import parse as parse_dateutil

def parse_size(size_str):
    """Parse a size string (e.g., '10MB') into bytes."""
    if not size_str:
        return 0
    pattern = r'^(\d+)\s*([BKMG]B?)?$'
    match = re.match(pattern, size_str.strip(), re.IGNORECASE)
    if not match:
        raise ValueError(f"Invalid size format: {size_str}. Expected format: '10MB', '500KB', etc.")
    
    number, unit = match.groups()
    number = int(number)
    units = {'B': 1, 'KB': 1024, 'MB': 1024**2, 'GB': 1024**3}
    unit = (unit or 'B').upper().replace('B', '') + 'B'
    return number * units.get(unit, 1)

def parse_date(date_str):
    """Parse a date string into a naive datetime object."""
    if not date_str:
        return None
    try:
        return parse_dateutil(date_str).replace(tzinfo=None)
    except ValueError as e:
        raise ValueError(f"Invalid date format: {date_str}. Expected format like '2023-01-01'.") from e

def sanitize_filename(filename):
    """Sanitize a filename to remove invalid characters."""
    return re.sub(r'[^\w\-\.]', '_', filename)