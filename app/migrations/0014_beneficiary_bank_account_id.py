# Generated by Django 3.2.25 on 2024-10-23 01:29

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0013_alter_linkedaccount_bank_account_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='beneficiary',
            name='bank_account_id',
            field=models.CharField(blank=True, max_length=255, null=True, unique=True),
        ),
    ]
