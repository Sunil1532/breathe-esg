import hashlib
from datetime import timezone as tz
from django.utils import timezone

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.models import Organization, IngestionJob, EmissionRecord, AuditLog
from core.serializers import IngestionJobSerializer
from ingestion.parsers.sap import parse_sap_csv
from ingestion.parsers.utility import parse_utility_csv
from ingestion.parsers.travel import parse_travel_csv


def get_user_org(request):
    try:
        return request.user.membership.organization
    except Exception:
        return None


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _ingest_file(request, source_type: str, parser_fn, parser_kwargs: dict = None):
    """
    Generic ingestion handler. Calls parser_fn on the uploaded file,
    creates EmissionRecord objects, and returns the IngestionJob.
    """
    org = get_user_org(request)
    if not org:
        return Response({'detail': 'No organization found for this user.'}, status=400)

    file_obj = request.FILES.get('file')
    if not file_obj:
        return Response({'detail': 'No file uploaded. Send the CSV as multipart/form-data field "file".'}, status=400)

    file_content = file_obj.read()
    file_hash = _sha256(file_content)

    # Duplicate upload detection
    existing = IngestionJob.objects.filter(
        organization=org, source_type=source_type, file_hash=file_hash,
        status__in=[IngestionJob.STATUS_COMPLETED, IngestionJob.STATUS_PARTIAL]
    ).first()
    if existing:
        return Response({
            'detail': f"This file was already ingested (job #{existing.id}, {existing.created_at.date()}). "
                      f"Upload a different file or delete the existing job first.",
            'existing_job': IngestionJobSerializer(existing).data,
        }, status=409)

    job = IngestionJob.objects.create(
        organization=org,
        source_type=source_type,
        file_name=file_obj.name,
        file_hash=file_hash,
        status=IngestionJob.STATUS_PROCESSING,
        created_by=request.user,
    )

    records_to_create = []
    errors = []
    warnings = []
    skipped = 0

    kwargs = parser_kwargs or {}
    # Pass org's grid factor settings for utility
    if source_type == IngestionJob.SOURCE_UTILITY:
        kwargs.setdefault('country_code', org.country_code)
        if org.custom_grid_factor_kg_per_kwh:
            kwargs['custom_grid_factor'] = float(org.custom_grid_factor_kg_per_kwh)

    try:
        for result in parser_fn(file_content, **kwargs):
            if 'error' in result:
                errors.append(result)
            elif result.get('skipped'):
                skipped += 1
                warnings.append({'type': 'skipped', **result})
            elif 'record' in result:
                rec = result['record']
                if result.get('warnings'):
                    warnings.extend(result['warnings'])

                records_to_create.append(EmissionRecord(
                    organization=org,
                    ingestion_job=job,
                    source_type=source_type,
                    scope=rec['scope'],
                    category=rec['category'],
                    subcategory=rec.get('subcategory', ''),
                    fuel_type=rec.get('fuel_type', ''),
                    raw_quantity=rec['raw_quantity'],
                    raw_unit=rec['raw_unit'],
                    raw_data=rec['raw_data'],
                    quantity_normalized=rec['quantity_normalized'],
                    normalized_unit=rec['normalized_unit'],
                    quantity_co2e_kg=rec.get('quantity_co2e_kg'),
                    emission_factor=rec.get('emission_factor'),
                    emission_factor_source=rec.get('emission_factor_source', ''),
                    period_start=rec['period_start'],
                    period_end=rec['period_end'],
                    source_system_id=rec.get('source_system_id', ''),
                    facility_code=rec.get('facility_code', ''),
                    description=rec.get('description', ''),
                    status=EmissionRecord.STATUS_FLAGGED if rec.get('flags') else EmissionRecord.STATUS_PENDING,
                    flags=rec.get('flags', []),
                ))
    except Exception as e:
        job.status = IngestionJob.STATUS_FAILED
        job.parse_errors = [{'message': str(e)}]
        job.completed_at = timezone.now()
        job.save()
        return Response({'detail': f"Parser error: {e}", 'job': IngestionJobSerializer(job).data}, status=500)

    # Bulk create records
    created = EmissionRecord.objects.bulk_create(records_to_create)

    # Create audit log entries
    AuditLog.objects.bulk_create([
        AuditLog(
            organization=org,
            record=r,
            user=request.user,
            action=AuditLog.ACTION_INGESTED,
            changes={},
        ) for r in created
    ])

    flagged_count = sum(1 for r in created if r.status == EmissionRecord.STATUS_FLAGGED)

    job.status = IngestionJob.STATUS_PARTIAL if errors else IngestionJob.STATUS_COMPLETED
    job.total_rows = len(created) + len(errors) + skipped
    job.success_rows = len(created)
    job.error_rows = len(errors)
    job.flagged_rows = flagged_count
    job.parse_errors = errors[:100]   # cap stored errors
    job.parse_warnings = warnings[:100]
    job.completed_at = timezone.now()
    job.save()

    return Response(IngestionJobSerializer(job).data, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def ingest_sap(request):
    """Upload a SAP flat-file CSV (semicolon-delimited, German headers)."""
    return _ingest_file(request, IngestionJob.SOURCE_SAP, parse_sap_csv)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def ingest_utility(request):
    """Upload a utility portal CSV export (electricity meters)."""
    return _ingest_file(request, IngestionJob.SOURCE_UTILITY, parse_utility_csv)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def ingest_travel(request):
    """Upload a Concur/Navan-style corporate travel CSV."""
    return _ingest_file(request, IngestionJob.SOURCE_TRAVEL, parse_travel_csv)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_jobs(request):
    org = get_user_org(request)
    if not org:
        return Response([], status=200)
    source = request.query_params.get('source_type')
    qs = IngestionJob.objects.filter(organization=org)
    if source:
        qs = qs.filter(source_type=source.upper())
    return Response(IngestionJobSerializer(qs[:50], many=True).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def job_detail(request, pk):
    org = get_user_org(request)
    try:
        job = IngestionJob.objects.get(pk=pk, organization=org)
    except IngestionJob.DoesNotExist:
        return Response(status=404)
    return Response(IngestionJobSerializer(job).data)
