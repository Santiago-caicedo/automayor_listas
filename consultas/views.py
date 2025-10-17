# archivo: consultas/views.py

from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.contrib.auth.decorators import login_required
from .forms import BusquedaForm
from .services import consultar_api_por_id, consultar_api_por_id_y_nombre, consultar_api_por_nombre
from .models import Busqueda, Resultado # <-- IMPORTAMOS LOS MODELOS
from django.utils import timezone
from weasyprint import HTML
from django.template.loader import render_to_string
from datetime import timedelta
from django.db.models import Count
from django.db.models.functions import TruncDay

@login_required
def pagina_busqueda(request):
    """
    Gestiona la página principal de consultas. Muestra el formulario,
    procesa la búsqueda, llama al API correspondiente, guarda los
    resultados y los muestra en la plantilla.
    """
    form = BusquedaForm()
    resultados_api = None
    alerta_generada = False
    busqueda_obj = None
    
    if request.method == 'POST':
        form = BusquedaForm(request.POST)

        # Verificamos si el formulario es válido
        if form.is_valid():
            # Si es válido, se ejecuta toda la lógica de búsqueda y guardado
            identificacion = form.cleaned_data.get("identificacion")
            nombres = form.cleaned_data.get("nombres")
            termino_buscado = ""

            # --- Lógica para decidir qué método del API usar ---
            if identificacion and nombres:
                termino_buscado = f"ID: {identificacion} y Nombre: {nombres}"
                resultados_api = consultar_api_por_id_y_nombre(identificacion, nombres)
            elif identificacion:
                termino_buscado = f"ID: {identificacion}"
                resultados_api = consultar_api_por_id(identificacion)
            elif nombres:
                termino_buscado = f"Nombre: {nombres}"
                resultados_api = consultar_api_por_nombre(nombres)
            
            # --- Lógica para guardar en la Base de Datos ---
            if termino_buscado:
                busqueda_obj = Busqueda.objects.create(
                    usuario=request.user,
                    termino_buscado=termino_buscado
                )
                if resultados_api is not None:
                    busqueda_obj.encontro_resultados = bool(resultados_api)
                    for item in resultados_api:
                        es_restrictiva = item.get('Restrictiva', False)
                        if es_restrictiva:
                            alerta_generada = True
                        
                        # Pequeña mejora para hacer el código más robusto y automático
                        # Mapea las llaves del API a los campos del modelo que coincidan
                        campos_modelo = [f.name for f in Resultado._meta.get_fields()]
                        datos_para_crear = {k.lower(): v for k, v in item.items() if k.lower() in campos_modelo}
                        
                        Resultado.objects.create(
                            busqueda=busqueda_obj,
                            nombre_completo=item.get('NombreCompleto'),
                            identificacion=item.get('Id'), # El ID del API va en nuestro campo 'identificacion'
                            tipo_lista=item.get('Tipo_Lista'),
                            origen_lista=item.get('Origen_Lista'),
                            relacionado_con=item.get('Relacionado_Con'),
                            fuente=item.get('Fuente'),
                            es_restrictiva=es_restrictiva
                        )
                    
                    if alerta_generada:
                        busqueda_obj.genero_alerta = True
                    
                    busqueda_obj.save()
        else:
            # Si el formulario NO es válido, imprimimos los errores en la terminal
            print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
            print("!!!      FORMULARIO INVÁLIDO       !!!")
            print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
            print("Errores encontrados:", form.errors)

    # Preparamos el contexto para la plantilla
    context = {
        'form': form,
        'resultados': resultados_api,
        'alerta_generada': alerta_generada,
        'busqueda_obj': busqueda_obj,
    }

    # --- PRUEBA FINAL Y DEFINITIVA ---
    # Justo antes de renderizar, imprimimos el contenido de 'resultados' en el contexto
    print("================ ÚLTIMA VERIFICACIÓN ================")
    if context['resultados']:
        print(f"Contexto CONTIENE {len(context['resultados'])} resultados.")
    else:
        print("Contexto NO CONTIENE resultados (es None o está vacío).")
    print("=====================================================")

    return render(request, 'consultas/pagina_busqueda.html', context)



@login_required
def historial_busquedas(request):
    # Esta es la línea clave:
    # Filtramos las búsquedas para obtener solo las del usuario actual (request.user)
    # y las ordenamos por fecha, de la más reciente a la más antigua.
    busquedas = Busqueda.objects.filter(usuario=request.user).order_by('-fecha_busqueda')

    context = {
        'busquedas': busquedas
    }
    return render(request, 'consultas/historial.html', context)



