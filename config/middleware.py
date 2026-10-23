from django.http import HttpResponse


class HealthCheckMiddleware:
    """Answer the platform's health probe before anything else looks at the request.

    The probe comes over plain HTTP with an internal Host/IP, so it must reach neither the Host check
    (ALLOWED_HOSTS) nor the HTTPS redirect: both live in middleware that runs later.
    """

    path = "/healthz/"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path == self.path:
            return HttpResponse("ok")
        return self.get_response(request)
