from django import forms
from .models import Patient, QueueSettings


class PatientForm(forms.ModelForm):
    class Meta:
        model  = Patient
        fields = ['name', 'age', 'phone_number', 'consultation_type', 'priority', 'notes']
        widgets = {
            'name':             forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Full name'}),
            'age':              forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'max': 130}),
            'phone_number':     forms.TextInput(attrs={'class': 'form-control', 'placeholder': '9876543210'}),
            'consultation_type': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. General, Cardiology'}),
            'priority':         forms.Select(attrs={'class': 'form-select'}),
            'notes':            forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Optional notes…'}),
        }


class QueueSettingsForm(forms.ModelForm):
    class Meta:
        model  = QueueSettings
        fields = ['average_consultation_time', 'clinic_name', 'doctor_name']
        widgets = {
            'average_consultation_time': forms.NumberInput(attrs={'class': 'form-control'}),
            'clinic_name':               forms.TextInput(attrs={'class': 'form-control'}),
            'doctor_name':               forms.TextInput(attrs={'class': 'form-control'}),
        }