@login_required
def detalle_busqueda(request, busqueda_id):
    """
    Muestra el detalle completo de una búsqueda específica del historial.
    """
    # Buscamos la búsqueda por su ID, pero con una condición de seguridad clave:
    # nos aseguramos de que la búsqueda pertenezca al usuario que está logueado.
    # Esto evita que un usuario pueda ver el historial de otro.
    busqueda = get_object_or_404(Busqueda, pk=busqueda_id, usuario=request.user)
    
    context = {
        'busqueda': busqueda
        # Los resultados asociados ya vienen dentro de 'busqueda.resultados.all'
    }
    return render(request, 'consultas/detalle_busqueda.html', context)



@login_required
def dashboard(request):
    # --- RANGO DE TIEMPO ---
    # Analizaremos los datos de los últimos 30 días
    hoy = timezone.now()
    hace_30_dias = hoy - timedelta(days=30)

    # --- FILTRO BASE ---
    # Obtenemos todas las búsquedas de la EMPRESA del usuario actual en el rango de tiempo
    busquedas = Busqueda.objects.filter(
        usuario__empresa=request.user.empresa, 
        fecha_busqueda__gte=hace_30_dias
    )

    # --- MÉTRICAS PRINCIPALES (KPIs) ---
    total_consultas_mes = busquedas.count()
    total_alertas_mes = busquedas.filter(genero_alerta=True).count()
    
    consultas_hoy = busquedas.filter(fecha_busqueda__date=hoy.date()).count()
    alertas_hoy = busquedas.filter(fecha_busqueda__date=hoy.date(), genero_alerta=True).count()
    
    tasa_alerta = (total_alertas_mes / total_consultas_mes * 100) if total_consultas_mes > 0 else 0

    # --- DATOS PARA GRÁFICO DE TENDENCIAS ---
    # Contamos las consultas por día para los últimos 30 días
    tendencia_consultas = (busquedas
                           .annotate(dia=TruncDay('fecha_busqueda'))
                           .values('dia')
                           .annotate(conteo=Count('id'))
                           .order_by('dia'))
    
    tendencia_alertas = (busquedas.filter(genero_alerta=True)
                         .annotate(dia=TruncDay('fecha_busqueda'))
                         .values('dia')
                         .annotate(conteo=Count('id'))
                         .order_by('dia'))

    # Preparamos los datos para Chart.js
    labels_tendencia = [item['dia'].strftime('%d/%m') for item in tendencia_consultas]
    data_consultas = [item['conteo'] for item in tendencia_consultas]
    data_alertas = [item['conteo'] for item in tendencia_alertas]

    # --- DATOS PARA GRÁFICO DE FUENTES DE ALERTA (La parte "Revolucionaria") ---
    # Analizamos de qué tipo de listas vienen las alertas más comunes
    fuentes_alertas = (Resultado.objects.filter(busqueda__in=busquedas, es_restrictiva=True)
                       .values('tipo_lista')
                       .annotate(conteo=Count('tipo_lista'))
                       .order_by('-conteo'))

    labels_fuentes = [item['tipo_lista'] for item in fuentes_alertas]
    data_fuentes = [item['conteo'] for item in fuentes_alertas]

    # --- BÚSQUEDAS RECIENTES ---
    ultimas_busquedas = busquedas.order_by('-fecha_busqueda')[:5]

    context = {
        'total_consultas_mes': total_consultas_mes,
        'total_alertas_mes': total_alertas_mes,
        'consultas_hoy': consultas_hoy,
        'alertas_hoy': alertas_hoy,
        'tasa_alerta': round(tasa_alerta, 2),
        'ultimas_busquedas': ultimas_busquedas,
        'labels_tendencia': labels_tendencia,
        'data_consultas': data_consultas,
        'data_alertas': data_alertas,
        'labels_fuentes': labels_fuentes,
        'data_fuentes': data_fuentes,
    }
    return render(request, 'consultas/dashboard.html', context)


@login_required
def generar_pdf_busqueda(request, busqueda_id):
    """
    Genera un reporte en PDF para una búsqueda específica.
    """
    # 1. Obtenemos la búsqueda de forma segura
    busqueda = get_object_or_404(Busqueda, pk=busqueda_id, usuario=request.user)

    # 2. Renderizamos la plantilla HTML a una cadena de texto
    #    Pasamos el objeto 'busqueda' al contexto de la plantilla.
    html_string = render_to_string('consultas/reporte_pdf.html', {'busqueda': busqueda})

    # 3. Usamos WeasyPrint para convertir el HTML en un PDF en memoria
    html = HTML(string=html_string)
    pdf = html.write_pdf()

    # 4. Creamos una respuesta HTTP con el contenido del PDF
    response = HttpResponse(pdf, content_type='application/pdf')

    # 5. Añadimos una cabecera para que el navegador lo trate como una descarga
    #    con un nombre de archivo dinámico.
    response['Content-Disposition'] = f'attachment; filename="Reporte-LAFT-{busqueda.termino_buscado}.pdf"'
    
    return response