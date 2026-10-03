from django.contrib import admin
from .models import Edital, Avaliacao

@admin.register(Edital)
class EditalAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'titulo', 'status', 'data_inicio', 'data_fim')
    search_fields = ('codigo', 'titulo')
    list_filter = ('status', 'modalidade')

@admin.register(Avaliacao)
class AvaliacaoAdmin(admin.ModelAdmin):
    list_display = ('tipo', 'avaliador', 'nota', 'data_avaliacao')
    list_filter = ('tipo',)
