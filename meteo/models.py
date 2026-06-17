from django.db import models

class Model1_MeteoBase(models.Model):
    date_mesure = models.DateTimeField(auto_now_add=True)
    temperature = models.FloatField(help_text="En °C")
    humidite = models.FloatField(help_text="En %")
    vent = models.FloatField(help_text="En km/h")
    precipitation = models.FloatField(help_text="En mm", null=True, blank=True)
    rayonnement = models.FloatField(help_text="Rayonnement solaire W/m²", null=True, blank=True)
    uv_index = models.FloatField(help_text="Indice UV 0-11+", null=True, blank=True)

    def __str__(self):
        return f"Meteo {self.date_mesure.strftime('%d/%m %H:%M')}"

class FWIDaily(models.Model):
    date = models.DateField(unique=True, verbose_name="Date")
    heure_mesure = models.TimeField(default='12:00', verbose_name="Heure TU")
    temp = models.FloatField(verbose_name="Temp 12h TU °C", null=True)
    rh = models.FloatField(verbose_name="HR 12h TU %", null=True)
    wind_kmh = models.FloatField(verbose_name="Vent 12h TU km/h", null=True)
    rain_24h = models.FloatField(verbose_name="Pluie 24h mm", null=True)

    fwi = models.FloatField(verbose_name="FWI", null=True)
    date_calcul = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f"FWI {self.fwi} le {self.date}"

class Model4_ET0(models.Model):
    date = models.DateField(null=True, blank=True, unique=True, verbose_name="Date")
    temp_moy = models.FloatField(verbose_name="Température moyenne (°C)", null=True, blank=True)
    rh_moy = models.FloatField(verbose_name="HR moyenne (%)", null=True, blank=True)
    wind_moy = models.FloatField(verbose_name="Vent moyen (km/h)", null=True, blank=True)
    radiation_moy = models.FloatField(verbose_name="Rayonnement moyen (W/m²)", null=True, blank=True)
    et0 = models.FloatField(verbose_name="ET0 (mm/jour)", null=True, blank=True)
    date_calcul = models.DateTimeField(auto_now=True)
    class Meta:
        ordering = ['-date']
        verbose_name = "ET0 Journalier"

    def __str__(self):
        return f"ET0 {self.et0} mm/j le {self.date}"

class Model5_BatteriePyra(models.Model):
    date_mesure = models.DateTimeField(auto_now_add=True)
    tension = models.FloatField(help_text="Tension en Volts, ex: 3.7")
    pourcentage = models.IntegerField(help_text="Niveau batterie 0 à 100%")
    etat = models.CharField(max_length=20, choices=[
        ('ok', 'OK'),
        ('faible', 'Batterie Faible'),
        ('critique', 'Critique')
    ], default='ok')

    def save(self, *args, **kwargs):
        # Calcule l'état automatiquement selon le %
        if self.pourcentage < 20:
            self.etat = 'critique'
        elif self.pourcentage < 40:
            self.etat = 'faible'
        else:
            self.etat = 'ok'
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Batterie Pyra {self.pourcentage}% - {self.date_mesure.strftime('%d/%m %H:%M')}"

class Model2_Rayonnement(models.Model):
    date_mesure = models.DateTimeField(auto_now_add=True)
    rayonnement = models.FloatField(help_text="Rayonnement solaire W/m²")

    def __str__(self):
        return f"Rayonnement {self.rayonnement} W/m²"
class CommandeLoRaWAN(models.Model):
    date_commande = models.DateTimeField(auto_now_add=True)

    equipement = models.CharField(max_length=100)

    action = models.CharField(max_length=50)

    payload = models.CharField(max_length=50)

    duree = models.IntegerField(
        null=True,
        blank=True
    )

    statut = models.CharField(
        max_length=50,
        default="Préparée"
    )

    def __str__(self):
        return f"{self.equipement} - {self.payload}"