# core_admin/urls.py
from django.urls import path
from . import views # Ahora sí importamos las vistas

app_name = 'core_admin'

urlpatterns = [
    path('', views.DashboardView.as_view(), name='dashboard'),
    path('cargas-masivas/', views.LoteListView.as_view(), name='lote_list'),
    path('cargas-masivas/procesar/<int:pk>/', views.LoteProcessView.as_view(), name='lote_process'),

    path('reporte-mensual/', views.ReporteMensualView.as_view(), name='reporte_mensual'),
]