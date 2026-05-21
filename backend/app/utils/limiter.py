import logging
import time
from asyncio import sleep


class TokenBucket:
    """令牌桶限速器"""

    def __init__(self, rate: float, capacity: float):
        """
        :param rate: 每秒产生的令牌数 (bytes/s)
        :param capacity: 桶容量 (bytes)
        """
        self.rate = rate
        self.capacity = capacity
        self.tokens = capacity
        self.last_update = time.monotonic()

    async def consume(self, amount: float):
        """消费指定数量的令牌，如果不够则等待"""
        if self.rate <= 0:
            return

        while self.tokens < amount:
            now = time.monotonic()
            elapsed = now - self.last_update
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
            self.last_update = now

            if self.tokens < amount:
                wait_time = (amount - self.tokens) / self.rate
                await sleep(wait_time)

        self.tokens -= amount
