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


# --- FUNCIÓN AUXILIAR PARA CLASIFICAR ---
def get_classification(tipo_lista):
    if not tipo_lista:
        return 'No Clasificado'

    tipo_lista_upper = tipo_lista.upper()

    # 1. Listas Amarillas (Filtraciones específicas)
    yellow_lists = [
        "PARADISE PAPERS", "PANAMA PAPERS", "BAHAMAS LEAKS",
        "BOLETIN PANAMA PAPERS", "OFFSHORE LEAKS"
    ]
    if tipo_lista_upper in yellow_lists:
        return "Amarillo"

    # 2. Listas PEP's (Palabras clave)
    pep_keywords = [
        'PEP', 'GOBIERNO', 'CONSEJO', 'CORTE', 'EMBAJADAS', 'MINISTERIO',
        'PRESIDENCIA', 'SENADO', 'CAMARA', 'ASAMBLEA', 'ALCALDIAS',
        'CONCEJOS', 'NOTARIAS', 'SIGEP', 'ELECTORAL', 'JUDICATURA',
        'CANDIDATOS', 'PARTIDOS'
    ]
    # Check if *any* keyword is *part* of the tipo_lista string
    if any(keyword in tipo_lista_upper for keyword in pep_keywords):
        return "PEP's"

    # 3. Todo lo demás es Rojo
    return "Rojo"
# --- FIN FUNCIÓN AUXILIAR ---

