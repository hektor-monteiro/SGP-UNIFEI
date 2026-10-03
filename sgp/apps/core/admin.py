from django.contrib import admin
from .models import Instituicao, Fomentador, ProcessoSipac

@admin.register(Instituicao)
class InstituicaoAdmin(admin.ModelAdmin):
    list_display = ('sigla', 'nome', 'ativo')
    search_fields = ('sigla', 'nome')

@admin.register(Fomentador)
class FomentadorAdmin(admin.ModelAdmin):
    list_display = ('sigla', 'nome', 'tipo', 'ativo')
    search_fields = ('sigla', 'nome')
    list_filter = ('tipo', 'ativo')

@admin.register(ProcessoSipac)
class ProcessoSipacAdmin(admin.ModelAdmin):
    list_display = ('numero', 'data_abertura')
    search_fields = ('numero',)
