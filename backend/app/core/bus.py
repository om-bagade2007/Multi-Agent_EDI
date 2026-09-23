"""In-memory and Redis Streams event-bus adapters."""
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable
from typing import Protocol

from app.core.events import Event

Handler = Callable[[Event], Awaitable[None]]


class EventBus(Protocol):
    """Common async event transport interface."""
    async def publish(self, stream: str, event: Event) -> None: ...
    async def subscribe(self, stream: str, group: str, consumer: str, handler: Handler) -> None: ...
    async def drain(self) -> None: ...


class InMemoryBus:
    """Deterministic bus that drains queued handlers in publish order."""
    def __init__(self) -> None:
        self._handlers: dict[str, list[Handler]] = defaultdict(list)
        self._queue: deque[tuple[str, Event]] = deque()
        self._draining = False

    async def publish(self, stream: str, event: Event) -> None:
        """Queue an event for its stream subscribers."""
        self._queue.append((stream, event))

    async def subscribe(self, stream: str, group: str, consumer: str, handler: Handler) -> None:
        """Register a handler; group and consumer preserve interface parity."""
        del group, consumer
        self._handlers[stream].append(handler)

    async def drain(self) -> None:
        """Handle all events, including events emitted by handlers during drain."""
        if self._draining:
            return
        self._draining = True
        try:
            while self._queue:
                stream, event = self._queue.popleft()
                for handler in tuple(self._handlers[stream]):
                    await handler(event)
        finally:
            self._draining = False


class RedisStreamsBus:
    """Redis Streams adapter; consumers process and acknowledge one entry at a time."""
    def __init__(self, url: str) -> None:
        from redis.asyncio import Redis
        self.client = Redis.from_url(url, decode_responses=True)
        self._subscriptions: list[tuple[str, str, str, Handler]] = []

    async def publish(self, stream: str, event: Event) -> None:
        """Append a bounded event entry to Redis."""
        await self.client.xadd(stream, {"event": event.model_dump_json()}, maxlen=10000)

    async def subscribe(self, stream: str, group: str, consumer: str, handler: Handler) -> None:
        """Create a group and register its consumer callback."""
        try:
            await self.client.xgroup_create(stream, group, id="0", mkstream=True)
        except Exception as exc:
            if "BUSYGROUP" not in str(exc):
                raise
        self._subscriptions.append((stream, group, consumer, handler))

    async def drain(self) -> None:
        """Read and acknowledge current pending entries for all local subscriptions."""
        for stream, group, consumer, handler in self._subscriptions:
            records = await self.client.xreadgroup(group, consumer, {stream: ">"}, count=100, block=1)
            for _, entries in records:
                for entry_id, fields in entries:
                    await handler(Event.model_validate_json(fields["event"]))
                    await self.client.xack(stream, group, entry_id)
