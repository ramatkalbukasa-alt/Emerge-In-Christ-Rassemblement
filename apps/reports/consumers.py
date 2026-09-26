import json
import logging

from channels.generic.websocket import AsyncWebsocketConsumer
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)


class ReportEventsConsumer(AsyncWebsocketConsumer):
    group_name = "reports"

    async def __call__(self, scope, receive, send):
        try:
            await super().__call__(scope, receive, send)
        except (RedisError, TimeoutError, OSError) as exc:
            # Receive errors occur in the Channels dispatch loop, outside connect.
            logger.warning("Report realtime connection unavailable (%s).", type(exc).__name__)
            await self.close(code=1013)

    async def connect(self):
        if not self.scope["user"].is_authenticated:
            await self.close()
            return
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        try:
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
        except (RedisError, TimeoutError, OSError):
            logger.warning("Report realtime group cleanup unavailable.")

    async def report_created(self, event):
        await self.send(text_data=json.dumps(event["payload"]))
