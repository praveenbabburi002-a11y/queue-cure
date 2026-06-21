import json
import logging
from datetime import datetime

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone

from .models import Patient, QueueSettings, DailyStatistics, QueueActionLog, ConsultationRecord
from .forms import PatientForm, QueueSettingsForm
from . import services

logger = logging.getLogger(__name__)


@login_required
def dashboard(request):
    settings       = QueueSettings.get_settings()
    serving        = Patient.objects.filter(status='serving').first()
    waiting        = Patient.objects.filter(status='waiting').order_by('-priority_rank', 'token_number')
    today_patients = Patient.objects.filter(created_at__date=timezone.localdate())
    avg_time       = services.compute_avg_consultation_time()

    waiting_with_eta = []
    for i, p in enumerate(waiting):
        remaining = 0
        if serving and serving.called_at:
            elapsed   = (timezone.now() - serving.called_at).total_seconds() / 60
            remaining = max(0, avg_time - elapsed)
        eta = round(remaining + i * avg_time)
        waiting_with_eta.append({'patient': p, 'eta': eta, 'position': i + 1})

    context = {
        'settings':         settings,
        'queue_active':     settings.queue_active,
        'serving':          serving,
        'waiting':          waiting,
        'waiting_with_eta': waiting_with_eta,
        'waiting_count':    waiting.count(),
        'served_count':     today_patients.filter(status='completed').count(),
        'cancelled_count':  today_patients.filter(status='cancelled').count(),
        'total_today':      today_patients.count(),
        'avg_time':         avg_time,
        'emergency_count':  waiting.filter(priority='emergency').count(),
        'urgent_count':     waiting.filter(priority='urgent').count(),
        'recent_actions':   QueueActionLog.objects.select_related('patient', 'performed_by')[:8],
    }
    return render(request, 'receptionist/dashboard.html', context)


@login_required
def add_patient(request):
    if request.method == 'POST':
        form = PatientForm(request.POST)
        if form.is_valid():
            patient = services.register_patient(form.cleaned_data, registered_by=request.user)
            messages.success(request, f"✅ Token #{patient.token_number} issued to {patient.name} ({patient.priority.upper()})")
            return redirect('dashboard')
        else:
            messages.error(request, "Please fix the errors below.")
    else:
        form = PatientForm()
    return render(request, 'receptionist/add_patient.html', {'form': form})


@login_required
def call_next(request):
    next_patient = services.call_next_patient(performed_by=request.user)
    if next_patient:
        messages.success(request, f"📣 Calling #{next_patient.token_number} — {next_patient.name}")
    else:
        messages.info(request, "Queue is empty or paused.")
    return redirect('dashboard')


@login_required
def complete_patient(request, patient_id):
    patient = services.complete_patient(patient_id, performed_by=request.user)
    messages.success(request, f"✅ Completed consultation for #{patient.token_number}")
    return redirect('dashboard')


@login_required
def cancel_patient(request, patient_id):
    patient = services.cancel_patient(patient_id, performed_by=request.user)
    messages.warning(request, f"❌ Cancelled #{patient.token_number} — {patient.name}")
    return redirect('dashboard')


@login_required
def skip_patient(request, patient_id):
    patient = services.skip_patient(patient_id, performed_by=request.user)
    messages.info(request, f"⏭ Skipped #{patient.token_number} — {patient.name}")
    return redirect('dashboard')


@login_required
def pause_queue(request):
    services.pause_queue(performed_by=request.user)
    messages.warning(request, "⏸ Queue paused.")
    return redirect('dashboard')


@login_required
def resume_queue(request):
    services.resume_queue(performed_by=request.user)
    messages.success(request, "▶ Queue resumed.")
    return redirect('dashboard')


@login_required
def stop_queue(request):
    current = Patient.objects.filter(status='serving').first()
    if current:
        services.complete_patient(current.id, performed_by=request.user)
    services.pause_queue(performed_by=request.user)
    messages.info(request, "Queue stopped.")
    return redirect('dashboard')


def patient_dashboard(request, token):
    patient  = get_object_or_404(Patient, token_number=token)
    position, ahead, eta = services.compute_position_and_eta(patient)
    current  = Patient.objects.filter(status='serving').first()
    return render(request, 'patient/waiting_room.html', {
        'patient':       patient,
        'position':      position,
        'ahead':         ahead,
        'eta':           eta,
        'current_token': current,
        'token_json':    token,
    })


def patient_status_api(request, token):
    try:
        patient = Patient.objects.get(token_number=token)
    except Patient.DoesNotExist:
        return JsonResponse({'error': 'Token not found'}, status=404)
    position, ahead, eta = services.compute_position_and_eta(patient)
    current = Patient.objects.filter(status='serving').first()
    return JsonResponse({
        'token':         patient.token_number,
        'name':          patient.name,
        'status':        patient.status,
        'priority':      patient.priority,
        'position':      position,
        'ahead':         ahead,
        'eta':           eta,
        'current_token': current.token_number if current else None,
    })


@login_required
def statistics_dashboard(request):

    DailyStatistics.update_statistics()

    selected_date = request.GET.get('date')

    if selected_date:

        selected_date_obj = datetime.strptime(
            selected_date,
            "%Y-%m-%d"
        ).date()

    else:

        selected_date_obj = timezone.localdate()

    patients = Patient.objects.filter(
        created_at__year=selected_date_obj.year,
        created_at__month=selected_date_obj.month,
        created_at__day=selected_date_obj.day
    ).order_by('token_number')

    print("DATE =", selected_date_obj)
    print("PATIENTS FOUND =", patients.count())

    context = {

        'total_patients': patients.count(),

        'waiting': patients.filter(
            status='waiting'
        ).count(),

        'served': patients.filter(
            status='completed'
        ).count(),

        'cancelled': patients.filter(
            status='cancelled'
        ).count(),

        'patients': patients,

        'selected_date': selected_date_obj,

        'analytics': {
            'avg_wait': 0,
            'completion_rate': 0
        },

        'throughput_json': '[]',

        'priority_json': '{"normal":0,"urgent":0,"emergency":0}'
    }

    return render(
        request,
        'receptionist/statistics.html',
        context
    )


@login_required
def queue_settings(request):
    settings = QueueSettings.get_settings()
    if request.method == 'POST':
        form = QueueSettingsForm(request.POST, instance=settings)
        if form.is_valid():
            form.save()
            QueueActionLog.objects.create(
                action='settings_changed', performed_by=request.user,
                description="Queue settings updated",
            )
            messages.success(request, "Settings saved.")
            return redirect('queue_settings')
    else:
        form = QueueSettingsForm(instance=settings)
    return render(request, 'receptionist/settings.html', {'form': form, 'settings': settings})


@login_required
def served_patients(request):
    patients = Patient.objects.filter(status='completed').order_by('-completed_at')
    return render(request, 'receptionist/served_patients.html', {'patients': patients})


@login_required
def audit_log(request):
    logs = QueueActionLog.objects.select_related('patient', 'performed_by').order_by('-timestamp')[:200]
    return render(request, 'receptionist/audit_log.html', {'logs': logs})
