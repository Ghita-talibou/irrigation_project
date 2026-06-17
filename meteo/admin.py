from django.contrib import admin
from .models import Model1_MeteoBase, FWIDaily, Model4_ET0, Model5_BatteriePyra
from .models import CommandeLoRaWAN
admin.site.register(Model1_MeteoBase)
admin.site.register(FWIDaily)
admin.site.register(Model4_ET0)
admin.site.register(Model5_BatteriePyra)
@admin.register(CommandeLoRaWAN)
class CommandeLoRaWANAdmin(admin.ModelAdmin):
    list_display = ('date_commande', 'equipement', 'action', 'payload', 'duree', 'statut')
    list_filter = ('equipement', 'action', 'statut')
    search_fields = ('equipement', 'payload')