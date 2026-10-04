from django.urls import path
from . import views

urlpatterns = [
    path(
        'projetos/<uuid:projeto_pk>/equipe/novo/',
        views.membro_novo,
        name='membro_novo',
    ),
    path('equipes/<uuid:pk>/editar/', views.membro_editar, name='membro_editar'),
    path('equipes/<uuid:pk>/encerrar/', views.membro_encerrar, name='membro_encerrar'),
    path('equipes/<uuid:pk>/excluir/', views.membro_excluir, name='membro_excluir'),
]
