from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.views.decorators.cache import never_cache

from apps.projetos.models import Projeto, Pessoa
from apps.bolsas.models import Bolsa
from apps.editais.models import Edital
from apps.relatorios.models import PlanoTrabalho


def index(request):
    """Página inicial (pública)."""
    if request.user.is_authenticated:
        return render(request, 'core/index.html')
    return render(request, 'core/index.html')


@login_required
@never_cache
def dashboard(request):
    """Painel do usuário autenticado com resumo de dados conforme seu perfil."""
    perfil = getattr(request.user, 'perfil', None)
    contexto = {
        'perfil': perfil,
        'e_superuser': request.user.is_superuser,
    }

    # Dados visíveis conforme nível hierárquico
    if request.user.is_superuser or (perfil and perfil.pelo_menos('tecnico')):
        contexto.update({
            'total_projetos': Projeto.objects.count(),
            'total_bolsas': Bolsa.objects.filter(status='ativa').count(),
            'total_editais': Edital.objects.count(),
            'total_pessoas': Pessoa.objects.count(),
            'mostrar_tudo': True,
        })
    elif perfil and perfil.perfil == 'docente':
        # Docente vê apenas seus projetos (vínculo via Perfil.pessoa;
        # NÃO filtrar por e-mail: o e-mail do usuário pode diferir do da Pessoa)
        meus_projetos = (
            Projeto.objects.filter(coordenador=perfil.pessoa)
            if perfil.pessoa
            else Projeto.objects.none()
        )
        contexto.update({
            'meus_projetos': meus_projetos,
            'total_projetos': meus_projetos.count(),
            'mostrar_meus_projetos': True,
        })
    else:
        # Aluno: vê seus planos de trabalho; relatórios e comprovantes depois
        planos = (
            PlanoTrabalho.objects.filter(aluno=perfil.pessoa).select_related('bolsa__modalidade')
            if perfil and perfil.pessoa else PlanoTrabalho.objects.none()
        )
        contexto.update({'mostrar_aluno': True, 'meus_planos': planos})

    return render(request, 'core/dashboard.html', contexto)
