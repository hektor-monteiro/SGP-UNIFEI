from django.urls import path
from . import views

urlpatterns = [
    path('bolsas/modalidades/', views.modalidade_lista, name='modalidades_lista'),
    path('bolsas/modalidades/nova/', views.modalidade_nova, name='modalidade_nova'),
    path('bolsas/modalidades/<uuid:pk>/editar/', views.modalidade_editar, name='modalidade_editar'),
    path('bolsas/', views.lista, name='bolsas_lista'),
    path('bolsas/nova/', views.nova, name='bolsa_nova'),
    path('bolsas/<uuid:pk>/', views.detalhe, name='bolsa_detalhe'),
    path('bolsas/<uuid:pk>/editar/', views.editar, name='bolsa_editar'),
]
