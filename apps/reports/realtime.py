import asyncio
import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)


async def _send_event(channel_layer, event):
    # Bound notification latency independently of the blocking receive timeout.
    await asyncio.wait_for(channel_layer.group_send("reports", event), timeout=5)


def publish_report_created(report):
    channel_layer = get_channel_layer()
    if not channel_layer:
        return

    event = {
        "type": "report.created",
        "payload": {
            "type": "report.created",
            "id": report.pk,
            "extension": report.extension.name,
            "service_date": report.service_date.isoformat(),
            "total_attendance": report.total_attendance,
            "total_offerings": str(report.total_offerings),
            "net_balance": str(report.net_balance),
        },
    }
    try:
        async_to_sync(_send_event)(channel_layer, event)
    except (RedisError, TimeoutError, OSError) as exc:
        # No connection URL or credentials in logs; the report is already saved.
        logger.warning("Report %s saved; realtime notification unavailable (%s).", report.pk, type(exc).__name__)
        return False
    return True
