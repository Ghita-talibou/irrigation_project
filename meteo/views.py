from .services import fwi_deja_calcule_aujourdhui, et0_deja_calcule_aujourdhui
from django.core.management import call_command
from django.shortcuts import render, redirect
from .models import Model1_MeteoBase, FWIDaily, Model4_ET0, Model5_BatteriePyra, Model2_Rayonnement, CommandeLoRaWAN
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Max, Min, Avg
from django.db.models.functions import TruncDate
from datetime import timedelta, datetime
import json, random
from django.contrib.auth import authenticate, login, logout
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from .services_lora import envoyer_downlink_chirpstack

DEVICES = {
    "🔌 Relais": "ab7554dc00001075",
    "💧 Vanne 1": "ce7554dc00001057",
    "💧 Vanne 2": "2e3554dc00001057",
    "💧 Vanne 3": "1e4554dc00001057",
}

def login_view(request):
    error = None

    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            return redirect("dashboard")
        else:
            error = "Nom d'utilisateur ou mot de passe incorrect"

    return render(request, "meteo/login.html", {"error": error})


def logout_view(request):
    logout(request)
    return redirect("login")

def get_update_info(dt):
    if not dt:
        return {
            "text": "--",
            "time": None
        }

    diff = timezone.now() - dt
    minutes = int(diff.total_seconds() / 60)

    if minutes < 1:
        text = "À l'instant"

    elif minutes < 60:
        text = f"Il y a {minutes} min"

    elif minutes < 1440:
        heures = minutes // 60
        text = f"Il y a {heures} h"

    else:
        jours = minutes // 1440
        text = f"Il y a {jours} j"

    return {
        "text": text,
        "time": timezone.localtime(dt).strftime("%H:%M")
    }

