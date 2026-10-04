from django.urls import path
from . import views

urlpatterns = [
    path('indicadores/', views.indicadores, name='indicadores'),
    path('indicadores/csv/', views.indicadores_csv, name='indicadores_csv'),
    path('planos/', views.lista, name='planos_lista'),
    path('planos/novo/', views.novo, name='plano_novo'),
    path('planos/<uuid:pk>/', views.detalhe, name='plano_detalhe'),
    path('planos/<uuid:pk>/editar/', views.editar, name='plano_editar'),
    path('relatorios/', views.lista_relatorios, name='relatorios_lista'),
    path('relatorios/novo/', views.novo_relatorio, name='relatorio_novo'),
    path('relatorios/<uuid:pk>/', views.detalhe_relatorio, name='relatorio_detalhe'),
    path('relatorios/<uuid:pk>/editar/', views.editar_relatorio, name='relatorio_editar'),
    path('relatorios/<uuid:pk>/submeter/', views.submeter_relatorio, name='relatorio_submeter'),
    path('relatorios/<uuid:pk>/avaliar/', views.avaliar_relatorio, name='relatorio_avaliar'),
]
