from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer


def publish_report_created(report):
    channel_layer = get_channel_layer()
    if not channel_layer:
        return

    async_to_sync(channel_layer.group_send)(
        "reports",
        {
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
        },
    )
