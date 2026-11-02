(function () {
  const digits = (value, max) => value.replace(/\D/g, '').slice(0, max);
  function cpf(v) {
    const n = digits(v, 11);
    return n.replace(/^(\d{3})(\d)/, '$1.$2')
            .replace(/^(\d{3}\.\d{3})(\d)/, '$1.$2')
            .replace(/^(\d{3}\.\d{3}\.\d{3})(\d)/, '$1-$2');
  }
  function phone(v) {
    const n = digits(v, 11);
    if (n.length < 3) return n;
    if (n.length <= 6) return '(' + n.slice(0, 2) + ') ' + n.slice(2);
    const split = n.length === 11 ? 7 : 6;
    return '(' + n.slice(0, 2) + ') ' + n.slice(2, split) + '-' + n.slice(split);
  }
  function mask(id, formatter) {
    const input = document.getElementById(id);
    if (!input) return;
    input.addEventListener('input', () => { input.value = formatter(input.value); });
    input.value = formatter(input.value);
  }
  mask('cpf', cpf);
  mask('phone', phone);
}());
