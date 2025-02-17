from django.contrib.auth import authenticate, login
from django.shortcuts import render, redirect
from django.contrib.auth import get_user_model
from django.contrib import messages, auth
from django.contrib.auth.decorators import login_required

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


@login_required(login_url="accounts:login")
def logout(request):
    auth.logout(request)
    messages.info(request, "You have sucesfully logged out!")
    return redirect("accounts:login")
