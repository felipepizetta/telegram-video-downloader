def parse_size(size_str):
    units = {'B': 1, 'KB': 1024, 'MB': 1024**2, 'GB': 1024**3}
    number = int(''.join(filter(str.isdigit, size_str)))
    unit = ''.join(filter(str.isalpha, size_str)).upper()
    return number * units.get(unit, 1)

def parse_date(date_str):
    from datetime import datetime
    if not date_str:
        return None
    return datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=None)