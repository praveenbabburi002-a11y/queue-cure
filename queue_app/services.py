import logging
from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from django.db.models import Avg, Q
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from .models import Patient, QueueSettings, ConsultationRecord, DailyStatistics, QueueActionLog

logger = logging.getLogger(__name__)


def compute_avg_consultation_time(lookback_days=7, min_records=3):
    cutoff = timezone.now() - timedelta(days=lookback_days)
    records = ConsultationRecord.objects.filter(start_time__gte=cutoff)
    if records.count() >= min_records:
        avg = records.aggregate(Avg('duration_minutes'))['duration_minutes__avg']
        return round(avg, 1)
    settings = QueueSettings.get_settings()
    return settings.average_consultation_time


def compute_position_and_eta(patient):
    if patient.status == 'serving':
        return 0, 0, 0
    if patient.status in ('completed', 'cancelled', 'skipped'):
        return None, None, None

    ahead = Patient.objects.filter(status='waiting').filter(
        Q(priority_rank__gt=patient.priority_rank) |
        Q(priority_rank=patient.priority_rank, token_number__lt=patient.token_number)
    ).count()

    avg_time = compute_avg_consultation_time()
    serving = Patient.objects.filter(status='serving').first()
    remaining_current = 0
    if serving and serving.called_at:
        elapsed = (timezone.now() - serving.called_at).total_seconds() / 60
        remaining_current = max(0, avg_time - elapsed)

    eta = round(remaining_current + (ahead * avg_time))
    return ahead + 1, ahead, eta


def _broadcast(event_type, payload):
    try:
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            "queue_updates",
            {"type": "queue_event", "event": event_type, "payload": payload}
        )
    except Exception as exc:
        logger.warning("WebSocket broadcast failed: %s", exc)


def _queue_snapshot():
    settings = QueueSettings.get_settings()
    serving  = Patient.objects.filter(status='serving').first()
    waiting  = Patient.objects.filter(status='waiting')
    return {
        "queue_active":     settings.queue_active,
        "avg_time":         compute_avg_consultation_time(),
        "waiting_count":    waiting.count(),
        "current_token":    serving.token_number if serving else None,
        "current_name":     serving.name if serving else None,
        "current_priority": serving.priority if serving else None,
    }


@transaction.atomic
def register_patient(form_data, registered_by=None):
    priority     = form_data.get('priority', 'normal')
    priority_map = {'emergency': 3, 'urgent': 2, 'normal': 1}
    last  = Patient.objects.select_for_update().order_by('-token_number').first()
    token = (last.token_number + 1) if last else 1
    patient = Patient(
        token_number=token,
        name=form_data['name'],
        age=form_data['age'],
        phone_number=form_data['phone_number'],
        consultation_type=form_data['consultation_type'],
        priority=priority,
        priority_rank=priority_map.get(priority, 1),
        notes=form_data.get('notes', ''),
        registered_by=registered_by,
    )
    patient.save()
    _, _, eta = compute_position_and_eta(patient)
    patient.estimated_wait_time = eta
    patient.save(update_fields=['estimated_wait_time'])
    QueueActionLog.objects.create(
        action='register', performed_by=registered_by, patient=patient,
        description=f"Registered {patient.name} (#{token}) as {priority}",
    )
    _broadcast('patient_registered', {
        **_queue_snapshot(),
        "new_patient": {"token": token, "name": patient.name, "priority": priority}
    })
    if priority == 'emergency':
        _broadcast('emergency_alert', {
            "token": token, "name": patient.name,
            "message": f"EMERGENCY patient #{token} — {patient.name}"
        })
    DailyStatistics.update_statistics()
    return patient


def _complete_consultation(patient, performed_by=None):
    patient.status       = 'completed'
    patient.completed_at = timezone.now()
    patient.save(update_fields=['status', 'completed_at'])
    if patient.called_at:
        duration = (patient.completed_at - patient.called_at).total_seconds() / 60
        ConsultationRecord.objects.update_or_create(
            patient=patient,
            defaults={
                'start_time':       patient.called_at,
                'end_time':         patient.completed_at,
                'duration_minutes': round(duration, 2),
            }
        )
    QueueActionLog.objects.create(
        action='complete', performed_by=performed_by, patient=patient,
        description=f"Completed #{patient.token_number} — {patient.name}",
    )
    _broadcast('consultation_completed', {
        **_queue_snapshot(),
        "completed_token": patient.token_number,
    })