@login_required
def dashboard(request):
    batterie_etat = None
    temp = None
    hum = None
    vent = None

    use_fake = False

    if use_fake:
        fake_data = []
        base_temp = 28 + random.uniform(-2, 2)

        for i in range(7):
            temp = round(base_temp + random.uniform(-3, 3), 1)
            hum = round(60 + random.uniform(-15, 15), 1)
            vent = round(random.uniform(2, 18), 1)
            rad = round(random.uniform(300, 850), 0)
            uv = round(random.uniform(2, 10), 1)
            rain = round(random.uniform(0, 2), 1)
            fake_data.append({
                'temp': temp,
                'hum': hum,
                'vent': vent,
                'rad': rad,
                'uv': uv,
                'rain': rain
            })

        temp_data = [d['temp'] for d in fake_data]
        hum_data = [d['hum'] for d in fake_data]
        wind_data = [d['vent'] for d in fake_data]
        rain_data = [d['rain'] for d in fake_data]
        rad_data = [d['rad'] for d in fake_data]
        uv_data = [d['uv'] for d in fake_data]

        last = fake_data[-1]
        meteo = None
        fwi = None
        et0 = None
        batterie = None
        packets_today = 0
        last_measure = None
        minutes_since_update = None
        last_update_time = None

    else:
        last_24h = Model1_MeteoBase.objects.order_by('-date_mesure')[:24][::-1]
        meteo = Model1_MeteoBase.objects.order_by('-date_mesure').first()

        fwi = FWIDaily.objects.filter(
            date__lte=timezone.now().date()
        ).order_by('-date').first()

        et0 = Model4_ET0.objects.order_by('-date').first()
        batterie = Model5_BatteriePyra.objects.order_by('-date_mesure').first()
        rayonnement_obj = Model2_Rayonnement.objects.order_by('-date_mesure').first()
        meteo_update = get_update_info(meteo.date_mesure if meteo else None)
        ray_update = get_update_info(rayonnement_obj.date_mesure if rayonnement_obj else None)
        batt_update = get_update_info(batterie.date_mesure if batterie else None)
        fwi_update = get_update_info(fwi.date_calcul if fwi else None)
        et0_update = get_update_info(et0.date_calcul if et0 else None)
        last_7_rayonnement = list(Model2_Rayonnement.objects.order_by('-date_mesure')[:7][::-1])
        last_7_meteo = list(Model1_MeteoBase.objects.order_by('-date_mesure')[:7][::-1])

        temp_data = [m.temperature for m in last_7_meteo] if last_7_meteo else []
        hum_data = [m.humidite for m in last_7_meteo] if last_7_meteo else []
        wind_data = [m.vent for m in last_7_meteo] if last_7_meteo else []
        rain_data = [m.precipitation for m in last_7_meteo] if last_7_meteo else []
        rad_data = [r.rayonnement for r in last_7_rayonnement] if last_7_rayonnement else []
        uv_data = [m.uv_index for m in last_7_meteo] if last_7_meteo else []

        packets_today = Model1_MeteoBase.objects.filter(
            date_mesure__date=timezone.now().date()
        ).count() if meteo else 0

        last = meteo
        last_measure = meteo

        minutes_since_update = None
        last_update_time = None

        if last_measure:
            diff = timezone.now() - last_measure.date_mesure
            minutes_since_update = int(diff.total_seconds() / 60)
            last_update_time = timezone.localtime(last_measure.date_mesure).strftime("%H:%M")

        batterie_etat = 'normal'
        if batterie and batterie.pourcentage:
            if batterie.pourcentage < 20:
                batterie_etat = 'critique'
            elif batterie.pourcentage < 40:
                batterie_etat = 'faible'

    last_temp = last.temperature if meteo else last['temp']
    last_hum = last.humidite if meteo else last['hum']
    last_vent = last.vent if meteo else last['vent']
    last_rain = last.precipitation if meteo else last['rain']
    last_rad = rayonnement_obj.rayonnement if not use_fake and rayonnement_obj else (last['rad'] if use_fake else 0)
    last_uv = last.uv_index if meteo else last['uv']
    last_fwi = fwi.fwi if fwi else round(random.uniform(10, 40), 1)
    last_et0 = et0.et0 if et0 else round(random.uniform(3, 7), 2)
    last_batt = batterie.pourcentage if batterie else random.randint(25, 95)
    last_batt_voltage = batterie.tension if batterie else 0

    cards = [
        {'title':'TEMPÉRATURE', 'value':last_temp, 'unit':'°C', 'max':50, 'icon':'thermometer-half', 'color':'text-danger', 'detail_url':'temp'},
        {'title':'HUMIDITÉ', 'value':last_hum, 'unit':'%', 'max':100, 'icon':'droplet-half', 'color':'text-primary', 'detail_url':'hum'},
        {'title':'VENT', 'value':last_vent, 'unit':'km/h', 'max':50, 'icon':'wind', 'color':'text-info', 'detail_url':'vent'},
        {'title':'PRÉCIPITATION', 'value':last_rain, 'unit':'mm', 'max':50, 'icon':'cloud-rain', 'color':'text-primary', 'detail_url':'precip'},
        {'title':'RAYONNEMENT', 'value':last_rad, 'unit':'W/m²', 'max':1200, 'icon':'brightness-high', 'color':'text-warning', 'detail_url':'rayonnement'},
        {'title':'UV', 'value':last_uv, 'unit':'', 'max':12, 'icon':'sunglasses', 'color':'text-warning', 'detail_url':'uv'},
        {'title':'FWI', 'value':last_fwi, 'unit':'', 'max':100, 'icon':'fire', 'color':'text-danger', 'detail_url':'fwi'},
        {'title':'ET0', 'value':last_et0, 'unit':'mm/j', 'max':20, 'icon':'droplet-half', 'color':'text-success', 'detail_url':'et0'},
        {'title':'BAT-PYRA', 'value':last_batt, 'unit':'%', 'max':100, 'icon':'battery-half', 'color':'text-success', 'detail_url':'batterie'},
    ]

    context = {
        'active_page': 'dashboard',
        'last_update': meteo.date_mesure if meteo else timezone.now(),

        'last_measure': last_measure,
        'minutes_since_update': minutes_since_update,
        'last_update_time': last_update_time,

        'meteo_update': meteo_update,
        'ray_update': ray_update,
        'batt_update': batt_update,
        'fwi_update': fwi_update,
        'et0_update': et0_update,

        'last_temp': last_temp,
        'last_humidity': last_hum,
        'last_wind': last_vent,
        'last_rain': last_rain,
        'last_radiation': last_rad,
        'last_uv': last_uv,
        'last_fwi': last_fwi,
        'last_et0': last_et0,
        'last_batterie': last_batt,
        'last_batt_voltage': last_batt_voltage,

        'cards': cards,
        'batterie_etat': batterie_etat,
        'packets_today': packets_today,

        'temp_data': json.dumps(temp_data),
        'hum_data': json.dumps(hum_data),
        'wind_data': json.dumps(wind_data),
        'rain_data': json.dumps(rain_data),
        'rad_data': json.dumps(rad_data),
        'uv_data': json.dumps(uv_data),
    }

    return render(request, 'meteo/dashboard.html', context)

