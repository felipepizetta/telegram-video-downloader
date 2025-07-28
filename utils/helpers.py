def parse_size(size_str):
    size_str = size_str.strip().upper()
    units = {'KB': 1024, 'MB': 1024**2, 'GB': 1024**3}
    for unit, multiplier in units.items():
        if size_str.endswith(unit):
            try:
                return float(size_str[:-2]) * multiplier
            except ValueError:
                raise ValueError(f"Invalid size format: {size_str}")
    raise ValueError(f"Invalid size format: {size_str}")