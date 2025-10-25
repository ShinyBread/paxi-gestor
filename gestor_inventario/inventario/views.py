# inventario/views.py

from django.shortcuts import render, redirect, get_object_or_404
from .models import Producto, Venta, Compra
from .forms import RegistroInventarioForm, ProductoEditForm, VentaForm
from django.db.models import Sum, Q
from django.utils import timezone
from datetime import datetime
from django.core.paginator import Paginator
import pandas as pd
from django.http import HttpResponse
import io


# --- VISTA PRINCIPAL (PRODUCTOS, VENTAS, EDICIÓN) ---

def lista_productos(request):
    """
    Maneja la lista, filtros, paginación, y los 3 formularios (modales)
    de añadir inventario, registrar venta y editar producto.
    """
    
    # Inicializa los formularios
    inventario_form = RegistroInventarioForm()
    venta_form = VentaForm()
    edit_form = ProductoEditForm()

    # --- Lógica de POST (Manejo de los 3 formularios) ---
    if request.method == 'POST':
        form_type = request.POST.get('form_type')
        
        # CASO 1: Se envió el formulario de AÑADIR INVENTARIO
        if form_type == 'inventario':
            inventario_form = RegistroInventarioForm(request.POST)
            if inventario_form.is_valid():
                cd = inventario_form.cleaned_data
                producto = None

                if cd.get('nuevo_producto_nombre'):
                    # Si es un producto nuevo, lo creamos
                    producto = Producto.objects.create(
                        nombre=cd['nuevo_producto_nombre'],
                        precio_venta=cd['precio_venta'],
                        stock=0,
                        precio_compra=0
                    )
                else:
                    # Si es uno existente, lo seleccionamos
                    producto = cd.get('producto_existente')

                # Lógica de Costo Promedio Ponderado
                stock_actual = producto.stock
                costo_actual_unitario = producto.precio_compra
                valor_inventario_actual = stock_actual * costo_actual_unitario
                
                cantidad_comprada = cd['cantidad']
                costo_compra_actual = cd['costo_total']
                
                nuevo_stock_total = stock_actual + cantidad_comprada
                nuevo_valor_inventario_total = valor_inventario_actual + costo_compra_actual
                
                nuevo_costo_promedio = 0
                if nuevo_stock_total > 0:
                    nuevo_costo_promedio = nuevo_valor_inventario_total / nuevo_stock_total
                
                # Actualizamos el producto con el nuevo stock y costo
                producto.stock = nuevo_stock_total
                producto.precio_compra = round(nuevo_costo_promedio, 0)
                producto.save()
                
                # Guardamos un registro de la compra
                Compra.objects.create(
                    producto=producto,
                    cantidad=cantidad_comprada,
                    costo_total=costo_compra_actual
                )
                return redirect('lista_productos') # Redirigimos a la misma pág (limpia)

        # CASO 2: Se envió el formulario de REGISTRAR VENTA
        elif form_type == 'venta':
            venta_form = VentaForm(request.POST)
            if venta_form.is_valid():
                venta = venta_form.save(commit=False)
                producto = venta.producto
                # Descontamos el stock
                producto.stock -= venta.cantidad
                producto.save()
                # Guardamos la venta (el modelo Venta calcula la ganancia)
                venta.save() 
                return redirect('lista_productos')
        
        # CASO 3: Se envió el formulario de EDITAR PRODUCTO
        elif form_type == 'edit_producto':
            producto_id = request.POST.get('producto_id')
            producto = get_object_or_404(Producto, id=producto_id)
            # Pasamos la instancia del producto para que se actualice
            edit_form = ProductoEditForm(request.POST, instance=producto)
            if edit_form.is_valid():
                edit_form.save()
                return redirect('lista_productos')
            # Si el form no es válido, la vista continuará y pasará el
            # 'edit_form' con errores al contexto para mostrarlo en el modal.

    # --- Lógica de GET (Filtros, Búsqueda y Paginación) ---
    queryset = Producto.objects.all().order_by('nombre')
    search_query = request.GET.get('q', '')
    filtro_stock = request.GET.get('filtro_stock', '')

    if search_query:
        queryset = queryset.filter(Q(nombre__icontains=search_query))
    if filtro_stock:
        if filtro_stock == 'agotado':
            queryset = queryset.filter(stock=0)
        elif filtro_stock == 'poco_stock':
            queryset = queryset.filter(stock__gt=0, stock__lt=10)
        elif filtro_stock == 'en_stock':
            queryset = queryset.filter(stock__gte=10)

    # Lógica de Paginación (9 productos por página)
    paginator = Paginator(queryset, 9)
    page_number = request.GET.get('page')
    productos_pagina = paginator.get_page(page_number)

    # --- Contexto Final ---
    context = {
        'productos_pagina': productos_pagina, # Objeto de página para el template
        'search_query': search_query,
        'filtro_stock': filtro_stock,
        'inventario_form': inventario_form, # Form para el modal de inventario
        'venta_form': venta_form,         # Form para el modal de venta
        'edit_form': edit_form,           # Form para el modal de edición
    }
    return render(request, 'inventario/lista_productos.html', context)


# --- VISTAS DE ELIMINACIÓN ---

def eliminar_producto(request, producto_id):
    """
    Elimina un producto. Solo acepta peticiones POST por seguridad.
    """
    producto = get_object_or_404(Producto, id=producto_id)
    if request.method == 'POST':
        producto.delete()
    return redirect('lista_productos')


