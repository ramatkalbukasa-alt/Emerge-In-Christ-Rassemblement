from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer


def publish_report_created(report):
    channel_layer = get_channel_layer()
    if not channel_layer:
        return

    event = {
        "type": "report.created",
        "extension_id": report.extension_id,
        "payload": {
            "type": "report.created",
            "id": report.pk,
            "extension": report.extension.name,
            "service_date": report.service_date.isoformat(),
            "total_attendance": report.total_attendance,
            "total_offerings": str(report.total_offerings),
            "net_balance": str(report.net_balance),
            "currency": report.currency,
        },
    }
    for group in ("reports.admin", f"reports.extension.{report.extension_id}"):
        async_to_sync(channel_layer.group_send)(group, event)
