from django.contrib import admin
from .models import JournalEntry, JournalLine, Account, AgentLog

class JournalLineInline(admin.TabularInline):
    model = JournalLine
    extra = 1

@admin.register(JournalEntry)
class JournalEntryAdmin(admin.ModelAdmin):
    list_display = ('entry_number', 'transaction_date', 'narration_preview', 'total_amount', 'status', 'checker_status')
    list_filter = ('status', 'transaction_type', 'checker_status', 'transaction_date')
    search_fields = ('entry_number', 'narration', 'reference')
    inlines = [JournalLineInline]
    date_hierarchy = 'transaction_date'
    
    def narration_preview(self, obj):
        return obj.narration[:50]
    
    def total_amount(self, obj):
        return obj.total_amount

@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'account_type', 'is_active')
    list_filter = ('account_type', 'is_active')
    search_fields = ('code', 'name')
    ordering = ('code',)

@admin.register(AgentLog)
class AgentLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'session_id', 'stage', 'level', 'message_preview')
    list_filter = ('stage', 'level', 'timestamp')
    search_fields = ('session_id', 'message')
    date_hierarchy = 'timestamp'
    
    def message_preview(self, obj):
        return obj.message[:50]
