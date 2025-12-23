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

def lista_productos(request):
    inventario_form = RegistroInventarioForm()
    venta_form = VentaForm()
    edit_form = ProductoEditForm()

    if request.method == 'POST':
        form_type = request.POST.get('form_type')
        
        if form_type == 'inventario':
            inventario_form = RegistroInventarioForm(request.POST)
            if inventario_form.is_valid():
                cd = inventario_form.cleaned_data
                producto = None

                if cd.get('nuevo_producto_nombre'):
                    producto = Producto.objects.create(
                        nombre=cd['nuevo_producto_nombre'],
                        precio_venta=cd['precio_venta'],
                        stock=0,
                        precio_compra=0
                    )
                else:
                    producto = cd.get('producto_existente')

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
                
                producto.stock = nuevo_stock_total
                producto.precio_compra = round(nuevo_costo_promedio, 0)
                producto.save()
                
                Compra.objects.create(
                    producto=producto,
                    cantidad=cantidad_comprada,
                    costo_total=costo_compra_actual
                )
                return redirect('lista_productos') 

        elif form_type == 'venta':
            venta_form = VentaForm(request.POST)
            if venta_form.is_valid():
                venta = venta_form.save(commit=False)
                producto = venta.producto
                producto.stock -= venta.cantidad
                producto.save()
                venta.save() 
                return redirect('lista_productos')
        
        elif form_type == 'edit_producto':
            producto_id = request.POST.get('producto_id')
            producto = get_object_or_404(Producto, id=producto_id)
            edit_form = ProductoEditForm(request.POST, instance=producto)
            if edit_form.is_valid():
                edit_form.save()
                return redirect('lista_productos')

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

    paginator = Paginator(queryset, 9)
    page_number = request.GET.get('page')
    productos_pagina = paginator.get_page(page_number)

    context = {
        'productos_pagina': productos_pagina, 
        'search_query': search_query,
        'filtro_stock': filtro_stock,
        'inventario_form': inventario_form, 
        'venta_form': venta_form,         
        'edit_form': edit_form,           
    }
    return render(request, 'inventario/lista_productos.html', context)


def eliminar_producto(request, producto_id):
    producto = get_object_or_404(Producto, id=producto_id)
    if request.method == 'POST':
        producto.delete()
    return redirect('lista_productos')


def eliminar_venta(request, venta_id):
    venta = get_object_or_404(Venta, id=venta_id)
    if request.method == 'POST':
        producto = venta.producto
        producto.stock += venta.cantidad
        producto.save()
        venta.delete()
    return redirect(request.META.get('HTTP_REFERER', 'reporte_mensual'))


def reporte_mensual(request):
    if request.method == 'POST' and 'editar_venta' in request.POST:
        venta_id = request.POST.get('venta_id')
        nuevo_total = float(request.POST.get('nuevo_total_venta'))
        venta = get_object_or_404(Venta, id=venta_id)
        costo_total_original = venta.total_venta - venta.ganancia
        venta.total_venta = nuevo_total
        venta.ganancia = nuevo_total - costo_total_original
        venta.save()
        return redirect(request.get_full_path())

    meses_disponibles = Venta.objects.dates('fecha_venta', 'month', order='DESC')
    today = timezone.now()
    
    try:
        year = int(request.GET.get('year'))
        month = int(request.GET.get('month'))
    except (TypeError, ValueError):
        if meses_disponibles:
            year = meses_disponibles[0].year
            month = meses_disponibles[0].month
        else:
            year = today.year
            month = today.month

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
    compras = Compra.objects.select_related('producto').order_by('-fecha_compra')
    context = {
        'compras': compras,
    }
    return render(request, 'inventario/historial_compras.html', context)


def exportar_excel(request):
    productos = Producto.objects.all().values(
        'nombre', 'stock', 'precio_compra', 'precio_venta'
    )
    ventas = Venta.objects.select_related('producto').all().values(
        'fecha_venta', 'producto__nombre', 'cantidad', 'total_venta', 'ganancia', 'cliente'
    )
    compras = Compra.objects.select_related('producto').all().values(
        'fecha_compra', 'producto__nombre', 'cantidad', 'costo_total'
    )
    
    df_productos = pd.DataFrame(list(productos))
    df_ventas = pd.DataFrame(list(ventas))
    df_compras = pd.DataFrame(list(compras))
    
    df_productos.rename(columns={'precio_compra': 'costo_promedio'}, inplace=True)
    df_ventas.rename(columns={'producto__nombre': 'producto'}, inplace=True)
    df_compras.rename(columns={'producto__nombre': 'producto'}, inplace=True)

    if not df_ventas.empty:
        df_ventas['fecha_venta'] = pd.to_datetime(df_ventas['fecha_venta']).dt.strftime('%Y-%m-%d %H:%M:%S')
    if not df_compras.empty:
        df_compras['fecha_compra'] = pd.to_datetime(df_compras['fecha_compra']).dt.strftime('%Y-%m-%d %H:%M:%S')

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_productos.to_excel(writer, sheet_name='Productos', index=False)
        df_ventas.to_excel(writer, sheet_name='Ventas', index=False)
        df_compras.to_excel(writer, sheet_name='Compras', index=False)

        for sheet_name in writer.sheets:
            worksheet = writer.sheets[sheet_name]
            for col in worksheet.columns:
                max_length = 0
                column = col[0].column_letter 
                for cell in col:
                    try: 
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = (max_length + 2)
                worksheet.column_dimensions[column].width = adjusted_width

    output.seek(0) 
    
    response = HttpResponse(
        output,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename="inventario_export.xlsx"'

    return response


def seguimiento_pedidos(request):
    return render(request, 'inventario/seguimiento_pedidos.html', {})