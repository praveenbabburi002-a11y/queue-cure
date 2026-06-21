from django.urls import path

from . import views

urlpatterns = [

    path(
        'queue-status/',
        views.queue_status,
        name='queue_status'
    ),

    path(
        'patient-status/<int:token>/',
        views.patient_status,
        name='patient_status'
    ),

]