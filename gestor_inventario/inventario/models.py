# inventario/models.py
from django.db import models
from django.utils import timezone

class Producto(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    # MODIFICADO: El stock se manejará con Compras y Ventas
    stock = models.PositiveIntegerField(default=0)
    # MODIFICADO: Este será el Costo Promedio Ponderado
    precio_compra = models.DecimalField(max_digits=10, decimal_places=0, default=0)
    precio_venta = models.DecimalField(max_digits=10, decimal_places=0)

    def __str__(self):
        return self.nombre

# --- NUEVO MODELO ---
class Compra(models.Model):
    """Registra una transacción de compra de inventario."""
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE)
    cantidad = models.PositiveIntegerField()
    costo_total = models.DecimalField(max_digits=10, decimal_places=0)
    fecha_compra = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Compra de {self.cantidad} x {self.producto.nombre}"

# --- MODELO VENTA (Sin cambios) ---
class Venta(models.Model):
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE)
    cantidad = models.PositiveIntegerField()
    cliente = models.CharField(max_length=100, blank=True, null=True)
    fecha_venta = models.DateTimeField(default=timezone.now)
    total_venta = models.DecimalField(max_digits=10, decimal_places=0, editable=False)
    ganancia = models.DecimalField(max_digits=10, decimal_places=0, editable=False)

    def save(self, *args, **kwargs):
        # La ganancia ahora usará el 'precio_compra' promedio del producto
        self.total_venta = self.cantidad * self.producto.precio_venta
        costo_total = self.cantidad * self.producto.precio_compra # Usa el CPP
        self.ganancia = self.total_venta - costo_total
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Venta de {self.cantidad} x {self.producto.nombre} el {self.fecha_venta.strftime('%Y-%m-%d')}"