@login_required
def detail(request, param=None):
    print("=== DETAIL CALLED ===")
    param = param or request.GET.get('param', 'temp')
    mapping = {
        'temp': {'field': 'temperature', 'label': 'Température', 'unit': '°C'},
        'temperature': {'field': 'temperature', 'label': 'Température', 'unit': '°C'},  # <-- AJOUTE CETTE LIGNE
        'hum': {'field': 'humidite', 'unit': '%', 'label': 'Humidité'},
        'vent': {'field': 'vent', 'unit': 'km/h', 'label': 'Vent'},
       'rain': {'field': 'precipitation', 'label': 'Pluie', 'unit': 'mm'},
     'precip': {'field': 'precipitation', 'label': 'Pluie', 'unit': 'mm'},  # ajoute ça
      'precipitation': {'field': 'precipitation', 'label': 'Pluie', 'unit': 'mm'},  # ajoute aussi si besoin
        'rad': {'field': 'rayonnement', 'unit': 'W/m²', 'label': 'Rayonnement'},
        'rayonnement': {'field': 'rayonnement', 'label': 'Rayonnement', 'unit': 'W/m²'},  # <-- corrige ici
      'radiation': {'field': 'rayonnement', 'label': 'Rayonnement', 'unit': 'W/m²'},  # alias
        'uv': {'field': 'uv_index', 'unit': '', 'label': 'UV'},
        't0': {'field': 'et0', 'unit': 'mm/jour', 'label': 'ETO'},
    }
    print("PARAM =", param)
    # === CAS FWI ===
    if param == 'fwi':
        date_debut_str = request.GET.get('date_debut')
        date_fin_str = request.GET.get('date_fin')
        period = request.GET.get('period', '30')
        if period == '7':
            date_debut = timezone.now().date() - timedelta(days=7)
            date_fin = timezone.now().date()
        elif period == '30':
            date_debut = timezone.now().date() - timedelta(days=30)
            date_fin = timezone.now().date()
        elif period == '90':
            date_debut = timezone.now().date() - timedelta(days=90)
            date_fin = timezone.now().date()
        else:
            date_debut = datetime.strptime(date_debut_str, '%Y-%m-%d').date() if date_debut_str else timezone.now().date() - timedelta(days=30)
            date_fin = datetime.strptime(date_fin_str, '%Y-%m-%d').date() if date_fin_str else timezone.now().date()
        qs = FWIDaily.objects.filter(date__gte=date_debut, date__lte=date_fin).order_by('date')
        labels = [d.date.strftime('%d/%m/%Y') for d in qs]
        data = [float(d.fwi) for d in qs]
        fwi_data = qs
        dernier_fwi = qs.last()
        context = {
            'param': param,
            'label': 'FWI',
            'unit': '',
            'labels': json.dumps(labels),
            'data': json.dumps(data),
            'fwi_data': fwi_data,
            'dernier_fwi': dernier_fwi,
            'date_debut': date_debut.strftime('%Y-%m-%d'),
            'date_fin': date_fin.strftime('%Y-%m-%d'),
        }
        return render(request, 'meteo/detail.html', context)

        # === CAS RAYONNEMENT ===
    elif param == 'rayonnement' or param == 'rad' or param == 'radiation':
        date_debut_str = request.GET.get('date_debut')
        date_fin_str = request.GET.get('date_fin')
        period = request.GET.get('period', '30')

        if period == '7':
            date_debut = timezone.now().date() - timedelta(days=7)
            date_fin = timezone.now().date()
        elif period == '30':
            date_debut = timezone.now().date() - timedelta(days=30)
            date_fin = timezone.now().date()
        elif period == '90':
            date_debut = timezone.now().date() - timedelta(days=90)
            date_fin = timezone.now().date()
        else:
            date_debut = datetime.strptime(date_debut_str, '%Y-%m-%d').date() if date_debut_str else timezone.now().date() - timedelta(days=30)
            date_fin = datetime.strptime(date_fin_str, '%Y-%m-%d').date() if date_fin_str else timezone.now().date()

        qs = Model2_Rayonnement.objects.filter(
            date_mesure__date__gte=date_debut,
            date_mesure__date__lte=date_fin
        ).order_by('date_mesure')

        labels = [timezone.localtime(d.date_mesure).strftime('%d/%m %Hh%M') for d in qs]
        data = [float(d.rayonnement) for d in qs]

        historique_jour = Model2_Rayonnement.objects.filter(
            date_mesure__date__gte=date_debut,
            date_mesure__date__lte=date_fin
        ).annotate(
            jour=TruncDate('date_mesure')
        ).values('jour').annotate(
            max_val=Max('rayonnement'),
            min_val=Min('rayonnement'),
            avg_val=Avg('rayonnement')
        ).order_by('-jour')

        context = {
            'param': 'rayonnement',
            'label': 'Rayonnement',
            'unit': 'W/m²',
            'labels': json.dumps(labels),
            'data': json.dumps(data),
            'historique': historique_jour,
            'date_debut': date_debut.strftime('%Y-%m-%d'),
            'date_fin': date_fin.strftime('%Y-%m-%d'),
        }

        return render(request, 'meteo/detail.html', context)

    # === CAS ET0 ===
    elif param == 'et0':
        date_debut_str = request.GET.get('date_debut')
        date_fin_str = request.GET.get('date_fin')
        period = request.GET.get('period', '30')
        if period == '7':
            date_debut = timezone.now().date() - timedelta(days=7)
            date_fin = timezone.now().date()
        elif period == '30':
            date_debut = timezone.now().date() - timedelta(days=30)
            date_fin = timezone.now().date()
        elif period == '90':
            date_debut = timezone.now().date() - timedelta(days=90)
            date_fin = timezone.now().date()
        else:
            date_debut = datetime.strptime(date_debut_str, '%Y-%m-%d').date() if date_debut_str else timezone.now().date() - timedelta(days=30)
            date_fin = datetime.strptime(date_fin_str, '%Y-%m-%d').date() if date_fin_str else timezone.now().date()
        qs = Model4_ET0.objects.filter(date__gte=date_debut, date__lte=date_fin).order_by('date')
        labels = [d.date.strftime('%d/%m/%Y') for d in qs]
        data = [float(d.et0) if d.et0 else 0 for d in qs]
        et0_data = qs
        dernier_et0 = qs.last()
        context = {
            'param': param,
            'label': 'ET0',
            'unit': 'mm/jour',
            'labels': json.dumps(labels),
            'data': json.dumps(data),
            'et0_data': et0_data,
            'dernier_et0': dernier_et0,
            'date_debut': date_debut.strftime('%Y-%m-%d'),
            'date_fin': date_fin.strftime('%Y-%m-%d'),
        }
        return render(request, 'meteo/detail.html', context)

    elif param == 'batterie':
         date_debut_str = request.GET.get('date_debut')
         date_fin_str = request.GET.get('date_fin')
         period = request.GET.get('period', '30')

         if period == '7':
             date_debut = timezone.now().date() - timedelta(days=7)
             date_fin = timezone.now().date()
         elif period == '30':
             date_debut = timezone.now().date() - timedelta(days=30)
             date_fin = timezone.now().date()
         elif period == '90':
             date_debut = timezone.now().date() - timedelta(days=90)
             date_fin = timezone.now().date()
         else:
            date_debut = datetime.strptime(date_debut_str, '%Y-%m-%d').date() if date_debut_str else timezone.now().date() - timedelta(days=30)
            date_fin = datetime.strptime(date_fin_str, '%Y-%m-%d').date() if date_fin_str else timezone.now().date()

         qs = Model5_BatteriePyra.objects.filter(
         date_mesure__date__gte=date_debut,
         date_mesure__date__lte=date_fin
         ).order_by('date_mesure')

         labels = [d.date_mesure.strftime('%d/%m %Hh%M') for d in qs]
         data_pourcentage = [d.pourcentage for d in qs]
         data_voltage = [float(d.tension) for d in qs]

         context = {
             'param': param,
             'label': 'BAT-PYRA',
             'unit': '%',
             'labels': json.dumps(labels),
             'data_pourcentage': json.dumps(data_pourcentage),
             'data_voltage': json.dumps(data_voltage),
             'data': qs,
             'date_debut': date_debut.strftime('%Y-%m-%d'),
             'date_fin': date_fin.strftime('%Y-%m-%d'),
            }

         return render(request, 'meteo/detail.html', context)
    # === AUTRES PARAMS ===
    else:
        field = mapping[param]['field']
        date_debut_str = request.GET.get('date_debut')
        date_fin_str = request.GET.get('date_fin')
        period = request.GET.get('period', '30')

        if period == '7':
           date_debut = timezone.now().date() - timedelta(days=7)
           date_fin = timezone.now().date()
        elif period == '30':
             date_debut = timezone.now().date() - timedelta(days=30)
             date_fin = timezone.now().date()
        elif period == '90':
             date_debut = timezone.now().date() - timedelta(days=90)
             date_fin = timezone.now().date()
        else:
            date_debut = datetime.strptime(date_debut_str, '%Y-%m-%d').date() if date_debut_str else timezone.now().date() - timedelta(days=30)
            date_fin = datetime.strptime(date_fin_str, '%Y-%m-%d').date() if date_fin_str else timezone.now().date()

    # Choix du modèle + champ date
    if param == 't0':
        Model = Model4_ET0
        date_field = 'date'
    elif param == 'batterie':
        Model = Model5_BatteriePyra
        date_field = 'date_mesure'
    else:
        Model = Model1_MeteoBase
        date_field = 'date_mesure'

    qs = Model.objects.filter(
        **{f'{date_field}__date__gte': date_debut, f'{date_field}__date__lte': date_fin}
    ).order_by(date_field)

    labels = [timezone.localtime(d.date_mesure).strftime('%d/%m %Hh%M') for d in qs]
    data = [getattr(d, field) for d in qs]

    historique_jour = Model.objects.filter(
        **{f'{date_field}__date__gte': date_debut, f'{date_field}__date__lte': date_fin}
    ).annotate(
        jour=TruncDate(date_field)
    ).values('jour').annotate(
        max_val=Max(field),
        min_val=Min(field),
        avg_val=Avg(field)
    ).order_by('-jour')

    context = {
        'param': param,
        'label': mapping[param]['label'],
        'unit': mapping[param]['unit'],
        'labels': json.dumps(labels),
        'data': json.dumps(data),
        'historique': historique_jour,
        'date_debut': date_debut.strftime('%Y-%m-%d'),
        'date_fin': date_fin.strftime('%Y-%m-%d'),
    }
    return render(request, 'meteo/detail.html', context)

