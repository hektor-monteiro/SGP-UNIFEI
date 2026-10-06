from django.urls import path
from . import views

urlpatterns = [
    path('editais/', views.lista, name='editais_lista'),
    path('editais/novo/', views.novo, name='edital_novo'),
    path('editais/<uuid:pk>/', views.detalhe, name='edital_detalhe'),
    path('editais/<uuid:pk>/editar/', views.editar, name='edital_editar'),
    path('editais/<uuid:pk>/acao/<str:acao>/', views.acao, name='edital_acao'),
    path('editais/<uuid:pk>/propostas/nova/', views.proposta_nova, name='proposta_nova'),
    path('propostas/<uuid:pk>/', views.proposta_detalhe, name='proposta_detalhe'),
    path('propostas/<uuid:pk>/editar/', views.proposta_editar, name='proposta_editar'),
    path('propostas/<uuid:pk>/indicar/', views.proposta_indicar, name='proposta_indicar'),
    path('propostas/<uuid:pk>/alocar/', views.proposta_alocar, name='proposta_alocar'),
    path('avaliacoes/<uuid:pk>/', views.avaliacao_detalhe, name='avaliacao_detalhe'),
    path('avaliacoes/<uuid:pk>/remover/', views.avaliacao_remover, name='avaliacao_remover'),
    path('criterios/', views.criterios_lista, name='criterios_lista'),
    path('criterios/novo/', views.criterio_novo, name='criterio_novo'),
    path('criterios/<uuid:pk>/editar/', views.criterio_editar, name='criterio_editar'),
]
