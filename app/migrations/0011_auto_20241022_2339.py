# Generated by Django 3.2.25 on 2024-10-22 22:39

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0010_alter_beneficiary_user'),
    ]

    operations = [
        migrations.AddField(
            model_name='linkedaccount',
            name='default',
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name='linkedaccount',
            name='routing_number',
            field=models.CharField(max_length=9, validators=[django.core.validators.RegexValidator(message='Routing number must be exactly 9 digits.', regex='^\\d{9}$')]),
        ),
        migrations.AlterUniqueTogether(
            name='linkedaccount',
            unique_together={('user', 'account_number')},
        ),
        migrations.RemoveField(
            model_name='linkedaccount',
            name='bank_account_id',
        ),
    ]
