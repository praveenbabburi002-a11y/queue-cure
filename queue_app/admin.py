from django.contrib import admin
from .models import (
    Patient,
    QueueSettings,
    ConsultationRecord,
    DailyStatistics
)

admin.site.register(Patient)
admin.site.register(QueueSettings)
admin.site.register(ConsultationRecord)
admin.site.register(DailyStatistics)