@login_required
def pagina_busqueda(request):
    form = BusquedaForm()
    resultados_api = None
    alerta_generada = False
    busqueda_obj = None # Initialize outside the POST block

    if request.method == 'POST':
        form = BusquedaForm(request.POST)

        if form.is_valid():
            identificacion = form.cleaned_data.get("identificacion")
            nombres = form.cleaned_data.get("nombres")
            termino_buscado = ""

            # --- Decide API method ---
            if identificacion and nombres:
                termino_buscado = f"ID: {identificacion} y Nombre: {nombres}"
                resultados_api = consultar_api_por_id_y_nombre(identificacion, nombres)
            elif identificacion:
                termino_buscado = f"ID: {identificacion}"
                resultados_api = consultar_api_por_id(identificacion)
            elif nombres:
                termino_buscado = f"Nombre: {nombres}"
                resultados_api = consultar_api_por_nombre(nombres)

            # --- Save to Database ---
            if termino_buscado:
                busqueda_obj = Busqueda.objects.create( # Assign to the outer scope variable
                    usuario=request.user,
                    termino_buscado=termino_buscado
                )
                if resultados_api is not None:
                    busqueda_obj.encontro_resultados = bool(resultados_api)
                    for item in resultados_api:
                        es_restrictiva = item.get('Restrictiva', False)
                        if es_restrictiva:
                            alerta_generada = True

                        # --- Calculate and Save Classification ---
                        tipo_lista_api = item.get('Tipo_Lista', '')
                        clasificacion_calculada = get_classification(tipo_lista_api)
                        # --- End Calculate ---

                        Resultado.objects.create(
                            busqueda=busqueda_obj,

                            # Original fields
                            nombre_completo=item.get('NombreCompleto'),
                            identificacion=item.get('Id'),
                            tipo_lista=tipo_lista_api, # Use variable already retrieved
                            origen_lista=item.get('Origen_Lista'),
                            relacionado_con=item.get('Relacionado_Con'),
                            fuente=item.get('Fuente'),
                            es_restrictiva=es_restrictiva,

                            # New fields from Vadom PDF / SIDIF Guide
                            es_boletin=item.get('Boletin', False),
                            alias=item.get('Aka'),
                            coincidencia_nombre=item.get('CoincidenciaNombre', 0),
                            coincidencia_id=item.get('CoincidenciaID', 0),
                            tipo_persona=item.get('Tipo_Persona'),
                            fecha_update=item.get('Fecha_Update'), # Added from model
                            estado=item.get('Estado'),             # Added from model
                            llaveimagen=item.get('LlaveImagen'),   # Added from model

                            # Our internal classification
                            clasificacion=clasificacion_calculada
                        )

                    if alerta_generada:
                        busqueda_obj.genero_alerta = True
                    busqueda_obj.save()
        else:
            # If form is invalid, print errors
            print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
            print("!!!      FORMULARIO INVÁLIDO       !!!")
            print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
            print("Errores encontrados:", form.errors)

    # Prepare context for the template
    context = {
        'form': form,
        # 'resultados': resultados_api, # We don't show results directly anymore
        'alerta_generada': alerta_generada, # Keep for potential general alert messages
        'busqueda_obj': busqueda_obj, # Pass the created search object for the banner link
    }

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
    hoy = timezone.now()
    hace_30_dias = hoy - timedelta(days=30)

    # --- FILTRO BASE (Búsquedas de la empresa en el rango) ---
    busquedas_periodo = Busqueda.objects.filter(
        usuario__empresa=request.user.empresa,
        fecha_busqueda__gte=hace_30_dias
    )

    # --- OBTENER TODOS LOS RESULTADOS CLASIFICADOS DEL PERIODO ---
    resultados_periodo = Resultado.objects.filter(busqueda__in=busquedas_periodo)

    # --- MÉTRICAS PRINCIPALES POR CLASIFICACIÓN (KPIs) ---
    total_consultas_mes = busquedas_periodo.count()

    # Contamos resultados por clasificación en los últimos 30 días
    rojo_mes = resultados_periodo.filter(clasificacion='Rojo').count()
    amarillo_mes = resultados_periodo.filter(clasificacion='Amarillo').count()
    peps_mes = resultados_periodo.filter(clasificacion="PEP's").count()

    # Contamos resultados por clasificación para HOY
    busquedas_hoy_ids = busquedas_periodo.filter(fecha_busqueda__date=hoy.date()).values_list('id', flat=True)
    resultados_hoy = Resultado.objects.filter(busqueda_id__in=busquedas_hoy_ids)
    rojo_hoy = resultados_hoy.filter(clasificacion='Rojo').count()
    amarillo_hoy = resultados_hoy.filter(clasificacion='Amarillo').count()
    peps_hoy = resultados_hoy.filter(clasificacion="PEP's").count()
    consultas_hoy_count = len(busquedas_hoy_ids) # Contamos las búsquedas únicas de hoy

    # --- DATOS PARA GRÁFICO DE TENDENCIAS ---
    # Tendencia general de consultas
    tendencia_consultas = (busquedas_periodo
                           .annotate(dia=TruncDay('fecha_busqueda'))
                           .values('dia')
                           .annotate(conteo=Count('id'))
                           .order_by('dia'))

    # Tendencia de hallazgos ROJOS
    tendencia_rojos = (resultados_periodo.filter(clasificacion='Rojo')
                         .annotate(dia=TruncDay('busqueda__fecha_busqueda'))
                         .values('dia')
                         .annotate(conteo=Count('id'))
                         .order_by('dia'))

    # Preparamos los datos para Chart.js
    labels_tendencia = [item['dia'].strftime('%d/%m') for item in tendencia_consultas]
    data_consultas = [item['conteo'] for item in tendencia_consultas]
    # Aseguramos que los datos rojos coincidan con las etiquetas, rellenando días faltantes con 0
    rojos_dict = {item['dia']: item['conteo'] for item in tendencia_rojos}
    data_rojos = [rojos_dict.get(item['dia'], 0) for item in tendencia_consultas]


    # --- DATOS PARA GRÁFICO DE FUENTES ROJAS ---
    # Mantenemos este gráfico enfocado en las fuentes de riesgo ROJO (más críticas)
    fuentes_rojas = (resultados_periodo.filter(clasificacion='Rojo')
                       .values('tipo_lista')
                       .annotate(conteo=Count('tipo_lista'))
                       .order_by('-conteo')[:5]) # Top 5 fuentes rojas

    labels_fuentes = [item['tipo_lista'] if item['tipo_lista'] else 'N/A' for item in fuentes_rojas]
    data_fuentes = [item['conteo'] for item in fuentes_rojas]

    # --- BÚSQUEDAS RECIENTES ---
    ultimas_busquedas = busquedas_periodo.order_by('-fecha_busqueda')[:5]

    context = {
        'total_consultas_mes': total_consultas_mes,
        'consultas_hoy_count': consultas_hoy_count, # Nuevo nombre para claridad
        # Nuevas métricas por clasificación
        'rojo_mes': rojo_mes,
        'amarillo_mes': amarillo_mes,
        'peps_mes': peps_mes,
        'rojo_hoy': rojo_hoy,
        'amarillo_hoy': amarillo_hoy,
        'peps_hoy': peps_hoy,
        # Datos para gráficos y tabla
        'ultimas_busquedas': ultimas_busquedas,
        'labels_tendencia': labels_tendencia,
        'data_consultas': data_consultas,
        'data_rojos': data_rojos, # Cambiado de data_alertas
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
    html = HTML(string=html_string, base_url=request.build_absolute_uri('/'))
    pdf = html.write_pdf()

    # 4. Creamos una respuesta HTTP con el contenido del PDF
    response = HttpResponse(pdf, content_type='application/pdf')

    # 5. Añadimos una cabecera para que el navegador lo trate como una descarga
    #    con un nombre de archivo dinámico.
    response['Content-Disposition'] = f'attachment; filename="Reporte-LAFT-{busqueda.termino_buscado}.pdf"'
    
    return response