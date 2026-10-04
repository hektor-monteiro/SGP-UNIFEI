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
    path('lgpd/auditoria/', views.auditoria, name='auditoria'),
]
