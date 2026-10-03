from django.contrib import admin
from .models import ModalidadeBolsa, Bolsa

@admin.register(ModalidadeBolsa)
class ModalidadeBolsaAdmin(admin.ModelAdmin):
    list_display = ('sigla', 'nome', 'ativo')
    search_fields = ('sigla', 'nome')

@admin.register(Bolsa)
class BolsaAdmin(admin.ModelAdmin):
    list_display = ('aluno', 'modalidade', 'projeto', 'status', 'data_inicio', 'data_fim')
    search_fields = ('aluno__nome', 'projeto__codigo')
    list_filter = ('status', 'modalidade', 'fomentador')
