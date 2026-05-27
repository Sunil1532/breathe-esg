from django.contrib import admin
from django.urls import path, include, re_path
from django.http import FileResponse, HttpResponse
from django.conf import settings
import os

def serve_react(request, path=''):
    """Serve the built React SPA for all non-API routes."""
    index = settings.FRONTEND_DIR / 'index.html'
    if index.exists():
        return FileResponse(open(index, 'rb'), content_type='text/html')
    return HttpResponse(
        '<h2>Frontend not built yet.</h2>'
        '<p>Run: <code>cd frontend && npm install && npm run build && '
        'cp -r dist/* ../backend/staticfiles/frontend/</code></p>',
        status=200
    )

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('core.urls')),
    path('api/ingest/', include('ingestion.urls')),
    # Catch-all: serve React app for any non-API route
    re_path(r'^(?!api/)(?!admin/)(?!static/).*$', serve_react),
]
