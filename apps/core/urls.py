from django.contrib.auth import views as auth_views
from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('painel/', views.dashboard, name='dashboard'),
    path(
        'contas/entrar/',
        auth_views.LoginView.as_view(template_name='registration/login.html'),
        name='login',
    ),
    path('contas/sair/', auth_views.LogoutView.as_view(), name='logout'),
    # LGPD (§6)
    path('lgpd/', views.lgpd_pagina, name='lgpd'),
    path('lgpd/meus-dados/', views.lgpd_meus_dados, name='lgpd_meus_dados'),
    path('lgpd/consentimento/', views.lgpd_consentimento, name='lgpd_consentimento'),
    path(
        'lgpd/consentimento/revogar/',
        views.lgpd_revogar_consentimento,
        name='lgpd_revogar_consentimento',
    ),
    path('lgpd/solicitacoes/', views.solicitacoes_lista, name='lgpd_solicitacoes'),
    path(
        'lgpd/solicitacoes/nova/',
        views.solicitacao_nova,
        name='lgpd_solicitacao_nova',
    ),
    path(
        'lgpd/solicitacoes/<uuid:pk>/',
        views.solicitacao_detalhe,
        name='lgpd_solicitacao_detalhe',
    ),
    path(
        'lgpd/solicitacoes/<uuid:pk>/tratar/',
        views.solicitacao_tratar,
        name='lgpd_solicitacao_tratar',
    ),
    path('lgpd/auditoria/', views.auditoria, name='auditoria'),
]
