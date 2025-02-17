from django import forms
from .models import Contact


class ContactForm(forms.ModelForm):
    class Meta:
        model = Contact
        fields = ["name", "email", "subject", "content"]
        labels = {
            "name": "Full Name",
            "email": "Email Address",
            "subject": "Subject",
            "content": "Your Message",
        }
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "Enter your name"}),
            "email": forms.EmailInput(attrs={"placeholder": "Enter your email"}),
            "subject": forms.TextInput(attrs={"placeholder": "Enter the subject"}),
            "content": forms.Textarea(
                attrs={"placeholder": "Write your message here", "rows": 5}
            ),
        }
