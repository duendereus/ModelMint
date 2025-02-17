from django.contrib.auth import authenticate, login
from django.shortcuts import render, redirect
from django.contrib.auth import get_user_model
from django.contrib import messages

User = get_user_model()


# Create your views here.
def login_view(request):
    if request.method == "POST":
        email = request.POST.get("email") or None
        password = request.POST.get("password") or None
        if all([email, password]):
            user = authenticate(request, email=email, password=password)
            if user is not None:
                login(request, user)
                return redirect("home")
            else:
                messages.error(request, "Invalid credentials, please try again!")
    return render(request, "accounts/login.html", {})
