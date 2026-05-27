from django.utils import timezone
from django.db.models import Sum, Count, Q
from rest_framework import viewsets, status
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import Organization, EmissionRecord, IngestionJob, AuditLog
from .serializers import (
    UserSerializer, EmissionRecordListSerializer, EmissionRecordDetailSerializer,
    EmissionRecordEditSerializer, IngestionJobSerializer, AuditLogSerializer,
)


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        data['user'] = UserSerializer(self.user).data
        return data


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


def get_user_org(request):
    """Returns the Organization for the authenticated user, or raises."""
    try:
        return request.user.membership.organization
    except Exception:
        return None


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def me(request):
    return Response(UserSerializer(request.user).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_summary(request):
    org = get_user_org(request)
    if not org:
        return Response({'detail': 'No organization found.'}, status=400)

    qs = EmissionRecord.objects.filter(organization=org)

    total = qs.count()
    pending = qs.filter(status='PENDING').count()
    flagged = qs.filter(status='FLAGGED').count()
    approved = qs.filter(status='APPROVED').count()
    rejected = qs.filter(status='REJECTED').count()

    total_co2e = qs.filter(
        quantity_co2e_kg__isnull=False
    ).aggregate(s=Sum('quantity_co2e_kg'))['s'] or 0

    approved_co2e = qs.filter(
        status='APPROVED', quantity_co2e_kg__isnull=False
    ).aggregate(s=Sum('quantity_co2e_kg'))['s'] or 0

    # Scope breakdown (approved only for reporting)
    scope_rows = qs.filter(
        status='APPROVED', quantity_co2e_kg__isnull=False
    ).values('scope').annotate(co2e_kg=Sum('quantity_co2e_kg'))
    scope_breakdown = {
        r['scope']: float(r['co2e_kg']) / 1000 for r in scope_rows
    }

    # Source breakdown
    source_rows = qs.values('source_type').annotate(
        count=Count('id'),
        pending=Count('id', filter=Q(status='PENDING')),
        flagged=Count('id', filter=Q(status='FLAGGED')),
        approved=Count('id', filter=Q(status='APPROVED')),
    )
    source_breakdown = {
        r['source_type']: {
            'count': r['count'],
            'pending': r['pending'],
            'flagged': r['flagged'],
            'approved': r['approved'],
        } for r in source_rows
    }

    recent_jobs = IngestionJob.objects.filter(organization=org).order_by('-created_at')[:10]

    return Response({
        'total_records': total,
        'pending': pending,
        'flagged': flagged,
        'approved': approved,
        'rejected': rejected,
        'total_co2e_tonnes': float(total_co2e) / 1000,
        'approved_co2e_tonnes': float(approved_co2e) / 1000,
        'scope_breakdown': scope_breakdown,
        'source_breakdown': source_breakdown,
        'recent_jobs': IngestionJobSerializer(recent_jobs, many=True).data,
    })


class EmissionRecordViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        org = get_user_org(self.request)
        if not org:
            return EmissionRecord.objects.none()

        qs = EmissionRecord.objects.filter(organization=org).select_related(
            'ingestion_job', 'reviewed_by'
        )

        # Filters
        status_param = self.request.query_params.get('status')
        if status_param:
            qs = qs.filter(status__in=status_param.upper().split(','))

        source_param = self.request.query_params.get('source_type')
        if source_param:
            qs = qs.filter(source_type=source_param.upper())

        scope_param = self.request.query_params.get('scope')
        if scope_param:
            qs = qs.filter(scope=scope_param)

        job_param = self.request.query_params.get('job')
        if job_param:
            qs = qs.filter(ingestion_job_id=job_param)

        search = self.request.query_params.get('search')
        if search:
            qs = qs.filter(
                Q(description__icontains=search) |
                Q(facility_code__icontains=search) |
                Q(category__icontains=search) |
                Q(source_system_id__icontains=search)
            )

        return qs

    def get_serializer_class(self):
        if self.action in ['retrieve', 'update', 'partial_update']:
            return EmissionRecordDetailSerializer
        return EmissionRecordListSerializer

    def partial_update(self, request, *args, **kwargs):
        """Allow analysts to correct quantity/unit/notes. Records the change in edit_history."""
        record = self.get_object()
        org = get_user_org(request)
        if record.organization != org:
            return Response(status=403)
        if record.status == EmissionRecord.STATUS_APPROVED:
            return Response({'detail': 'Cannot edit an approved record.'}, status=400)

        serializer = EmissionRecordEditSerializer(record, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        # Build edit history entry
        entry = {'timestamp': timezone.now().isoformat(), 'user': request.user.username, 'changes': {}}
        for field, new_val in serializer.validated_data.items():
            old_val = getattr(record, field)
            if str(old_val) != str(new_val):
                entry['changes'][field] = {'before': str(old_val), 'after': str(new_val)}

        if entry['changes']:
            record.edit_history.append(entry)
            record.is_manually_edited = True
            AuditLog.objects.create(
                organization=org, record=record, user=request.user,
                action=AuditLog.ACTION_EDITED, changes=entry['changes'],
            )

        serializer.save()
        return Response(EmissionRecordDetailSerializer(record).data)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        record = self.get_object()
        org = get_user_org(request)
        if record.organization != org:
            return Response(status=403)
        if record.status == EmissionRecord.STATUS_APPROVED:
            return Response({'detail': 'Already approved.'}, status=400)

        old_status = record.status
        record.status = EmissionRecord.STATUS_APPROVED
        record.reviewed_by = request.user
        record.reviewed_at = timezone.now()
        record.review_notes = request.data.get('notes', record.review_notes)
        record.save()

        AuditLog.objects.create(
            organization=org, record=record, user=request.user,
            action=AuditLog.ACTION_APPROVED,
            changes={'status': {'before': old_status, 'after': 'APPROVED'}},
            note=record.review_notes,
        )
        return Response(EmissionRecordListSerializer(record).data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        record = self.get_object()
        org = get_user_org(request)
        if record.organization != org:
            return Response(status=403)

        old_status = record.status
        record.status = EmissionRecord.STATUS_REJECTED
        record.reviewed_by = request.user
        record.reviewed_at = timezone.now()
        record.review_notes = request.data.get('notes', '')
        record.save()

        AuditLog.objects.create(
            organization=org, record=record, user=request.user,
            action=AuditLog.ACTION_REJECTED,
            changes={'status': {'before': old_status, 'after': 'REJECTED'}},
            note=record.review_notes,
        )
        return Response(EmissionRecordListSerializer(record).data)

    @action(detail=False, methods=['post'], url_path='bulk-approve')
    def bulk_approve(self, request):
        ids = request.data.get('ids', [])
        org = get_user_org(request)
        qs = EmissionRecord.objects.filter(organization=org, id__in=ids).exclude(
            status=EmissionRecord.STATUS_APPROVED
        )
        now = timezone.now()
        updated = []
        for record in qs:
            old_status = record.status
            record.status = EmissionRecord.STATUS_APPROVED
            record.reviewed_by = request.user
            record.reviewed_at = now
            record.save()
            AuditLog.objects.create(
                organization=org, record=record, user=request.user,
                action=AuditLog.ACTION_APPROVED,
                changes={'status': {'before': old_status, 'after': 'APPROVED'}},
            )
            updated.append(record.id)
        return Response({'approved': updated, 'count': len(updated)})

    @action(detail=False, methods=['post'], url_path='bulk-reject')
    def bulk_reject(self, request):
        ids = request.data.get('ids', [])
        notes = request.data.get('notes', '')
        org = get_user_org(request)
        qs = EmissionRecord.objects.filter(organization=org, id__in=ids)
        now = timezone.now()
        updated = []
        for record in qs:
            old_status = record.status
            record.status = EmissionRecord.STATUS_REJECTED
            record.reviewed_by = request.user
            record.reviewed_at = now
            record.review_notes = notes
            record.save()
            AuditLog.objects.create(
                organization=org, record=record, user=request.user,
                action=AuditLog.ACTION_REJECTED,
                changes={'status': {'before': old_status, 'after': 'REJECTED'}},
                note=notes,
            )
            updated.append(record.id)
        return Response({'rejected': updated, 'count': len(updated)})

    @action(detail=True, methods=['get'])
    def audit_log(self, request, pk=None):
        record = self.get_object()
        logs = AuditLog.objects.filter(record=record).order_by('-timestamp')
        return Response(AuditLogSerializer(logs, many=True).data)
