from django.urls import path
from . import views

urlpatterns = [
    path('bolsas/', views.lista, name='bolsas_lista'),
    path('bolsas/nova/', views.nova, name='bolsa_nova'),
    path('bolsas/<uuid:pk>/', views.detalhe, name='bolsa_detalhe'),
    path('bolsas/<uuid:pk>/editar/', views.editar, name='bolsa_editar'),
]
