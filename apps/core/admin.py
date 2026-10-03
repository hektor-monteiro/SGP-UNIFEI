from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from .models import Instituicao, Fomentador, ProcessoSipac, Perfil

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

class PerfilInline(admin.StackedInline):
    model = Perfil
    can_delete = False
    verbose_name_plural = 'Perfil de acesso'
    fk_name = 'user'

admin.site.unregister(User)

@admin.register(User)
class UsuarioAdmin(UserAdmin):
    inlines = (PerfilInline,)
    list_display = ('username', 'email', 'first_name', 'last_name', 'get_perfil')

    @admin.display(description='Perfil')
    def get_perfil(self, obj):
        return obj.perfil.perfil if hasattr(obj, 'perfil') else '—'

@admin.register(Perfil)
class PerfilAdmin(admin.ModelAdmin):
    list_display = ('user', 'perfil', 'pessoa')
    list_filter = ('perfil',)
    search_fields = ('user__username', 'user__email', 'pessoa__nome')
    raw_id_fields = ('user', 'pessoa')
