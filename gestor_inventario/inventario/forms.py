# inventario/forms.py
from django import forms
from .models import Producto, Venta

# --- ESTE ES EL FORMULARIO MODIFICADO ---
class RegistroInventarioForm(forms.Form):
    # Campo para seleccionar un producto existente (opcional)
    producto_existente = forms.ModelChoiceField(
        queryset=Producto.objects.all().order_by('nombre'), # Ordenado alfabéticamente
        required=False,
        label="Producto Existente (Opcional)",
        widget=forms.Select(attrs={'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm'})
    )
    
    # --- Campos para crear un producto nuevo (opcional) ---
    nuevo_producto_nombre = forms.CharField(
        required=False, 
        label="Nombre del Nuevo Producto",
        widget=forms.TextInput(attrs={'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm'})
    )
    precio_venta = forms.DecimalField(
        required=False, 
        label="Precio de Venta (Unitario)",
        min_value=0,
        decimal_places=0,
        widget=forms.NumberInput(attrs={'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm'})
    )

    # --- Campos de la compra (siempre requeridos) ---
    cantidad = forms.IntegerField(
        label="Cantidad Comprada",
        min_value=1,
        widget=forms.NumberInput(attrs={'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm'})
    )
    costo_total = forms.DecimalField(
        label="Costo Total del Lote (Ej: 2500)",
        min_value=0,
        decimal_places=0,
        widget=forms.NumberInput(attrs={'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm'})
    )

    # ==================================================================
    # --- NUEVO MÉTODO DE VALIDACIÓN (AÑADIDO) ---
    # ==================================================================
    def clean_nuevo_producto_nombre(self):
        """
        Verifica si el nombre del nuevo producto ya existe en la base de datos.
        """
        nombre = self.cleaned_data.get('nuevo_producto_nombre')
        
        # Solo hacemos la comprobación si el usuario escribió un nombre
        if nombre:
            # Usamos 'iexact' para una búsqueda exacta sin importar mayúsculas/minúsculas
            if Producto.objects.filter(nombre__iexact=nombre).exists():
                # Si existe, lanzamos un error de validación
                raise forms.ValidationError(
                    f"Ya existe un producto llamado '{nombre}'. "
                    f"Si quieres añadir stock, búscalo en la lista de 'Producto Existente'."
                )
        
        # Siempre devuelve el dato, ya sea el nombre o None
        return nombre

    # --- Lógica de Validación (Sin cambios) ---
    def clean(self):
        cleaned_data = super().clean()
        existente = cleaned_data.get("producto_existente")
        nuevo_nombre = cleaned_data.get("nuevo_producto_nombre")

        # 1. Debe elegir uno (existente O nuevo), pero no ambos
        if existente and nuevo_nombre:
            raise forms.ValidationError(
                "Error: No puedes seleccionar un producto existente Y crear uno nuevo a la vez.", 
                code='conflicto'
            )
        
        # 2. Debe elegir al menos uno
        if not existente and not nuevo_nombre:
            raise forms.ValidationError(
                "Debes seleccionar un producto existente o ingresar el nombre de uno nuevo.", 
                code='requerido'
            )
            
        # 3. Si es nuevo, el precio de venta es obligatorio
        if nuevo_nombre and not cleaned_data.get("precio_venta"):
            self.add_error('precio_venta', 'Este campo es obligatorio al crear un producto nuevo.')
        
        return cleaned_data


# --- Formulario de Edición (sin cambios) ---
class ProductoEditForm(forms.ModelForm):
    class Meta:
        model = Producto
        fields = ['nombre', 'precio_venta']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm'}),
            'precio_venta': forms.NumberInput(attrs={'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm'}),
        }


# --- VentaForm (Sin cambios) ---
class VentaForm(forms.ModelForm):
    class Meta:
        model = Venta
        fields = ['producto', 'cantidad', 'cliente']
        widgets = {
            'producto': forms.Select(attrs={'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm'}),
            'cantidad': forms.NumberInput(attrs={'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm'}),
            'cliente': forms.TextInput(attrs={'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm', 'placeholder': 'Opcional'}),
        }

    def clean_cantidad(self):
        cantidad = self.cleaned_data.get('cantidad')
        producto = self.cleaned_data.get('producto')
        if producto and cantidad > producto.stock:
            raise forms.ValidationError(f"No hay suficiente stock. Stock actual: {producto.stock}")
        return cantidad