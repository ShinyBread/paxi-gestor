# inventario/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('', views.lista_productos, name='lista_productos'),
    
    # --- ELIMINA ESTA LÍNEA (si aún existe) ---
    # path('producto/editar/<int:producto_id>/', views.editar_producto, name='editar_producto'),
    
    # --- AÑADE ESTA LÍNEA PARA LA FUNCIÓN DE ELIMINAR ---
    path('producto/eliminar/<int:producto_id>/', views.eliminar_producto, name='eliminar_producto'),

    # Sección de Reportes y Ventas (sin cambios)
    path('reporte/', views.reporte_mensual, name='reporte_mensual'),
    path('venta/eliminar/<int:venta_id>/', views.eliminar_venta, name='eliminar_venta'),
    path('historial/compras/', views.historial_compras, name='historial_compras'),
    path('exportar/excel/', views.exportar_excel, name='exportar_excel'),
]