from django.views.decorators.http import require_POST

WsSENSECAP_WeatherStation = '2cf7f1c04430038d'
pyraGV = 'a84041fc4188657b'

@csrf_exempt
@require_POST
def v_chirpstack(request):
    try:
        print("********************** uplink")

        data = json.loads(request.body.decode("utf-8"))
        print("OBJECT RECU =", data.get("object", {}))

        event = request.GET.get("event")
        if event != "up":
            return JsonResponse({
                "status": "ignored",
                "message": "Event ignoré",
                "event": event
            })

        dev_eui = data.get("deviceInfo", {}).get("devEui")
        print("devEUI =", dev_eui)

        # === CAS 1 : PYRANOMÈTRE GREEN VISION ===
        if dev_eui == pyraGV:
            input_mA = float(data["object"]["IDC_intput_mA"])
            ray = 2000 * (1 + (input_mA - 20) / 16)
            bat_v = data["object"].get("Bat_V")

            ray_obj = Model2_Rayonnement.objects.create(
                rayonnement=round(ray, 2)
            )

            if bat_v is not None:

                pourcentage = round(
                  ((float(bat_v) - 3.0) / (4.2 - 3.0)) * 100
                )

                pourcentage = max(0, min(100, pourcentage))

                Model5_BatteriePyra.objects.create(
                    tension=float(bat_v),
                    pourcentage=pourcentage
                )

            print("Rayonnement enregistré :", ray_obj)

            return JsonResponse({
                "status": "ok",
                "message": "Données Green Vision enregistrées",
                "devEui": dev_eui,
                "rayonnement": round(ray, 2),
                "bat_v": bat_v
            })

        # === CAS 2 : STATION MÉTÉO SENSECAP ===
        if dev_eui != WsSENSECAP_WeatherStation:
            return JsonResponse({
                "status": "ignored",
                "message": "Device non concerné",
                "devEui": dev_eui
            })

        messages = data.get("object", {}).get("messages", [])
        print("messages:", messages)

        airTemp = None
        airHum = None
        windSpeed = None
        rainfall = None
        uv = None
        pressure = None
        bat = None
        batt_mesure = False

        for message in messages:
            for measurement in message:
                if "Battery(%)" in measurement and not batt_mesure:
                    bat = measurement.get("Battery(%)")
                    batt_mesure = True
                    continue

                type_mesure = measurement.get("type")
                valeur = measurement.get("measurementValue")

                print(type_mesure, valeur)

                if type_mesure == "Air Temperature":
                    airTemp = valeur

                elif type_mesure == "Air Humidity":
                    airHum = valeur

                elif type_mesure == "UV Index":
                    uv = valeur

                elif type_mesure == "Wind Speed":
                    windSpeed = valeur

                elif type_mesure == "Rain Gauge":
                    rainfall = valeur
                    print("rain_fall : sense cap :", rainfall, type(rainfall))

                elif type_mesure == "Barometric Pressure":
                    pressure = valeur

        if airTemp is None or airHum is None or windSpeed is None:
            return JsonResponse({
                "status": "error",
                "message": "Température, humidité ou vent manquant",
                "received": data
            }, status=400)

        meteo = Model1_MeteoBase.objects.create(
            temperature=float(airTemp),
            humidite=float(airHum),
            vent=round(float(windSpeed) * 3.6, 4),
            precipitation=float(rainfall) if rainfall is not None else 0,
            uv_index=float(uv) if uv is not None else 0,
        )
        now_local = timezone.localtime()

        if now_local.hour == 12 and not fwi_deja_calcule_aujourdhui():
            call_command('indices')
            print("FWI calculé automatiquement")

        if now_local.hour >= 23 and not et0_deja_calcule_aujourdhui():
            call_command('calcul_et0')
            print("ET0 calculé automatiquement")

        if bat is not None:
            Model5_BatteriePyra.objects.create(
                tension=0,
                pourcentage=int(float(bat))
            )

        return JsonResponse({
            "status": "ok",
            "message": "Données SenseCAP enregistrées",
            "meteo_id": meteo.id,
            "devEui": dev_eui,
            "temperature": airTemp,
            "humidite": airHum,
            "vent_kmh": round(float(windSpeed) * 3.6, 4),
            "pluie": rainfall,
            "uv": uv,
            "batterie": bat,
            "pression": pressure
        })

    except Exception as e:
        print("ERREUR CHIRPSTACK:", e)
        return JsonResponse({
            "status": "error",
            "message": str(e)
        }, status=400)

