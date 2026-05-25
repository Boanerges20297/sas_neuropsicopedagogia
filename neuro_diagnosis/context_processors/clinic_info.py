
from django.conf import settings

def clinic_details(request):
    return {
        'CLINICA_NOME': getattr(settings, 'CLINICA_NOME', 'Neuro-Diagnosis'),
        'PROFISSIONAL_NOME': getattr(settings, 'PROFISSIONAL_NOME', 'Neuropsicopedagoga'),
    }
