from django.urls import path
from .views import ingest_sap, ingest_utility, ingest_travel, list_jobs, job_detail

urlpatterns = [
    path('sap/', ingest_sap, name='ingest_sap'),
    path('utility/', ingest_utility, name='ingest_utility'),
    path('travel/', ingest_travel, name='ingest_travel'),
    path('jobs/', list_jobs, name='list_jobs'),
    path('jobs/<int:pk>/', job_detail, name='job_detail'),
]
