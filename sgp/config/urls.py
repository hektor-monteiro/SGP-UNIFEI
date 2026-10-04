from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('apps.core.urls')),
    path('', include('apps.projetos.urls')),
    path('', include('apps.bolsas.urls')),
    path('', include('apps.relatorios.urls')),
    path('', include('apps.editais.urls')),
]
