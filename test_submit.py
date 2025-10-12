from app import app

with app.test_client() as c:
    res = c.post('/', data={'nome':'Teste','idade_anos':'10','idade_meses':'6','data_nascimento':'01/01/2015','sexo':'Fem','unidade_escolar':'Escola X'})
    print('status', res.status_code)
