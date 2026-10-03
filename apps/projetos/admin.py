from django.contrib import admin
from .models import Pessoa, Projeto, Proposta

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
