# inventario/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('', views.lista_productos, name='lista_productos'),
    path('producto/eliminar/<int:producto_id>/', views.eliminar_producto, name='eliminar_producto'),
    path('reporte/', views.reporte_mensual, name='reporte_mensual'),
    path('venta/eliminar/<int:venta_id>/', views.eliminar_venta, name='eliminar_venta'),
    path('historial/compras/', views.historial_compras, name='historial_compras'),
    path('exportar/excel/', views.exportar_excel, name='exportar_excel'),
    path('pedidos/seguimiento/', views.seguimiento_pedidos, name='seguimiento_pedidos'),
    
    
]