@login_required
def commande_lorawan(request):

    commandes = CommandeLoRaWAN.objects.all()[:3]

    return render(
        request,
        'meteo/commande_lorawan.html',
        {
            'commandes': commandes
        }
    )
@login_required
def enregistrer_commande_lora(request):

    if request.method == "POST":

        data = json.loads(request.body)

        commande = CommandeLoRaWAN.objects.create(
            equipement=data.get("equipement"),
            action=data.get("action"),
            payload=data.get("payload"),
            duree=data.get("duree"),
            statut="EN_ATTENTE"
        )

        dev_eui = DEVICES.get(data.get("equipement"))

        if dev_eui:
            resultat = envoyer_downlink_chirpstack(
                dev_eui,
                data.get("payload")
            )

            if resultat["success"]:
                commande.statut = "ENVOYEE"
            else:
               commande.statut = "ERREUR"
               print(resultat["message"])

            commande.save()

        return JsonResponse({
            "status": "success"
        })

    return JsonResponse({
        "status": "error"
    })
@login_required
def historique_commandes_lora(request):
    commandes = CommandeLoRaWAN.objects.all()

    equipement = request.GET.get("equipement")
    action = request.GET.get("action")

    if equipement:
        commandes = commandes.filter(equipement__icontains=equipement)

    if action:
        commandes = commandes.filter(action=action)

    return render(request, "meteo/historique_commandes_lora.html", {
        "commandes": commandes,
        "equipement": equipement,
        "action": action,
        "active_page": "lorawan",
    })