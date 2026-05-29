def format_bytes(n: int) -> str:
    """将字节数格式化为可读的 KB/MB/GB/TB。"""
    if n < 1024:
        return f"{n} B"
    if n < 1024 ** 2:
        return f"{n / 1024:.1f} KB"
    if n < 1024 ** 3:
        return f"{n / (1024 ** 2):.1f} MB"
    if n < 1024 ** 4:
        return f"{n / (1024 ** 3):.2f} GB"
    return f"{n / (1024 ** 4):.2f} TB"
