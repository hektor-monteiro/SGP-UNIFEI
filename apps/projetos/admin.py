from django.contrib import admin
from .models import (
    AreaConhecimento,
    GrandeAreaConhecimento,
    ODS,
    Pessoa,
    Projeto,
    Proposta,
    SubareaConhecimento,
)

@admin.register(Pessoa)
class PessoaAdmin(admin.ModelAdmin):
    list_display = ('nome', 'email', 'tipo', 'matricula', 'ativo')
    search_fields = ('nome', 'email', 'matricula')
    list_filter = ('tipo', 'ativo')

@admin.register(Projeto)
class ProjetoAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'titulo', 'status', 'coordenador', 'data_inicio')
    search_fields = ('codigo', 'titulo')
    list_filter = ('status', 'instituicao')

@admin.register(Proposta)
class PropostaAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'submetido_por', 'status', 'data_submissao')
    search_fields = ('titulo',)
    list_filter = ('status',)

@admin.register(ODS)
class ODSAdmin(admin.ModelAdmin):
    list_display = ('numero', 'nome')
    ordering = ('numero',)

@admin.register(GrandeAreaConhecimento)
class GrandeAreaConhecimentoAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'nome')
    search_fields = ('nome',)

@admin.register(AreaConhecimento)
class AreaConhecimentoAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'nome', 'grande_area')
    list_filter = ('grande_area',)
    search_fields = ('nome',)

@admin.register(SubareaConhecimento)
class SubareaConhecimentoAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'nome', 'area')
    list_filter = ('area__grande_area',)
    search_fields = ('nome',)
