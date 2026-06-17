from django.utils import timezone
from meteo.models import FWIDaily, Model4_ET0

def fwi_deja_calcule_aujourdhui():
    today = timezone.now().date()
    return FWIDaily.objects.filter(date=today).exists()

def et0_deja_calcule_aujourdhui():
    today = timezone.now().date()
    return Model4_ET0.objects.filter(date=today).exists()