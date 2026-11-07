/* Progressive enhancement; all access and age validation happens server-side. */
(() => {
  const mode = document.getElementById('representation_mode');
  const guardian = document.getElementById('guardian_fields');
  const guardianName = document.getElementById('guardian_name');
  const adultContact = document.getElementById('adult_contact');
  const birth = document.getElementById('birth_date');
  const age = document.getElementById('intake_age');
  if (!mode || !guardian || !birth) return;

  function updateMode() {
    const minor = mode.value === 'guardian';
    guardian.hidden = !minor;
    guardianName.required = minor;
    adultContact.hidden = minor;
  }
  function updateAge() {
    const b = birth.value;
    if (!/^\d{4}-\d{2}-\d{2}$/.test(b)) {
      age.textContent = 'A idade será calculada automaticamente.';
      return;
    }
    const now = new Date();
    const [y, m, d] = b.split('-').map(Number);
    const years = now.getFullYear() - y - ((now.getMonth() + 1 < m ||
      (now.getMonth() + 1 === m && now.getDate() < d)) ? 1 : 0);
    age.textContent = years >= 0 && years <= 120 ? 'Idade: ' + years + ' anos.' :
      'Verifique a data de nascimento.';
  }
  mode.addEventListener('change', updateMode);
  birth.addEventListener('change', updateAge);
  updateMode();
  updateAge();
})();
