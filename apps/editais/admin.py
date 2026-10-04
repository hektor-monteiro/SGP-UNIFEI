from django.contrib import admin
from .models import Edital, Avaliacao, CriterioAvaliacao, NotaCriterio

@admin.register(Edital)
class EditalAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'titulo', 'status', 'data_inicio', 'data_fim', 'nota_minima')
    search_fields = ('codigo', 'titulo')
    list_filter = ('status', 'modalidade')

@admin.register(Avaliacao)
class AvaliacaoAdmin(admin.ModelAdmin):
    list_display = ('tipo', 'avaliador', 'status', 'nota', 'data_avaliacao', 'data_conclusao')
    list_filter = ('tipo', 'status')

@admin.register(CriterioAvaliacao)
class CriterioAvaliacaoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'peso', 'ativo')
    list_filter = ('ativo',)

@admin.register(NotaCriterio)
class NotaCriterioAdmin(admin.ModelAdmin):
    list_display = ('avaliacao', 'criterio', 'nota')
