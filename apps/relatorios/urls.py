from django.urls import path
from . import views

urlpatterns = [
    path('planos/', views.lista, name='planos_lista'),
    path('planos/novo/', views.novo, name='plano_novo'),
    path('planos/<uuid:pk>/', views.detalhe, name='plano_detalhe'),
    path('planos/<uuid:pk>/editar/', views.editar, name='plano_editar'),
]
