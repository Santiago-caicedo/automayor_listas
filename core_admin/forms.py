# core_admin/forms.py
from django import forms
from cargas_masivas.models import LoteConsultaMasiva

class ProcesarLoteForm(forms.ModelForm):
    """
    Formulario para que el SuperAdmin procese un lote pendiente.
    Solo permite cambiar el estado y subir el archivo de resultado.
    """
    class Meta:
        model = LoteConsultaMasiva
        fields = ['estado', 'archivo_resultado']
        widgets = {
            'estado': forms.Select(attrs={'class': 'form-select'}),
            'archivo_resultado': forms.FileInput(attrs={'class': 'form-control'}),
        }