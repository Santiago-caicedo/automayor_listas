from django.views.generic import TemplateView
from .mixins import SuperuserRequiredMixin
from django.utils import timezone
from datetime import datetime
from django.db.models.functions import TruncDay
from consultas.models import Busqueda
from cargas_masivas.models import LoteConsultaMasiva
from empresas.models import Empresa
from usuarios.models import Usuario
from django.db.models import Count
from django.db.models.functions import TruncMonth
import json 
from django.views.generic import TemplateView, ListView, UpdateView 
from .forms import ProcesarLoteForm 
from django.urls import reverse_lazy

class DashboardView(SuperuserRequiredMixin, TemplateView):
    template_name = 'core_admin/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = "Dashboard de Administración"

        # --- 1. KPIs Globales ---
        context['total_consultas'] = Busqueda.objects.count()
        context['total_lotes'] = LoteConsultaMasiva.objects.count()
        context['total_empresas'] = Empresa.objects.count()
        context['total_usuarios'] = Usuario.objects.filter(is_superuser=False, is_active=True).count()
        context['lotes_pendientes'] = LoteConsultaMasiva.objects.filter(estado='PENDIENTE').count()

        # --- 2. Datos para Gráfico: Consultas por Mes ---
        consultas_mes_data = Busqueda.objects.annotate(
            mes=TruncMonth('fecha_busqueda')
        ).values('mes').annotate(
            total=Count('id')
        ).order_by('mes')

        context['chart_labels'] = json.dumps([mes['mes'].strftime('%Y-%m') for mes in consultas_mes_data])
        context['chart_data'] = json.dumps([mes['total'] for mes in consultas_mes_data])

        # --- 3. Tabla de Actividad por Empresa ---
        busqueda_counts = Busqueda.objects.values('usuario__empresa_id') \
                                  .annotate(num_consultas=Count('id')) \
                                  .order_by()
        
        busqueda_dict = {item['usuario__empresa_id']: item['num_consultas'] for item in busqueda_counts}

        # --- LÍNEA CORREGIDA (usando el nombre de la lista "Choices") ---
        empresas_list = Empresa.objects.annotate(
            num_lotes=Count('loteconsultamasiva', distinct=True) # Era 'loteconsultamasiva_set'
        )
        # ---

        for empresa in empresas_list:
            empresa.num_consultas = busqueda_dict.get(empresa.id, 0)
        
        empresas_list_sorted = sorted(empresas_list, key=lambda e: e.num_consultas, reverse=True)

        context['empresas_data'] = empresas_list_sorted

        return context



# --- VISTAS PARA GESTIONAR CARGAS MASIVAS ---

class LoteListView(SuperuserRequiredMixin, ListView):
    """
    Lista todos los lotes para que el admin los gestione.
    """
    model = LoteConsultaMasiva
    template_name = 'core_admin/lote_list.html'
    context_object_name = 'lotes'
    ordering = ['estado', '-fecha_solicitud'] # Muestra PENDIENTES primero
    paginate_by = 25 # Pagina los resultados

    def get_context_data(self, **kwargs):
        # Llama a la implementación base primero para obtener el contexto
        context = super().get_context_data(**kwargs)
        # Añade el contador de pendientes al contexto
        # Usamos self.model para referirnos a LoteConsultaMasiva
        context['lotes_pendientes'] = self.model.objects.filter(estado='PENDIENTE').count()
        return context

class LoteProcessView(SuperuserRequiredMixin, UpdateView):
    """
    Vista para editar un lote, cambiar estado y subir PDF.
    """
    model = LoteConsultaMasiva
    form_class = ProcesarLoteForm
    template_name = 'core_admin/lote_process.html'
    success_url = reverse_lazy('core_admin:lote_list') # Redirige a la lista
    context_object_name = 'lote' # Para usar 'lote' en la plantilla

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = f"Procesar Lote ID: {self.object.id}"
        return context


class ReporteMensualView(SuperuserRequiredMixin, TemplateView):
    """
    Muestra un reporte de consultas diarias para un mes seleccionado.
    """
    template_name = 'core_admin/reporte_mensual.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # 1. Determinar el mes a consultar
        selected_month_str = self.request.GET.get('month_selector')
        
        if selected_month_str:
            try:
                # Si el usuario selecciona un mes (ej: "2025-10")
                target_date = datetime.strptime(selected_month_str, '%Y-%m').date()
            except ValueError:
                target_date = timezone.now().date()
        else:
            # Por defecto, mostrar el mes actual
            target_date = timezone.now().date()

        context['selected_month_form_value'] = target_date.strftime('%Y-%m')
        context['titulo'] = f"Reporte de Consultas: {target_date.strftime('%B %Y')}"
        
        # 2. Consultar la base de datos
        consultas_del_mes = Busqueda.objects.filter(
            fecha_busqueda__year=target_date.year,
            fecha_busqueda__month=target_date.month
        )
        
        # 3. Preparar datos para el gráfico (agrupados por día)
        consultas_por_dia = consultas_del_mes.annotate(
            dia=TruncDay('fecha_busqueda')
        ).values('dia').annotate(
            total=Count('id')
        ).order_by('dia')

        # 4. Formatear para Chart.js
        chart_labels = [entry['dia'].strftime('%Y-%m-%d') for entry in consultas_por_dia]
        chart_data = [entry['total'] for entry in consultas_por_dia]

        context['chart_labels_json'] = json.dumps(chart_labels)
        context['chart_data_json'] = json.dumps(chart_data)
        
        # 5. KPI: Total de consultas en el mes
        context['total_consultas_mes'] = consultas_del_mes.count()

        return context