"""
Management command to export all accounting data to JSON for migration.

Usage:
    python manage.py export_data

This will create a data_backup.json file in the project root containing all:
- Accounts
- Journal Entries
- Journal Lines
- Agent Logs

Use this before migrating from SQLite to PostgreSQL.
"""
import json
from django.core.management.base import BaseCommand
from django.core import serializers
from accounting.models import Account, JournalEntry, JournalLine, AgentLog


class Command(BaseCommand):
    help = 'Export all accounting data to JSON for database migration'

    def add_arguments(self, parser):
        parser.add_argument(
            '--output',
            type=str,
            default='data_backup.json',
            help='Output file path (default: data_backup.json)',
        )

    def handle(self, *args, **options):
        output_file = options['output']

        self.stdout.write(self.style.SUCCESS('Starting data export...'))

        # Export models in correct order (respecting foreign key dependencies)
        models = [
            ('Accounts', Account),
            ('Journal Entries', JournalEntry),
            ('Journal Lines', JournalLine),
            ('Agent Logs', AgentLog),
        ]

        all_data = []
        total_objects = 0

        for model_name, model in models:
            objects = model.objects.all()
            count = objects.count()
            total_objects += count

            self.stdout.write(f'  Exporting {count} {model_name}...')

            # Serialize and convert to JSON-compatible format
            serialized = serializers.serialize('json', objects)
            data = json.loads(serialized)
            all_data.extend(data)

        # Write to file
        with open(output_file, 'w') as f:
            json.dump(all_data, f, indent=2)

        self.stdout.write(
            self.style.SUCCESS(
                f'\n✓ Successfully exported {total_objects} objects to {output_file}'
            )
        )
        self.stdout.write(
            self.style.WARNING(
                '\nTo import in production:\n'
                '  python manage.py migrate\n'
                f'  python manage.py loaddata {output_file}'
            )
        )
