from django.views.generic import TemplateView


class AtlasView(TemplateView):
    """Page publique de l'atlas. Tout le reste (carte, jeux, scores) se passe dans le navigateur."""

    template_name = "atlas/atlas.html"
