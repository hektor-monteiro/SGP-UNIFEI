/**
 * Cascata Grande Área → Área → Subárea (tabela de Áreas do Conhecimento
 * do CNPq). Filtra as opções dos <select> pelo mapa id→pai embutido no
 * template (json_script), sem dependências externas.
 */
document.addEventListener('DOMContentLoaded', () => {
  const origem = document.getElementById('hierarquia-cnpq');
  const selGa = document.getElementById('id_grande_area');
  const selArea = document.getElementById('id_area');
  const selSub = document.getElementById('id_subarea');
  if (!origem || !selGa || !selArea || !selSub) return;

  const mapa = JSON.parse(origem.textContent);

  /**
   * Esconde/desabilita opções cujo pai difere de `valorPai`.
   * Sem pai selecionado, nada além do placeholder fica visível (força a
   * ordem Grande Área → Área → Subárea).
   */
  function aplicar(sel, pai, valorPai) {
    let selecaoPerdida = false;
    for (const op of sel.options) {
      if (!op.value) continue; // opção vazia (placeholder) permanece
      const visivel = Boolean(valorPai) && pai[op.value] === valorPai;
      op.hidden = !visivel;
      op.disabled = !visivel;
      if (!visivel && op.selected) selecaoPerdida = true;
    }
    if (selecaoPerdida) sel.value = '';
  }

  function cascataArea() {
    aplicar(selArea, mapa.areas, selGa.value);
    cascataSub();
  }

  function cascataSub() {
    aplicar(selSub, mapa.subareas, selArea.value);
  }

  selGa.addEventListener('change', cascataArea);
  selArea.addEventListener('change', cascataSub);

  // Estado inicial: mantém a cascata coerente na edição (valores já setados)
  cascataArea();
});
