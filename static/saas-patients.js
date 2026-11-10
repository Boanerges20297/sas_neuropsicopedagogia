/* Patient list filters are a UI enhancement. The server scopes all rows to the signed-in professional. */
(() => {
  const search = document.getElementById('patients_search');
  const list = document.getElementById('patients_list');
  if (!list) return;
  const rows = [...list.querySelectorAll('[data-patient-name]')];
  const buttons = [...document.querySelectorAll('[data-filter]')];
  const empty = document.getElementById('patients_no_match');
  let filter = 'active';
  const normalize = value => (value || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase('pt-BR');
  function apply() {
    const term = normalize(search?.value);
    let shown = 0;
    rows.forEach(row => {
      const active = row.dataset.patientStatus === 'active';
      const today = row.dataset.patientToday === 'yes';
      const portal = row.dataset.patientPortal === 'yes';
      const eligible = filter === 'all' || (filter === 'active' && active) ||
        (filter === 'today' && today) || (filter === 'portal' && portal);
      const visible = eligible && normalize(row.dataset.patientName).includes(term);
      row.hidden = !visible;
      if (visible) shown++;
    });
    if (empty) empty.hidden = shown !== 0 || rows.length === 0;
    buttons.forEach(button => button.setAttribute('aria-pressed', String(button.dataset.filter === filter)));
  }
  buttons.forEach(button => button.addEventListener('click', () => {
    filter = button.dataset.filter;
    apply();
  }));
  search?.addEventListener('input', apply);
  apply();
})();
