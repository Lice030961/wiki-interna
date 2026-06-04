from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0003_regionais'),
    ]

    operations = [
        migrations.AddField(
            model_name='regiao',
            name='icon',
            field=models.CharField(blank=True, default='🌎', max_length=10),
        ),
    ]
