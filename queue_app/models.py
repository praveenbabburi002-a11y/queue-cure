from django.db import models
from django.utils import timezone
from django.db.models import Avg
from django.contrib.auth.models import User


class QueueSettings(models.Model):
    average_consultation_time = models.PositiveIntegerField(
        default=10,
        help_text="Fallback average consultation time in minutes"
    )
    queue_active = models.BooleanField(default=True)
    queue_paused_at = models.DateTimeField(null=True, blank=True)
    clinic_name = models.CharField(max_length=120, default="Queue Cure Clinic")
    doctor_name = models.CharField(max_length=120, default="Dr. Attending")

    def __str__(self):
        status = "Active" if self.queue_active else "Paused"
        return f"{self.clinic_name} — {status}"

    @classmethod
    def get_settings(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class Patient(models.Model):
    STATUS_CHOICES = (
        ('waiting',   'Waiting'),
        ('serving',   'Serving'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('skipped',   'Skipped'),
    )
    PRIORITY_CHOICES = (
        ('normal',    'Normal'),
        ('urgent',    'Urgent'),
        ('emergency', 'Emergency'),
    )
    PRIORITY_RANK = {'emergency': 3, 'urgent': 2, 'normal': 1}

    token_number      = models.PositiveIntegerField(unique=True)
    name              = models.CharField(max_length=100)
    age               = models.PositiveIntegerField()
    phone_number      = models.CharField(max_length=15)
    consultation_type = models.CharField(max_length=100)
    priority          = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='normal')
    priority_rank     = models.IntegerField(default=1)
    status            = models.CharField(max_length=20, choices=STATUS_CHOICES, default='waiting')
    created_at        = models.DateTimeField(auto_now_add=True)
    called_at         = models.DateTimeField(null=True, blank=True)
    completed_at      = models.DateTimeField(null=True, blank=True)
    estimated_wait_time = models.IntegerField(default=0)
    notes             = models.TextField(blank=True, default='')
    registered_by     = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='registered_patients'
    )

    class Meta:
        ordering = ['-priority_rank', 'token_number']

    def __str__(self):
        return f"#{self.token_number} — {self.name} [{self.priority.upper()}]"

    def save(self, *args, **kwargs):
        self.priority_rank = self.PRIORITY_RANK.get(self.priority, 1)
        super().save(*args, **kwargs)

    @staticmethod
    def generate_token():
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT COALESCE(MAX(token_number), 0) + 1 FROM queue_app_patient")
            row = cursor.fetchone()
        return row[0]

    @property
    def actual_wait_minutes(self):
        if self.called_at and self.created_at:
            return round((self.called_at - self.created_at).total_seconds() / 60, 1)
        return None

    @property
    def actual_consultation_minutes(self):
        if self.called_at and self.completed_at:
            return round((self.completed_at - self.called_at).total_seconds() / 60, 1)
        return None


class ConsultationRecord(models.Model):
    patient          = models.OneToOneField(Patient, on_delete=models.CASCADE, related_name='consultation')
    start_time       = models.DateTimeField()
    end_time         = models.DateTimeField()
    duration_minutes = models.FloatField()

    def __str__(self):
        return f"Consultation #{self.patient.token_number} — {self.duration_minutes}m"


class QueueActionLog(models.Model):
    ACTION_CHOICES = (
        ('register',      'Patient Registered'),
        ('call_next',     'Called Next'),
        ('complete',      'Completed'),
        ('cancel',        'Cancelled'),
        ('skip',          'Skipped'),
        ('pause_queue',   'Queue Paused'),
        ('resume_queue',  'Queue Resumed'),
        ('settings_changed', 'Settings Changed'),
    )
    action       = models.CharField(max_length=30, choices=ACTION_CHOICES)
    performed_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    patient      = models.ForeignKey(Patient, null=True, blank=True, on_delete=models.SET_NULL)
    description  = models.TextField()
    timestamp    = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.action} at {self.timestamp:%H:%M}"


class DailyStatistics(models.Model):
    date                      = models.DateField(unique=True)
    total_patients            = models.IntegerField(default=0)
    patients_served           = models.IntegerField(default=0)
    patients_cancelled        = models.IntegerField(default=0)
    patients_skipped          = models.IntegerField(default=0)
    average_wait_time         = models.FloatField(default=0)
    average_consultation_time = models.FloatField(default=0)

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f"Stats for {self.date}"

    @staticmethod
    def update_statistics():
        today = timezone.localdate()
        stats, _ = DailyStatistics.objects.get_or_create(date=today)
        patients = Patient.objects.filter(created_at__date=today)
        stats.total_patients     = patients.count()
        stats.patients_served    = patients.filter(status='completed').count()
        stats.patients_cancelled = patients.filter(status='cancelled').count()
        stats.patients_skipped   = patients.filter(status='skipped').count()
        records = ConsultationRecord.objects.filter(patient__created_at__date=today)
        avg_c = records.aggregate(Avg('duration_minutes'))['duration_minutes__avg']
        stats.average_consultation_time = round(avg_c or 0, 2)
        completed = patients.filter(status='completed', called_at__isnull=False)
        waits = [(p.called_at - p.created_at).total_seconds() / 60 for p in completed]
        stats.average_wait_time = round(sum(waits) / len(waits), 2) if waits else 0
        stats.save()
        return stats
