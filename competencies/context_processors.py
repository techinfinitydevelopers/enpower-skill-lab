"""Context processor that feeds the header bell-icon on every role dashboard
with the announcements actually targeted to that user (PPT slide 8).

Exposes on every template:
  nav_announcements       - list of Announcement objects (latest first, max 8)
  nav_announcement_count  - how many (used for the bell badge)

All targeting is delegated to competencies.announcements.announcements_for_user
so students, parents, teachers, coordinators and school admins share one rule.
"""


def nav_notifications(request):
    user = getattr(request, 'user', None)
    if not user or not getattr(user, 'is_authenticated', False):
        return {}

    anns = []
    try:
        from competencies.announcements import announcements_for_user
        anns = announcements_for_user(user)
    except Exception:
        anns = []

    anns = sorted(anns, key=lambda a: a.created_at, reverse=True)[:8]
    return {'nav_announcements': anns, 'nav_announcement_count': len(anns)}
