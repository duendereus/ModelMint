def get_base_url(request):
    scheme = "https" if request.is_secure() else "http"
    return f"{scheme}://{request.get_host()}"
