from django.contrib import admin
from .models import PlanoTrabalho, Relatorio

@admin.register(PlanoTrabalho)
class PlanoTrabalhoAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'aluno', 'status', 'data_submissao')
    search_fields = ('titulo', 'aluno__nome')
    list_filter = ('status',)

@admin.register(Relatorio)
class RelatorioAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'aluno', 'tipo', 'status', 'data_submissao')
    search_fields = ('titulo', 'aluno__nome')
    list_filter = ('tipo', 'status')
