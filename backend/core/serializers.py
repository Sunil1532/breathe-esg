from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Organization, OrganizationMembership, IngestionJob, EmissionRecord, AuditLog


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ['id', 'name', 'slug', 'country_code', 'custom_grid_factor_kg_per_kwh', 'created_at']


class UserSerializer(serializers.ModelSerializer):
    organization = serializers.SerializerMethodField()
    role = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'organization', 'role']

    def get_organization(self, obj):
        try:
            return OrganizationSerializer(obj.membership.organization).data
        except OrganizationMembership.DoesNotExist:
            return None

    def get_role(self, obj):
        try:
            return obj.membership.role
        except OrganizationMembership.DoesNotExist:
            return None


class IngestionJobSerializer(serializers.ModelSerializer):
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)
    source_type_display = serializers.CharField(source='get_source_type_display', read_only=True)

    class Meta:
        model = IngestionJob
        fields = [
            'id', 'source_type', 'source_type_display', 'file_name', 'status',
            'total_rows', 'success_rows', 'error_rows', 'flagged_rows',
            'parse_errors', 'parse_warnings', 'created_by_username',
            'created_at', 'completed_at',
        ]


class EmissionRecordListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for the review table list view."""
    source_type_display = serializers.CharField(source='get_source_type_display', read_only=True)
    scope_display = serializers.CharField(source='get_scope_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    reviewed_by_username = serializers.CharField(source='reviewed_by.username', read_only=True)
    quantity_co2e_tonnes = serializers.FloatField(read_only=True)

    class Meta:
        model = EmissionRecord
        fields = [
            'id', 'source_type', 'source_type_display',
            'scope', 'scope_display', 'category', 'subcategory',
            'raw_quantity', 'raw_unit',
            'quantity_normalized', 'normalized_unit',
            'quantity_co2e_kg', 'quantity_co2e_tonnes',
            'emission_factor', 'emission_factor_source',
            'period_start', 'period_end',
            'facility_code', 'description',
            'status', 'status_display', 'flags',
            'reviewed_by_username', 'reviewed_at', 'review_notes',
            'created_at', 'is_manually_edited',
        ]


class EmissionRecordDetailSerializer(serializers.ModelSerializer):
    """Full serializer including raw_data and edit_history for the detail view."""
    source_type_display = serializers.CharField(source='get_source_type_display', read_only=True)
    scope_display = serializers.CharField(source='get_scope_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    reviewed_by_username = serializers.CharField(source='reviewed_by.username', read_only=True)
    quantity_co2e_tonnes = serializers.FloatField(read_only=True)
    ingestion_job = IngestionJobSerializer(read_only=True)

    class Meta:
        model = EmissionRecord
        fields = '__all__'


class EmissionRecordEditSerializer(serializers.ModelSerializer):
    """Only the fields an analyst is permitted to change post-ingestion."""
    class Meta:
        model = EmissionRecord
        fields = ['raw_quantity', 'raw_unit', 'review_notes']


class AuditLogSerializer(serializers.ModelSerializer):
    user_username = serializers.CharField(source='user.username', read_only=True)
    user_display = serializers.SerializerMethodField()
    action_display = serializers.CharField(source='get_action_display', read_only=True)

    class Meta:
        model = AuditLog
        fields = ['id', 'action', 'action_display', 'user_username', 'user_display', 'changes', 'note', 'timestamp']

    def get_user_display(self, obj):
        if obj.user:
            name = f"{obj.user.first_name} {obj.user.last_name}".strip()
            return name or obj.user.username
        return 'System'


class DashboardSummarySerializer(serializers.Serializer):
    total_records = serializers.IntegerField()
    pending = serializers.IntegerField()
    flagged = serializers.IntegerField()
    approved = serializers.IntegerField()
    rejected = serializers.IntegerField()
    total_co2e_tonnes = serializers.FloatField()
    approved_co2e_tonnes = serializers.FloatField()
    scope_breakdown = serializers.DictField()
    source_breakdown = serializers.DictField()
    recent_jobs = IngestionJobSerializer(many=True)
