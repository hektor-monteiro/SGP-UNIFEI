/**
 * Busca digitando em <select> de nomes (padrão do projeto).
 *
 * Todo <select class="busca-nome"> ganha um campo "Digite para filtrar…"
 * logo acima: as opções são filtradas enquanto o usuário digita, sem
 * diferenciar acento nem caixa, com contador de resultados e
 * autopreenchimento quando sobra um único nome compatível. O dropdown
 * continua existindo — sem digitar, o menu funciona como sempre.
 */
document.addEventListener('DOMContentLoaded', () => {
  const normalizar = (texto) =>
    String(texto || '')
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .toLowerCase();

  document.querySelectorAll('select.busca-nome').forEach((sel) => {
    if (sel.dataset.buscaPronta === '1') return;
    sel.dataset.buscaPronta = '1';

    const opcoes = Array.from(sel.options).filter((op) => op.value !== '');
    const total = opcoes.length;
    if (total === 0) return;

    const campo = document.createElement('input');
    campo.type = 'search';
    campo.className = 'busca-nome-campo';
    campo.placeholder = 'Digite para filtrar…';
    campo.setAttribute('aria-label', 'Filtrar nomes');
    if (sel.id) campo.setAttribute('aria-controls', sel.id);

    const info = document.createElement('div');
    info.className = 'busca-nome-info';
    info.setAttribute('aria-live', 'polite');
    info.textContent = `${total} ${total === 1 ? 'nome' : 'nomes'}`;

    sel.parentNode.insertBefore(campo, sel);
    sel.parentNode.insertBefore(info, sel);

    function filtrar() {
      const termo = normalizar(campo.value).trim();
      const correspondem = termo
        ? opcoes.filter((op) => normalizar(op.textContent).includes(termo))
        : opcoes;

      // Sobrou um único nome compatível? Já vem selecionado.
      if (termo && correspondem.length === 1) {
        sel.value = correspondem[0].value;
      }

      // O nome selecionado permanece visível: filtrar não desfaz a escolha.
      opcoes.forEach((op) => {
        const mostra = correspondem.includes(op) || op.selected;
        op.hidden = !mostra;
        op.disabled = !mostra;
      });

      info.classList.toggle(
        'busca-nome-info--vazio',
        Boolean(termo) && correspondem.length === 0,
      );
      if (!termo) {
        info.textContent = `${total} ${total === 1 ? 'nome' : 'nomes'}`;
      } else if (correspondem.length === 0) {
        info.textContent = 'Nenhum nome encontrado';
      } else {
        info.textContent = `${correspondem.length} de ${total} nomes`;
      }
    }

    campo.addEventListener('input', filtrar);
    campo.addEventListener('search', filtrar);
  });
});
