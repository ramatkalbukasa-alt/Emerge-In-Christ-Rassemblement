import json

from asgiref.sync import async_to_sync
from channels.generic.websocket import WebsocketConsumer

from .permissions import report_event_group


class ReportEventsConsumer(WebsocketConsumer):
    group_name = None

    def connect(self):
        self.group_name = report_event_group(self.scope["user"])
        if self.group_name is None:
            self.close()
            return
        async_to_sync(self.channel_layer.group_add)(self.group_name, self.channel_name)
        self.accept()

    def disconnect(self, close_code):
        if self.group_name:
            async_to_sync(self.channel_layer.group_discard)(self.group_name, self.channel_name)

    def report_created(self, event):
        current_group = report_event_group(self.scope["user"])
        if current_group != self.group_name:
            self.close()
            return
        if current_group not in ("reports.admin", f"reports.extension.{event['extension_id']}"):
            return
        self.send(text_data=json.dumps(event["payload"]))