def eliminar_venta(request, venta_id):
    """
    Elimina una venta y restaura el stock al producto correspondiente.
    """
    venta = get_object_or_404(Venta, id=venta_id)
    if request.method == 'POST':
        producto = venta.producto
        # Restauramos el stock
        producto.stock += venta.cantidad
        producto.save()
        # Eliminamos la venta
        venta.delete()
    return redirect('reporte_mensual')


# --- VISTA DE REPORTES ---

def reporte_mensual(request):
    """
    Muestra el reporte de ventas de un mes específico.
    Incluye navegación para ver meses anteriores con ventas.
    """
    
    meses_disponibles = Venta.objects.dates('fecha_venta', 'month', order='DESC')
    today = timezone.now()
    
    try:
        year = int(request.GET.get('year'))
        month = int(request.GET.get('month'))
    except (TypeError, ValueError):
        # Si no hay parámetros GET, selecciona el mes más reciente CON ventas
        if meses_disponibles:
            year = meses_disponibles[0].year
            month = meses_disponibles[0].month
        else:
            # Si no hay ventas, muestra el mes actual
            year = today.year
            month = today.month

    # Asegurarse de que si se selecciona un mes sin ventas, redirija al más reciente
    if not Venta.objects.filter(fecha_venta__year=year, fecha_venta__month=month).exists() and meses_disponibles:
        year = meses_disponibles[0].year
        month = meses_disponibles[0].month

    ventas_mes = Venta.objects.filter(
        fecha_venta__year=year,
        fecha_venta__month=month
    ).order_by('-fecha_venta')

    total_ventas_mes = ventas_mes.aggregate(Sum('total_venta'))['total_venta__sum'] or 0
    ganancia_total_mes = ventas_mes.aggregate(Sum('ganancia'))['ganancia__sum'] or 0
    
    context = {
        'ventas': ventas_mes,
        'total_ventas': total_ventas_mes,
        'ganancia_total': ganancia_total_mes,
        'fecha_reporte': datetime(year, month, 1),
        'meses_disponibles': meses_disponibles,
        'selected_year': int(year),
        'selected_month': int(month),
    }
    return render(request, 'inventario/reporte_mensual.html', context)
def historial_compras(request):
    """
    Muestra una lista de todas las compras registradas,
    ordenadas por fecha (la más reciente primero).
    """
    # Obtenemos todas las compras, incluyendo el producto relacionado
    # y ordenamos por fecha descendente
    compras = Compra.objects.select_related('producto').order_by('-fecha_compra')
    
    # Podríamos añadir paginación aquí si la lista se vuelve muy larga
    # paginator = Paginator(compras, 20) # 20 por página
    # page_number = request.GET.get('page')
    # compras_pagina = paginator.get_page(page_number)
    
    context = {
        'compras': compras, # O 'compras': compras_pagina si usas paginación
    }
    return render(request, 'inventario/historial_compras.html', context)
def exportar_excel(request):
    """
    Exporta los datos de Productos, Ventas y Compras a un archivo Excel (.xlsx).
    """
    # 1. Obtener todos los datos
    productos = Producto.objects.all().values(
        'nombre', 'stock', 'precio_compra', 'precio_venta'
    )
    ventas = Venta.objects.select_related('producto').all().values(
        'fecha_venta', 'producto__nombre', 'cantidad', 'total_venta', 'ganancia', 'cliente'
    )
    compras = Compra.objects.select_related('producto').all().values(
        'fecha_compra', 'producto__nombre', 'cantidad', 'costo_total'
    )

    # 2. Crear DataFrames de Pandas
    df_productos = pd.DataFrame(list(productos))
    df_ventas = pd.DataFrame(list(ventas))
    df_compras = pd.DataFrame(list(compras))

    # Renombrar columnas para claridad en Excel
    df_productos.rename(columns={'precio_compra': 'costo_promedio'}, inplace=True)
    df_ventas.rename(columns={'producto__nombre': 'producto'}, inplace=True)
    df_compras.rename(columns={'producto__nombre': 'producto'}, inplace=True)

    # Formatear fechas (opcional, pero mejora la legibilidad)
    if not df_ventas.empty:
        df_ventas['fecha_venta'] = pd.to_datetime(df_ventas['fecha_venta']).dt.strftime('%Y-%m-%d %H:%M:%S')
    if not df_compras.empty:
        df_compras['fecha_compra'] = pd.to_datetime(df_compras['fecha_compra']).dt.strftime('%Y-%m-%d %H:%M:%S')


    # 3. Crear el archivo Excel en memoria
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_productos.to_excel(writer, sheet_name='Productos', index=False)
        df_ventas.to_excel(writer, sheet_name='Ventas', index=False)
        df_compras.to_excel(writer, sheet_name='Compras', index=False)

        # Ajustar ancho de columnas (opcional)
        for sheet_name in writer.sheets:
            worksheet = writer.sheets[sheet_name]
            for col in worksheet.columns:
                max_length = 0
                column = col[0].column_letter # Get the column name
                for cell in col:
                    try: # Necessary to avoid error on empty cells
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = (max_length + 2)
                worksheet.column_dimensions[column].width = adjusted_width


    output.seek(0) # Mover el cursor al inicio del stream

    # 4. Crear la respuesta HTTP
    response = HttpResponse(
        output,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename="inventario_export.xlsx"'

    return response
def seguimiento_pedidos(request):
    return render(request, 'inventario/seguimiento_pedidos.html', {})