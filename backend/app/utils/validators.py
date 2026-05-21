import aiohttp


async def verify_url(url: str, timeout: int = 10) -> dict:
    """验证 URL 可达性，返回 {reachable, file_size, content_type, error}"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Referer": "https://www.google.com/",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }
    try:
        # 使用 GET 替代 HEAD，因为某些 CDN 会拦截 HEAD 请求
        # 设置 stream=True (在 aiohttp 中通过 context manager 实现)
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout),
                                    allow_redirects=True) as resp:
                if resp.status < 400:
                    content_length = resp.headers.get("Content-Length", "0")
                    return {
                        "reachable": True,
                        "file_size": int(content_length) if content_length else 0,
                        "content_type": resp.headers.get("Content-Type", ""),
                        "error": "",
                    }
                else:
                    return {
                        "reachable": False,
                        "file_size": 0,
                        "content_type": "",
                        "error": f"HTTP {resp.status}",
                    }
    except Exception as e:
        return {
            "reachable": False,
            "file_size": 0,
            "content_type": "",
            "error": str(e),
        }
