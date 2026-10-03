from django.urls import path
from . import views

urlpatterns = [
    path('projetos/', views.lista, name='projetos_lista'),
    path('projetos/novo/', views.novo, name='projeto_novo'),
    path('projetos/<uuid:pk>/', views.detalhe, name='projeto_detalhe'),
    path('projetos/<uuid:pk>/editar/', views.editar, name='projeto_editar'),
]
