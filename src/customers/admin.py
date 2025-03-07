from django.contrib import admin
from .models import OrganizationCustomer


# Register your models here.
@admin.register(OrganizationCustomer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("organization",)
