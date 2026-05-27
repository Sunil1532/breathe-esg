"""
Core data model for Breathe ESG ingestion platform.

Design principles:
- Multi-tenancy via Organization FK on every table (row-level, not schema-level)
- Immutable raw_data: once parsed, the original row is never overwritten
- Full audit trail: every state change is logged in AuditLog
- Scope/category classification at the record level, not inferred at query time
- Unit normalization happens at ingest; emission factor application is separate
  so factors can be updated without re-parsing
"""

from django.db import models
from django.contrib.auth.models import User


class Organization(models.Model):
    """Tenant. Every data row is owned by exactly one Organization."""

    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    country_code = models.CharField(
        max_length=2, default='DE',
        help_text="ISO 3166-1 alpha-2. Used to select default grid emission factor for Scope 2."
    )
    # Allows overriding the default grid factor with a supplier-specific or
    # contractual (market-based) factor. Null means: use country default.
    custom_grid_factor_kg_per_kwh = models.DecimalField(
        max_digits=10, decimal_places=6, null=True, blank=True,
        help_text="Market-based Scope 2 grid factor override (kg CO2e / kWh). Leave blank to use country default."
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class OrganizationMembership(models.Model):
    """Links a User to an Organization with a role."""
    ROLE_ANALYST = 'ANALYST'
    ROLE_ADMIN = 'ADMIN'
    ROLE_CHOICES = [
        (ROLE_ANALYST, 'Analyst'),
        (ROLE_ADMIN, 'Admin'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='membership')
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='members')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_ANALYST)

    def __str__(self):
        return f"{self.user.username} → {self.organization.name} ({self.role})"


class IngestionJob(models.Model):
    """
    Represents one file-upload event.

    Tracks parse outcomes at the job level so analysts can see at a glance
    how clean each import was without inspecting individual records.
    """
    SOURCE_SAP = 'SAP'
    SOURCE_UTILITY = 'UTILITY'
    SOURCE_TRAVEL = 'TRAVEL'
    SOURCE_CHOICES = [
        (SOURCE_SAP, 'SAP Fuel & Procurement'),
        (SOURCE_UTILITY, 'Utility (Electricity)'),
        (SOURCE_TRAVEL, 'Corporate Travel'),
    ]

    STATUS_PROCESSING = 'PROCESSING'
    STATUS_COMPLETED = 'COMPLETED'
    STATUS_FAILED = 'FAILED'
    STATUS_PARTIAL = 'PARTIAL'  # some rows parsed, some errored
    STATUS_CHOICES = [
        (STATUS_PROCESSING, 'Processing'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_FAILED, 'Failed'),
        (STATUS_PARTIAL, 'Partial'),
    ]

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='jobs')
    source_type = models.CharField(max_length=20, choices=SOURCE_CHOICES)
    file_name = models.CharField(max_length=512)
    # SHA-256 of the uploaded file — used to detect duplicate uploads
    file_hash = models.CharField(max_length=64, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PROCESSING)
    total_rows = models.IntegerField(default=0)
    success_rows = models.IntegerField(default=0)
    error_rows = models.IntegerField(default=0)
    flagged_rows = models.IntegerField(default=0)
    # Structured list of {row, field, message} parse errors
    parse_errors = models.JSONField(default=list)
    # Non-fatal warnings (unknown unit, missing description, etc.)
    parse_warnings = models.JSONField(default=list)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.source_type} import {self.file_name} ({self.status})"


