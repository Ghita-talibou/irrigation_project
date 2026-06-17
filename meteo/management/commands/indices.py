from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import datetime, time
from meteo.models import Model1_MeteoBase, FWIDaily
from django.db.models import Sum
import math

def calculer_et0(donnees):
    # Penman-Monteith FAO-56
    gamma = 0.067  # kPa/°C
    Rn = donnees.rayonnement * 0.0864  # W/m² → MJ/m²/jour
    T = donnees.temperature
    u2 = donnees.vent / 3.6  # km/h → m/s
    HR = donnees.humidite

    es = 0.6108 * math.exp(17.27 * T / (T + 237.3))  # kPa
    ea = es * HR / 100
    delta = 4098 * es / (T + 237.3)**2  # kPa/°C

    et0 = (0.408 * delta * Rn + gamma * (900/(T+273)) * u2 * (es - ea)) / (delta + gamma * (1 + 0.34*u2))
    return max(et0, 0)

class Command(BaseCommand):
    help = 'Calcule FWI quotidien à 12h TU avec formule canadienne complète'
    def calc_bui(self, dmc, dc):
        """Build Up Index"""
        if dmc <= 0 or dc <= 0:
               return 0

        if dmc <= 0.4 * dc:
           bui = (0.8 * dmc * dc) / (dmc + 0.4 * dc)
        else:
           bui = dmc - (1 - (0.8 * dc) / (dmc + 0.4 * dc)) * (0.92 + (0.0114 * dmc) ** 1.7)

        return max(0, bui)

    def calc_ffmc(self, temp, rh, wind, rain, ffmc_prev=85.0):
        """Fine Fuel Moisture Code"""
        mo = 147.2 * (101 - ffmc_prev) / (59.5 + ffmc_prev)

        if rain > 0.5:
            rf = rain - 0.5
            mr = mo + 42.5 * rf * math.exp(-100 / (251 - mo)) * (1 - math.exp(-6.93 / rf))
            if mo <= 150:
                mo = mr + 0.0015 * (mo - 150)**2 * math.sqrt(rf)
            else:
                mo = mr + 0.0015 * (mo - 150)**2 * rf
            if mo > 250: mo = 250

        ed = 0.942 * rh**0.679 + 11 * math.exp((rh - 100) / 10) + 0.18 * (21.1 - temp) * (1 - math.exp(-0.115 * rh))
        ew = 0.618 * rh**0.753 + 10 * math.exp((rh - 100) / 10) + 0.18 * (21.1 - temp) * (1 - math.exp(-0.115 * rh))

        if mo < ed:
            k = 0.424 * (1 - (rh / 100)**1.7) + 0.0694 * math.sqrt(wind) * (1 - (rh / 100)**8)
            mo = ed - (ed - mo) * math.exp(-k * 1)
        elif mo > ew:
            k = 0.424 * (1 - ((100 - rh) / 100)**1.7) + 0.0694 * math.sqrt(wind) * (1 - ((100 - rh) / 100)**8)
            mo = ew - (ew - mo) * math.exp(-k * 1)

        ffmc = 59.5 * (250 - mo) / (147.2 + mo)
        return max(0, min(101, ffmc))

    def calc_dmc(self, temp, rh, rain, dmc_prev=6.0):
        """Duff Moisture Code"""
        if rain > 1.5:
            re = 0.92 * rain - 1.27
            mo = 20 + 280 / math.exp(0.023 * dmc_prev)
            b = 100 / (0.5 + 0.3 * dmc_prev) if dmc_prev <= 33 else 14 - 1.3 * math.log(dmc_prev)
            mr = mo + 1000 * re / (48.77 + b * re)
            pr = 244.72 - 43.43 * math.log(mr - 20)
            dmc = max(0, pr)
        else:
            dmc = dmc_prev

        k = 1.894 * (temp + 1.1) * (100 - rh) * 0.0001
        dmc += k
        return max(0, dmc)

    def calc_dc(self, temp, rain, dc_prev=15.0):
        """Drought Code"""
        if rain > 2.8:
            rd = 0.83 * rain - 1.27
            qo = 800 * math.exp(-dc_prev / 400)
            qr = qo + 3.937 * rd
            dc = 400 * math.log(800 / qr)
        else:
            dc = dc_prev

        v = 0.36 * (temp + 2.8) + 1.2
        dc += v
        return max(0, dc)

    def calc_isi(self, ffmc, wind):
        """Initial Spread Index"""
        m = 147.2 * (101 - ffmc) / (59.5 + ffmc)
        fw = math.exp(0.05039 * wind)
        fffmc = 91.9 * math.exp(-0.1386 * m) * (1 + m**5.31 / 4.93e7)
        isi = fffmc * fw
        return isi

    def calc_fwi(self, isi, b_ui):
        """Fire Weather Index - formule canadienne"""
        if b_ui <= 80:
            bb = 0.1 * isi * (0.626 * (b_ui ** 0.809) + 2)
        else:
            bb = 0.1 * isi * (1000 / (25 + 108.64 * math.exp(-0.023 * b_ui)))

        if bb <= 1:
           fwi = bb
        else:
           fwi = math.exp(2.72 * (0.434 * math.log(bb)) ** 0.647)

        return round(fwi, 1)

    def handle(self, *args, **options):
        today = timezone.now().date()

        # Données 12h TU
        data_12h = Model1_MeteoBase.objects.filter(
            date_mesure__date=today,
            date_mesure__time__gte=time(12, 0),
            date_mesure__time__lte=time(12, 59)
        ).first()

        if not data_12h:
            self.stdout.write(self.style.WARNING('Pas de données à 12h TU aujourd’hui'))
            return

        # Récupérer valeurs veille
        last_fwi = FWIDaily.objects.order_by('-date').first()
        ffmc_prev = 85.0
        dmc_prev = 6.0
        dc_prev = 15.0

        temp = data_12h.temperature
        rh = data_12h.humidite
        wind = data_12h.vent
        rain = Model1_MeteoBase.objects.filter(
        date_mesure__date=today
        ).aggregate(total=Sum('precipitation'))['total'] or 0

        # Calculs séquentiels
        ffmc = self.calc_ffmc(temp, rh, wind, rain, ffmc_prev)
        dmc = self.calc_dmc(temp, rh, rain, dmc_prev)
        dc = self.calc_dc(temp, rain, dc_prev)
        isi = self.calc_isi(ffmc, wind)
        b_ui = self.calc_bui(dmc, dc)
        fwi = self.calc_fwi(isi, b_ui)

        # Sauvegarder
        FWIDaily.objects.update_or_create(
            date=today,
            defaults={
                'heure_mesure': time(12, 0),
                'temp': temp,
                'rh': rh,
                'wind_kmh': wind,
                'rain_24h': rain,
                'fwi': fwi
            }
        )

        self.stdout.write(self.style.SUCCESS(f'FWI {fwi} calculé pour {today} - T:{temp}°C RH:{rh}% V:{wind}km/h'))