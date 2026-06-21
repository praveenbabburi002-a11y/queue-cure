from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
import json
import logging

logger = logging.getLogger(__name__)
GROUP_NAME = "queue_updates"


class QueueConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        await self.channel_layer.group_add(GROUP_NAME, self.channel_name)
        await self.accept()
        snapshot = await self._get_snapshot()
        await self.send(text_data=json.dumps({"event": "connected", "payload": snapshot}))

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(GROUP_NAME, self.channel_name)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            if data.get("type") == "ping":
                await self.send(text_data=json.dumps({"event": "pong"}))
            elif data.get("type") == "request_snapshot":
                snapshot = await self._get_snapshot()
                await self.send(text_data=json.dumps({"event": "snapshot", "payload": snapshot}))
        except Exception as exc:
            logger.warning("Consumer receive error: %s", exc)

    async def queue_event(self, event):
        await self.send(text_data=json.dumps({"event": event["event"], "payload": event["payload"]}))

    # Keep backwards compat with old broadcast format
    async def queue_update(self, event):
        await self.send(text_data=json.dumps({"event": "queue_update", "payload": event}))

    @database_sync_to_async
    def _get_snapshot(self):
        from .models import Patient, QueueSettings
        from .services import compute_avg_consultation_time
        settings = QueueSettings.get_settings()
        serving  = Patient.objects.filter(status='serving').first()
        waiting  = Patient.objects.filter(status='waiting').order_by('-priority_rank', 'token_number')
        waiting_list = [
            {"token": p.token_number, "name": p.name, "priority": p.priority}
            for p in waiting[:20]
        ]
        return {
            "queue_active":  settings.queue_active,
            "avg_time":      compute_avg_consultation_time(),
            "waiting_count": waiting.count(),
            "current_token": serving.token_number if serving else None,
            "current_name":  serving.name if serving else None,
            "current_priority": serving.priority if serving else None,
            "waiting_list":  waiting_list,
        }
