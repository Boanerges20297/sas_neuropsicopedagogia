# Generated manually after adding the clinical patient workflow.

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('avaliacao', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Paciente',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome', models.TextField()),
                ('data_nascimento', models.CharField(blank=True, max_length=20, null=True)),
                ('responsavel', models.TextField(blank=True, null=True)),
                ('telefone', models.TextField(blank=True, null=True)),
                ('email', models.TextField(blank=True, null=True)),
                ('escola', models.CharField(blank=True, max_length=200, null=True)),
                ('serie', models.CharField(blank=True, max_length=80, null=True)),
                ('queixa_principal', models.TextField(blank=True, null=True)),
                ('observacoes', models.TextField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name='AnotacaoAtendimento',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tipo', models.CharField(choices=[('sessao', 'Sessao'), ('observacao', 'Observacao'), ('orientacao', 'Orientacao familiar/escolar'), ('encaminhamento', 'Encaminhamento'), ('ia', 'Consulta IA')], default='sessao', max_length=30)),
                ('titulo', models.CharField(blank=True, max_length=160, null=True)),
                ('conteudo', models.TextField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('paciente', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='anotacoes', to='avaliacao.paciente')),
                ('profissional', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='avaliacao.perfilusuario')),
            ],
        ),
    ]
