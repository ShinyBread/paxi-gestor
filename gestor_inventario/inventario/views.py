from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Sum, Q
from django.utils import timezone
from datetime import datetime
from decimal import Decimal, InvalidOperation
from django.core.paginator import Paginator
from django.http import HttpResponse
import pandas as pd
import io
from .models import Producto, Venta, Compra
from .forms import RegistroInventarioForm, ProductoEditForm, VentaForm


def lista_productos(request):
    inventario_form = RegistroInventarioForm()
    venta_form = VentaForm()
    edit_form = ProductoEditForm()

    if request.method == 'POST':
        form_type = request.POST.get('form_type')

        # ================== COMPRAS ==================
        if form_type == 'inventario':
            inventario_form = RegistroInventarioForm(request.POST)
            if inventario_form.is_valid():
                cd = inventario_form.cleaned_data

                if cd.get('nuevo_producto_nombre'):
                    producto = Producto.objects.create(
                        nombre=cd['nuevo_producto_nombre'],
                        precio_venta=cd['precio_venta'],
                        stock=0,
                        precio_compra=0
                    )
                else:
                    producto = cd['producto_existente']

                stock_actual = producto.stock
                valor_actual = stock_actual * producto.precio_compra

                cantidad = cd['cantidad']
                costo_total = cd['costo_total']

                nuevo_stock = stock_actual + cantidad
                nuevo_valor = valor_actual + costo_total

                nuevo_cpp = (
                    nuevo_valor / Decimal(nuevo_stock)
                    if nuevo_stock > 0 else Decimal('0.00')
                )

                producto.stock = nuevo_stock
                producto.precio_compra = round(nuevo_cpp, 2)
                producto.save()

                Compra.objects.create(
                    producto=producto,
                    cantidad=cantidad,
                    costo_total=costo_total
                )

                return redirect('lista_productos')

        # ================== VENTAS ==================
        elif form_type == 'venta':
            venta_form = VentaForm(request.POST)
            if venta_form.is_valid():
                venta = venta_form.save(commit=False)
                producto = venta.producto

                if venta.cantidad > producto.stock:
                    venta_form.add_error('cantidad', 'Stock insuficiente')
                else:
                    producto.stock -= venta.cantidad
                    producto.save()
                    venta.save()
                    return redirect('lista_productos')

        # ================== EDITAR PRODUCTO ==================
        elif form_type == 'edit_producto':
            producto = get_object_or_404(Producto, id=request.POST.get('producto_id'))
            edit_form = ProductoEditForm(request.POST, instance=producto)
            if edit_form.is_valid():
                edit_form.save()
                return redirect('lista_productos')

    queryset = Producto.objects.all().order_by('nombre')

    search_query = request.GET.get('q', '')
    filtro_stock = request.GET.get('filtro_stock', '')

    if search_query:
        queryset = queryset.filter(nombre__icontains=search_query)

    if filtro_stock == 'agotado':
        queryset = queryset.filter(stock=0)
    elif filtro_stock == 'poco_stock':
        queryset = queryset.filter(stock__gt=0, stock__lt=10)
    elif filtro_stock == 'en_stock':
        queryset = queryset.filter(stock__gte=10)

    paginator = Paginator(queryset, 9)
    productos_pagina = paginator.get_page(request.GET.get('page'))

    return render(request, 'inventario/lista_productos.html', {
        'productos_pagina': productos_pagina,
        'inventario_form': inventario_form,
        'venta_form': venta_form,
        'edit_form': edit_form,
        'search_query': search_query,
        'filtro_stock': filtro_stock
    })



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
        venta = get_object_or_404(Venta, id=request.POST.get('venta_id'))

        try:
            nuevo_total = Decimal(request.POST.get('nuevo_total_venta'))
        except (InvalidOperation, TypeError):
            nuevo_total = venta.total_venta

        costo_real = venta.producto.precio_compra * venta.cantidad

        venta.total_venta = nuevo_total
        venta.ganancia = nuevo_total - costo_real

        venta.save(update_fields=['total_venta', 'ganancia'])

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

    ventas_mes = Venta.objects.filter(
        fecha_venta__year=year,
        fecha_venta__month=month
    ).order_by('-fecha_venta')

    total_ventas = ventas_mes.aggregate(
        total=Sum('total_venta')
    )['total'] or Decimal('0.00')

    ganancia_total = ventas_mes.aggregate(
        total=Sum('ganancia')
    )['total'] or Decimal('0.00')

    return render(request, 'inventario/reporte_mensual.html', {
        'ventas': ventas_mes,
        'total_ventas': total_ventas,
        'ganancia_total': ganancia_total,
        'fecha_reporte': datetime(year, month, 1),
        'meses_disponibles': meses_disponibles,
        'selected_year': year,
        'selected_month': month
    })



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
