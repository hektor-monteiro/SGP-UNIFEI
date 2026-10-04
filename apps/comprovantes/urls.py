from django.urls import path
from . import views

urlpatterns = [
    path('comprovantes/', views.lista, name='comprovantes_lista'),
    path('comprovantes/emitir/bolsa/', views.emitir_bolsa, name='comprovante_emitir_bolsa'),
    path('comprovantes/emitir/participacao/', views.emitir_participacao, name='comprovante_emitir_participacao'),
    path('comprovantes/emitir/avaliacao/', views.emitir_avaliacao, name='comprovante_emitir_avaliacao'),
    path('comprovantes/verificar/<str:codigo>/', views.verificar, name='comprovante_verificar'),
    path('comprovantes/<uuid:pk>/', views.detalhe, name='comprovante_detalhe'),
]