class EmissionRecord(models.Model):
    """
    One normalized emission-relevant activity row.

    Invariants:
    - raw_data is never modified after creation; it preserves the exact
      parsed representation of the source row.
    - quantity_co2e_kg may be null if the emission factor lookup failed —
      this is surfaced to analysts as a flag.
    - status transitions: PENDING → APPROVED or REJECTED (terminal).
      FLAGGED is a non-terminal annotation; a flagged record can still be approved.
    """

    # ── Scope / GHG Protocol classification ──────────────────────────────
    SCOPE_1 = '1'   # Direct: combustion, company vehicles
    SCOPE_2 = '2'   # Indirect: purchased electricity, heat, steam
    SCOPE_3 = '3'   # Value chain: business travel, procurement
    SCOPE_CHOICES = [(SCOPE_1, 'Scope 1'), (SCOPE_2, 'Scope 2'), (SCOPE_3, 'Scope 3')]

    # GHG Protocol Scope 3 categories (abbreviated list for this prototype)
    CATEGORY_STATIONARY = 'Stationary Combustion'
    CATEGORY_MOBILE = 'Mobile Combustion'
    CATEGORY_ELECTRICITY = 'Purchased Electricity'
    CATEGORY_TRAVEL = 'Business Travel'
    CATEGORY_PROCUREMENT = 'Purchased Goods & Services'

    # ── Review workflow ───────────────────────────────────────────────────
    STATUS_PENDING = 'PENDING'
    STATUS_FLAGGED = 'FLAGGED'    # auto-flagged or manually flagged; still reviewable
    STATUS_APPROVED = 'APPROVED'  # locked for audit
    STATUS_REJECTED = 'REJECTED'  # excluded from totals
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending Review'),
        (STATUS_FLAGGED, 'Flagged'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_REJECTED, 'Rejected'),
    ]

    # ── Ownership ────────────────────────────────────────────────────────
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='records')
    ingestion_job = models.ForeignKey(IngestionJob, on_delete=models.CASCADE, related_name='records')
    source_type = models.CharField(max_length=20, choices=IngestionJob.SOURCE_CHOICES)

    # ── Classification ───────────────────────────────────────────────────
    scope = models.CharField(max_length=1, choices=SCOPE_CHOICES)
    category = models.CharField(max_length=100)
    subcategory = models.CharField(max_length=100, blank=True)
    fuel_type = models.CharField(max_length=50, blank=True, help_text="e.g. diesel, natural_gas, air_economy_long")

    # ── Raw values (immutable after creation) ────────────────────────────
    raw_quantity = models.DecimalField(max_digits=20, decimal_places=6)
    raw_unit = models.CharField(max_length=50)
    raw_data = models.JSONField(help_text="Complete original parsed row from source file")

    # ── Normalized values ────────────────────────────────────────────────
    # Everything is converted to a canonical unit (L, M3, KG, KWH, passenger-km)
    # before emission factor application.
    quantity_normalized = models.DecimalField(max_digits=20, decimal_places=6)
    normalized_unit = models.CharField(max_length=50)
    quantity_co2e_kg = models.DecimalField(
        max_digits=20, decimal_places=4, null=True, blank=True,
        help_text="Null if emission factor lookup failed"
    )
    emission_factor = models.DecimalField(max_digits=14, decimal_places=6, null=True, blank=True)
    emission_factor_source = models.CharField(max_length=200, blank=True)

    # ── Temporal ─────────────────────────────────────────────────────────
    period_start = models.DateField()
    period_end = models.DateField()

    # ── Source metadata ───────────────────────────────────────────────────
    # Preserves the identity of the source row so duplicates can be detected
    source_system_id = models.CharField(max_length=255, blank=True, help_text="Doc number, trip ID, meter ID, etc.")
    facility_code = models.CharField(max_length=100, blank=True, help_text="SAP plant, meter ID, office code")
    description = models.CharField(max_length=500, blank=True)

    # ── Review workflow ───────────────────────────────────────────────────
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    # Structured list of {code, message} flag reasons
    flags = models.JSONField(default=list)
    reviewed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_records'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(blank=True)

    # ── Audit trail ───────────────────────────────────────────────────────
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    # True if an analyst manually corrected quantity or unit after ingestion
    is_manually_edited = models.BooleanField(default=False)
    # Append-only list of {timestamp, user_id, field, before, after}
    edit_history = models.JSONField(default=list)

    class Meta:
        ordering = ['-period_start', 'source_type']
        indexes = [
            models.Index(fields=['organization', 'status']),
            models.Index(fields=['organization', 'scope']),
            models.Index(fields=['organization', 'source_type', 'period_start']),
        ]

    def __str__(self):
        return f"{self.source_type} | {self.scope} | {self.description[:40]} ({self.period_start})"

    @property
    def quantity_co2e_tonnes(self):
        if self.quantity_co2e_kg is not None:
            return float(self.quantity_co2e_kg) / 1000
        return None


class AuditLog(models.Model):
    """
    Immutable log of every review action taken on an EmissionRecord.

    Written at the point of action; never updated. Provides the complete
    chain-of-custody that auditors require.
    """
    ACTION_APPROVED = 'APPROVED'
    ACTION_REJECTED = 'REJECTED'
    ACTION_EDITED = 'EDITED'
    ACTION_FLAGGED = 'FLAGGED'
    ACTION_UNFLAGGED = 'UNFLAGGED'
    ACTION_INGESTED = 'INGESTED'
    ACTION_CHOICES = [
        (ACTION_APPROVED, 'Approved'),
        (ACTION_REJECTED, 'Rejected'),
        (ACTION_EDITED, 'Edited'),
        (ACTION_FLAGGED, 'Flagged'),
        (ACTION_UNFLAGGED, 'Unflagged'),
        (ACTION_INGESTED, 'Ingested'),
    ]

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    record = models.ForeignKey(EmissionRecord, on_delete=models.CASCADE, related_name='audit_logs')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    # What changed: {field: {before, after}}
    changes = models.JSONField(default=dict)
    note = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.action} on record {self.record_id} by {self.user} at {self.timestamp}"
