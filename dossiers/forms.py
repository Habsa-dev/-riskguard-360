"""
RiskGuard 360 - Formulaires
============================
Formulaires de saisie avec validation stricte.
"""

from django import forms
from django.core.exceptions import ValidationError
from .models import Client, DossierPret, PieceJustificative


class ClientForm(forms.ModelForm):
    """Formulaire de création / modification d'un client."""

    class Meta:
        model = Client
        fields = [
            'type_client', 'nom', 'prenom', 'date_naissance',
            'telephone', 'email', 'adresse', 'numero_cni', 'profession',
            'revenu_mensuel', 'charges_mensuelles', 'dettes_existantes',
            'anciennete_emploi', 'incidents_paiement',
            # Champs entreprise
            'raison_sociale', 'numero_registre_commerce',
            'secteur_activite', 'chiffre_affaires_annuel',
        ]
        widgets = {
            'date_naissance': forms.DateInput(attrs={
                'type': 'date', 'class': 'form-control'
            }),
            'type_client': forms.Select(attrs={'class': 'form-select', 'id': 'id_type_client'}),
            'profession': forms.Select(attrs={'class': 'form-select'}),
            'adresse': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'nom': forms.TextInput(attrs={'class': 'form-control'}),
            'prenom': forms.TextInput(attrs={'class': 'form-control'}),
            'telephone': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'revenu_mensuel': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'charges_mensuelles': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'dettes_existantes': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'anciennete_emploi': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'step': '0.5'}),
            'incidents_paiement': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'raison_sociale': forms.TextInput(attrs={'class': 'form-control'}),
            'numero_registre_commerce': forms.TextInput(attrs={'class': 'form-control'}),
            'secteur_activite': forms.TextInput(attrs={'class': 'form-control'}),
            'chiffre_affaires_annuel': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        type_client = cleaned_data.get('type_client')

        if type_client == 'entreprise':
            if not cleaned_data.get('raison_sociale'):
                self.add_error('raison_sociale', "La raison sociale est obligatoire pour une entreprise.")
            if not cleaned_data.get('numero_registre_commerce'):
                self.add_error('numero_registre_commerce', "Le numéro de registre de commerce est obligatoire.")
        else:
            if not cleaned_data.get('prenom'):
                self.add_error('prenom', "Le prénom est obligatoire pour un particulier.")
            if not cleaned_data.get('date_naissance'):
                self.add_error('date_naissance', "La date de naissance est obligatoire pour un particulier.")

        revenu = cleaned_data.get('revenu_mensuel', 0)
        if revenu is not None and revenu <= 0:
            self.add_error('revenu_mensuel', "Le revenu mensuel doit être supérieur à 0.")

        return cleaned_data


class DossierPretForm(forms.ModelForm):
    """Formulaire de création d'un dossier de prêt."""

    class Meta:
        model = DossierPret
        fields = [
            'client', 'montant_demande', 'duree_mois',
            'objet_pret', 'apport_personnel', 'description',
        ]
        widgets = {
            'client': forms.Select(attrs={'class': 'form-select'}),
            'montant_demande': forms.NumberInput(attrs={
                'class': 'form-control', 'min': '10000',
                'placeholder': 'Montant en FCFA'
            }),
            'duree_mois': forms.NumberInput(attrs={
                'class': 'form-control', 'min': '1', 'max': '360',
                'placeholder': 'Durée en mois'
            }),
            'objet_pret': forms.Select(attrs={'class': 'form-select'}),
            'apport_personnel': forms.NumberInput(attrs={
                'class': 'form-control', 'min': '0',
                'placeholder': 'Apport en FCFA'
            }),
            'description': forms.Textarea(attrs={
                'rows': 4, 'class': 'form-control',
                'placeholder': 'Décrivez l\'objet et la justification du prêt...'
            }),
        }

    def clean_montant_demande(self):
        montant = self.cleaned_data.get('montant_demande')
        if montant and montant < 10000:
            raise ValidationError("Le montant minimum est de 10 000 FCFA.")
        if montant and montant > 500_000_000:
            raise ValidationError("Le montant maximum est de 500 000 000 FCFA.")
        return montant

    def clean_duree_mois(self):
        duree = self.cleaned_data.get('duree_mois')
        if duree and duree < 1:
            raise ValidationError("La durée minimum est de 1 mois.")
        if duree and duree > 360:
            raise ValidationError("La durée maximum est de 360 mois (30 ans).")
        return duree

    def clean(self):
        cleaned_data = super().clean()
        montant = cleaned_data.get('montant_demande')
        apport = cleaned_data.get('apport_personnel', 0)

        if montant and apport and apport >= montant:
            self.add_error('apport_personnel',
                           "L'apport personnel ne peut pas être supérieur ou égal au montant demandé.")

        return cleaned_data


class PieceJustificativeForm(forms.ModelForm):
    """Formulaire d'upload de pièce justificative."""

    class Meta:
        model = PieceJustificative
        fields = ['type_piece', 'fichier']
        widgets = {
            'type_piece': forms.Select(attrs={'class': 'form-select'}),
            'fichier': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }

    def clean_fichier(self):
        fichier = self.cleaned_data.get('fichier')
        if fichier:
            # Validation taille (max 10 MB)
            if fichier.size > 10 * 1024 * 1024:
                raise ValidationError("La taille du fichier ne doit pas dépasser 10 Mo.")
            # Validation extension
            ext = fichier.name.split('.')[-1].lower()
            extensions_autorisees = ['pdf', 'jpg', 'jpeg', 'png', 'doc', 'docx']
            if ext not in extensions_autorisees:
                raise ValidationError(
                    f"Extension non autorisée. Extensions acceptées : {', '.join(extensions_autorisees)}"
                )
        return fichier


class ChangerEtatForm(forms.Form):
    """Formulaire pour changer l'état d'un dossier (workflow)."""

    nouvel_etat = forms.ChoiceField(
        choices=DossierPret.ETAT_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    motif = forms.CharField(
        required=True,
        widget=forms.Textarea(attrs={
            'rows': 3, 'class': 'form-control',
            'placeholder': 'Justifiez le changement d\'état...'
        }),
        label="Motif"
    )

