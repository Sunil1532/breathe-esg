from django.contrib import admin
from .models import Organization, OrganizationMembership, IngestionJob, EmissionRecord, AuditLog


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'country_code', 'created_at']
    prepopulated_fields = {'slug': ('name',)}


@admin.register(OrganizationMembership)
class OrganizationMembershipAdmin(admin.ModelAdmin):
    list_display = ['user', 'organization', 'role']
    list_filter = ['organization', 'role']


@admin.register(IngestionJob)
class IngestionJobAdmin(admin.ModelAdmin):
    list_display = ['id', 'organization', 'source_type', 'file_name', 'status',
                    'total_rows', 'success_rows', 'error_rows', 'created_at']
    list_filter = ['source_type', 'status', 'organization']
    readonly_fields = ['parse_errors', 'parse_warnings']


@admin.register(EmissionRecord)
class EmissionRecordAdmin(admin.ModelAdmin):
    list_display = ['id', 'organization', 'source_type', 'scope', 'category',
                    'raw_quantity', 'raw_unit', 'quantity_co2e_kg', 'status', 'period_start']
    list_filter = ['source_type', 'scope', 'status', 'organization']
    search_fields = ['description', 'facility_code', 'source_system_id']
    readonly_fields = ['raw_data', 'edit_history', 'created_at', 'updated_at']


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['id', 'record', 'action', 'user', 'timestamp']
    list_filter = ['action']
    readonly_fields = ['record', 'user', 'action', 'changes', 'note', 'timestamp']
