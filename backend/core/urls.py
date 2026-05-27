from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView
from .views import CustomTokenObtainPairView, me, dashboard_summary, EmissionRecordViewSet

router = DefaultRouter()
router.register(r'records', EmissionRecordViewSet, basename='record')

urlpatterns = [
    path('auth/login/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/me/', me),
    path('dashboard/summary/', dashboard_summary),
    path('', include(router.urls)),
]
