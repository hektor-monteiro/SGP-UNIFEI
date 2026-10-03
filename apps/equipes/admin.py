from django.contrib import admin
from .models import MembroEquipe

@admin.register(MembroEquipe)
class MembroEquipeAdmin(admin.ModelAdmin):
    list_display = ('pessoa', 'projeto', 'funcao', 'data_entrada', 'ativo')
    search_fields = ('pessoa__nome', 'projeto__codigo')
    list_filter = ('funcao', 'ativo')
