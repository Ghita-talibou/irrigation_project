import math
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import Avg
from meteo.models import Model1_MeteoBase, Model2_Rayonnement, Model4_ET0


LATITUDE = 34.0   # provisoire
ALTITUDE = 500    # provisoire en mètres


def saturation_vapor_pressure(T):
    return 0.6108 * math.exp((17.27 * T) / (T + 237.3))


def calculer_et0_fao56(T, RH, u2_kmh, Rs_wm2, altitude, latitude_deg, day_of_year):
    # Vent km/h -> m/s
    u2 = u2_kmh / 3.6

    # Pression atmosphérique
    P = 101.3 * (((293 - 0.0065 * altitude) / 293) ** 5.26)

    # Constante psychrométrique
    gamma = 0.000665 * P

    # Pression vapeur saturante
    es = saturation_vapor_pressure(T)

    # Pression vapeur réelle
    ea = es * RH / 100

    # Pente courbe pression vapeur
    delta = 4098 * es / ((T + 237.3) ** 2)

    # Rayonnement solaire W/m² -> MJ/m²/jour
    Rs = Rs_wm2 * 0.0864 * 0.5

    # Latitude en radians
    phi = math.radians(latitude_deg)

    # Rayonnement extraterrestre Ra
    dr = 1 + 0.033 * math.cos((2 * math.pi / 365) * day_of_year)
    delta_s = 0.409 * math.sin((2 * math.pi / 365) * day_of_year - 1.39)
    ws = math.acos(-math.tan(phi) * math.tan(delta_s))

    Ra = (24 * 60 / math.pi) * 0.0820 * dr * (
        ws * math.sin(phi) * math.sin(delta_s)
        + math.cos(phi) * math.cos(delta_s) * math.sin(ws)
    )

    # Rayonnement ciel clair
    Rso = (0.75 + 2e-5 * altitude) * Ra

    # Rayonnement net court
    albedo = 0.23
    Rns = (1 - albedo) * Rs

    # Rayonnement net long
    sigma = 4.903e-9
    Tmax = T
    Tmin = T

    Rnl = sigma * (((Tmax + 273.16) ** 4 + (Tmin + 273.16) ** 4) / 2) * (
        0.34 - 0.14 * math.sqrt(ea)
    ) * (
        1.35 * min(Rs / Rso, 1) - 0.35
    )

    # Rayonnement net
    Rn = Rns - Rnl

    # Formule FAO-56 Penman-Monteith
    et0 = (
        (0.408 * delta * Rn)
        + (gamma * (900 / (T + 273)) * u2 * (es - ea))
    ) / (
        delta + gamma * (1 + 0.34 * u2)
    )

    return max(0, round(et0, 2))


class Command(BaseCommand):
    help = "Calcule ET0 journalier FAO-56"

    def handle(self, *args, **options):
        today = timezone.now().date()
        day_of_year = today.timetuple().tm_yday

        meteo_qs = Model1_MeteoBase.objects.filter(date_mesure__date=today)
        ray_qs = Model2_Rayonnement.objects.filter(date_mesure__date=today)

        if not meteo_qs.exists():
            self.stdout.write("Pas de données météo aujourd’hui pour ET0")
            return

        if not ray_qs.exists():
            self.stdout.write("Pas de données rayonnement aujourd’hui pour ET0")
            return

        temp_moy = meteo_qs.aggregate(moy=Avg("temperature"))["moy"]
        rh_moy = meteo_qs.aggregate(moy=Avg("humidite"))["moy"]
        wind_moy = meteo_qs.aggregate(moy=Avg("vent"))["moy"]
        radiation_moy = ray_qs.aggregate(moy=Avg("rayonnement"))["moy"]

        et0 = calculer_et0_fao56(
            T=temp_moy,
            RH=rh_moy,
            u2_kmh=wind_moy,
            Rs_wm2=radiation_moy,
            altitude=ALTITUDE,
            latitude_deg=LATITUDE,
            day_of_year=day_of_year
        )

        Model4_ET0.objects.update_or_create(
            date=today,
            defaults={
                "temp_moy": temp_moy,
                "rh_moy": rh_moy,
                "wind_moy": wind_moy,
                "radiation_moy": radiation_moy,
                "et0": et0,
            }
        )

        self.stdout.write(
            f"ET0 = {et0:.2f} mm/jour pour {today}"
        )