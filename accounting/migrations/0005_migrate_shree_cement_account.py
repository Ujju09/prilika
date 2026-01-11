# Generated manually for account split migration
from django.db import migrations


def migrate_shree_cement_transactions(apps, schema_editor):
    """
    Migrate existing A003 (Shree Cement A/c) journal lines to A003-CR (Commission Receivable).
    This is a data migration to split Shree Cement account into Security Deposit and Commission Receivable.
    """
    JournalLine = apps.get_model('accounting', 'JournalLine')
    
    # Update all A003 lines to A003-CR (Commission Receivable)
    # Assumption: All existing transactions are commission-related
    updated_count = JournalLine.objects.filter(account_code='A003').update(
        account_code='A003-CR',
        account_name='Shree Cement - Commission Receivable'
    )
    
    print(f"Migrated {updated_count} journal lines from A003 to A003-CR")


def reverse_migration(apps, schema_editor):
    """Reverse the migration by moving A003-CR lines back to A003"""
    JournalLine = apps.get_model('accounting', 'JournalLine')
    
    updated_count = JournalLine.objects.filter(account_code='A003-CR').update(
        account_code='A003',
        account_name='Shree Cement A/c'
    )
    
    print(f"Reversed migration: moved {updated_count} journal lines from A003-CR back to A003")


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0004_account_account_subtype'),
    ]

    operations = [
        migrations.RunPython(migrate_shree_cement_transactions, reverse_migration),
    ]
