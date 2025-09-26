from django.http import HttpResponse


def index(request):
    return HttpResponse("Građevinska knjiga — radi")
