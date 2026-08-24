"""Project-wide middleware."""


class NoStoreHTMLMiddleware:
    """Stop browsers caching logged-in HTML pages.

    Django sets no Cache-Control on ordinary responses and nginx adds none
    either, which lets browsers heuristically cache dashboards. That served
    stale pages to signed-in users — a teacher could open the scoring grid and
    get yesterday's markup and scores, and freshly deployed JS/HTML would not
    take effect until a hard reload.

    Only HTML for authenticated users is marked no-store; static files are
    served by nginx and never reach this middleware, so their caching is
    untouched.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if not getattr(request, 'user', None) or not request.user.is_authenticated:
            return response

        # Leave anything the view deliberately marked cacheable alone.
        if response.has_header('Cache-Control'):
            return response

        content_type = response.get('Content-Type', '')
        if content_type.startswith('text/html'):
            response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            response['Pragma'] = 'no-cache'

        return response
