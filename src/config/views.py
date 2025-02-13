from django.shortcuts import render


def home(request):
    return render(request, "home/home.html")


def contact(request):
    return render(request, "contact/contact.html")
