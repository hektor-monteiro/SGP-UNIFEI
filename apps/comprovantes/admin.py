from django.contrib import admin
from .models import Comprovante

@admin.register(Comprovante)
class ComprovanteAdmin(admin.ModelAdmin):
    list_display = ('tipo', 'pessoa', 'codigo_verificacao', 'emitido_em')
    search_fields = ('pessoa__nome', 'codigo_verificacao')
    list_filter = ('tipo',)
