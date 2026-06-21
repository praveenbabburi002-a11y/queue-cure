from django.urls import path
from . import views

urlpatterns = [
    path('',                               views.dashboard,            name='dashboard'),
    path('add-patient/',                   views.add_patient,          name='add_patient'),
    path('call-next/',                     views.call_next,            name='call_next'),
    path('complete/<int:patient_id>/',     views.complete_patient,     name='complete_patient'),
    path('cancel/<int:patient_id>/',       views.cancel_patient,       name='cancel_patient'),
    path('skip/<int:patient_id>/',         views.skip_patient,         name='skip_patient'),
    path('patient/<int:token>/',           views.patient_dashboard,    name='patient_dashboard'),
    path('api/patient/<int:token>/status/', views.patient_status_api,  name='patient_status_api'),
    path('statistics/',                    views.statistics_dashboard, name='statistics_dashboard'),
    path('settings/',                      views.queue_settings,       name='queue_settings'),
    path('served-patients/',               views.served_patients,      name='served_patients'),
    path('audit-log/',                     views.audit_log,            name='audit_log'),
    path('pause-queue/',                   views.pause_queue,          name='pause_queue'),
    path('resume-queue/',                  views.resume_queue,         name='resume_queue'),
    path('stop-queue/',                    views.stop_queue,           name='stop_queue'),
]