@transaction.atomic
def call_next_patient(performed_by=None):
    settings = QueueSettings.get_settings()
    if not settings.queue_active:
        return None
    current = Patient.objects.select_for_update().filter(status='serving').first()
    if current:
        _complete_consultation(current, performed_by)
    next_patient = (
        Patient.objects.select_for_update()
        .filter(status='waiting')
        .order_by('-priority_rank', 'token_number')
        .first()
    )
    if next_patient:
        next_patient.status    = 'serving'
        next_patient.called_at = timezone.now()
        next_patient.save(update_fields=['status', 'called_at'])
        QueueActionLog.objects.create(
            action='call_next', performed_by=performed_by, patient=next_patient,
            description=f"Called #{next_patient.token_number} — {next_patient.name}",
        )
        _broadcast('patient_called', {
            **_queue_snapshot(),
            "called_token":    next_patient.token_number,
            "called_name":     next_patient.name,
            "called_priority": next_patient.priority,
        })
    DailyStatistics.update_statistics()
    return next_patient


@transaction.atomic
def complete_patient(patient_id, performed_by=None):
    patient = Patient.objects.select_for_update().get(pk=patient_id)
    _complete_consultation(patient, performed_by)
    DailyStatistics.update_statistics()
    return patient


@transaction.atomic
def cancel_patient(patient_id, performed_by=None):
    patient = Patient.objects.select_for_update().get(pk=patient_id)
    patient.status = 'cancelled'
    patient.save(update_fields=['status'])
    QueueActionLog.objects.create(
        action='cancel', performed_by=performed_by, patient=patient,
        description=f"Cancelled #{patient.token_number} — {patient.name}",
    )
    _broadcast('patient_cancelled', {**_queue_snapshot(), "cancelled_token": patient.token_number})
    DailyStatistics.update_statistics()
    return patient


@transaction.atomic
def skip_patient(patient_id, performed_by=None):
    patient = Patient.objects.select_for_update().get(pk=patient_id)
    patient.status = 'skipped'
    patient.save(update_fields=['status'])
    QueueActionLog.objects.create(
        action='skip', performed_by=performed_by, patient=patient,
        description=f"Skipped #{patient.token_number} — {patient.name}",
    )
    _broadcast('queue_update', _queue_snapshot())
    DailyStatistics.update_statistics()
    return patient


@transaction.atomic
def pause_queue(performed_by=None):
    settings = QueueSettings.get_settings()
    settings.queue_active    = False
    settings.queue_paused_at = timezone.now()
    settings.save()
    QueueActionLog.objects.create(
        action='pause_queue', performed_by=performed_by, description="Queue paused",
    )
    _broadcast('queue_paused', _queue_snapshot())


@transaction.atomic
def resume_queue(performed_by=None):
    settings = QueueSettings.get_settings()
    settings.queue_active    = True
    settings.queue_paused_at = None
    settings.save()
    QueueActionLog.objects.create(
        action='resume_queue', performed_by=performed_by, description="Queue resumed",
    )
    _broadcast('queue_resumed', _queue_snapshot())


def get_analytics_summary(days=7):
    """
    Returns analytics for the last N days.
    Fixes: uses datetime.timedelta (not timezone.timedelta),
    and uses __gte with a proper datetime for ConsultationRecord.
    """
    today  = timezone.localdate()
    cutoff = today - timedelta(days=days - 1)

    patients = Patient.objects.filter(created_at__date__gte=cutoff)

    priority_breakdown = {
        'emergency': patients.filter(priority='emergency').count(),
        'urgent':    patients.filter(priority='urgent').count(),
        'normal':    patients.filter(priority='normal').count(),
    }

    throughput_by_day = []
    for i in range(days):
        day = cutoff + timedelta(days=i)
        dp  = patients.filter(created_at__date=day)
        throughput_by_day.append({
            'date':      day.strftime('%b %d'),
            'total':     dp.count(),
            'served':    dp.filter(status='completed').count(),
            'cancelled': dp.filter(status='cancelled').count(),
        })

    # Use date-range filter instead of __date lookup for ConsultationRecord
    # to avoid timezone issues with MySQL
    cutoff_dt = timezone.make_aware(
        timezone.datetime(cutoff.year, cutoff.month, cutoff.day)
    )
    records  = ConsultationRecord.objects.filter(start_time__gte=cutoff_dt)
    avg_cons = records.aggregate(Avg('duration_minutes'))['duration_minutes__avg'] or 0

    completed = patients.filter(status='completed', called_at__isnull=False)
    waits = []
    for p in completed:
        try:
            wait = (p.called_at - p.created_at).total_seconds() / 60
            waits.append(wait)
        except Exception:
            pass
    avg_wait = round(sum(waits) / len(waits), 1) if waits else 0

    total = patients.count()
    served = patients.filter(status='completed').count()

    return {
        'total_patients':     total,
        'served':             served,
        'cancelled':          patients.filter(status='cancelled').count(),
        'avg_consultation':   round(avg_cons, 1),
        'avg_wait':           avg_wait,
        'priority_breakdown': priority_breakdown,
        'throughput_by_day':  throughput_by_day,
        'completion_rate':    round(served / total * 100, 1) if total else 0,
    }
