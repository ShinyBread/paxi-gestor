from django.db import models
from django.utils import timezone
from decimal import Decimal


class Producto(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    stock = models.PositiveIntegerField(default=0)
    precio_compra = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    precio_venta = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return self.nombre


class Compra(models.Model):
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE)
    cantidad = models.PositiveIntegerField()
    costo_total = models.DecimalField(max_digits=10, decimal_places=2)
    fecha_compra = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Compra {self.producto.nombre} ({self.cantidad})"


class Venta(models.Model):
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE)
    cantidad = models.PositiveIntegerField()
    cliente = models.CharField(max_length=100, blank=True, null=True)
    fecha_venta = models.DateTimeField(default=timezone.now)
    total_venta = models.DecimalField(max_digits=10, decimal_places=2)
    ganancia = models.DecimalField(max_digits=10, decimal_places=2)

    def save(self, *args, **kwargs):
        if not self.pk:
            self.total_venta = self.cantidad * self.producto.precio_venta
            costo_total = self.cantidad * self.producto.precio_compra
            self.ganancia = self.total_venta - costo_total

        super().save(*args, **kwargs)

    def __str__(self):
        return f"Venta {self.producto.nombre} ({self.cantidad})"
