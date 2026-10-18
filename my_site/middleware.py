from django.utils import translation


class FrenchAccountPagesMiddleware:
    """Affiche en français les pages de connexion / inscription (django-allauth).

    On n'active le français que sous /accounts/ : les autres pages gardent la
    langue du projet, ce qui évite de changer le format des nombres affichés
    dans les tableaux de bord immo et dividendes.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.path.startswith("/accounts/"):
            return self.get_response(request)

        with translation.override("fr"):
            return self.get_response(request)
