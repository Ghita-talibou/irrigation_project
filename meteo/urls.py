from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('detail/<str:param>/', views.detail, name='detail'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('chirpstack/', views.v_chirpstack, name='chirpstack'),
    path('chirpstack', views.v_chirpstack),
    path('commande-lorawan/', views.commande_lorawan, name='commande_lorawan'),
    path(
    'enregistrer-commande-lora/',
    views.enregistrer_commande_lora,
    name='enregistrer_commande_lora'
    ),
    path(
    'historique-commandes-lora/',
    views.historique_commandes_lora,
    name='historique_commandes_lora'
   ),
]
