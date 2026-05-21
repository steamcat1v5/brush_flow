def format_bytes(n: int) -> str:
    """将字节数格式化为人类可读形式"""
    if n < 1024:
        return f"{n} B"
    elif n < 1024 ** 2:
        return f"{n / 1024:.1f} KB"
    elif n < 1024 ** 3:
        return f"{n / 1024 ** 2:.1f} MB"
    elif n < 1024 ** 4:
        return f"{n / 1024 ** 3:.2f} GB"
    else:
        return f"{n / 1024 ** 4:.2f} TB"


def format_speed(bytes_per_sec: int) -> str:
    """格式化速度"""
    return f"{format_bytes(bytes_per_sec)}/s"


def format_duration(seconds: int) -> str:
    """格式化时长"""
    if seconds < 60:
        return f"{seconds}秒"
    elif seconds < 3600:
        return f"{seconds // 60}分{seconds % 60}秒"
    else:
        h = seconds // 3600
        m = (seconds % 3600) // 60
        return f"{h}小时{m}分"
