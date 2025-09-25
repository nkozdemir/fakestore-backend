from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('catalog', '0002_rating'),
    ]

    operations = [
        migrations.AlterField(
            model_name='product',
            name='id',
            field=models.AutoField(primary_key=True, serialize=False),
        ),
    ]
