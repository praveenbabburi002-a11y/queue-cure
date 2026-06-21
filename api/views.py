from rest_framework.decorators import api_view
from rest_framework.response import Response

from queue_app.models import (
    Patient,
    QueueSettings
)

from .serializers import PatientSerializer


@api_view(["GET"])
def queue_status(request):

    waiting = Patient.objects.filter(
        status="waiting"
    ).count()

    serving = Patient.objects.filter(
        status="serving"
    ).first()

    completed = Patient.objects.filter(
        status="completed"
    ).count()

    return Response({

        "waiting": waiting,

        "served": completed,

        "current_token":
        serving.token_number
        if serving else None

    })


@api_view(["GET"])
def patient_status(
        request,
        token):

    try:

        patient = Patient.objects.get(
            token_number=token
        )

    except Patient.DoesNotExist:

        return Response({

            "error":
            "Patient not found"

        }, status=404)

    ahead = Patient.objects.filter(
        status='waiting',
        token_number__lt=token
    ).count()

    settings = QueueSettings.objects.first()

    avg = 10

    if settings:
        avg = settings.average_consultation_time

    serializer = PatientSerializer(
        patient
    )

    return Response({

        "patient":
        serializer.data,

        "ahead":
        ahead,

        "eta":
        ahead * avg

    })