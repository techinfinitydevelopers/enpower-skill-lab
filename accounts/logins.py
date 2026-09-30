"""One shape for a login, so a capital letter cannot lock someone out.

Sign-in compares `username` exactly. A coach onboarded from a sheet that spelt
his address SUJITKUMAR5305@GMAIL.COM therefore could not get in by typing it
the way he reads it, and the form told him "Invalid credentials" -- the same
words it uses for a wrong password.

The fix is to store one shape. Everything email-shaped is trimmed and
lowercased on the way in, and sign-in trims and lowercases what it is given
before looking it up.

Registration IDs are left exactly as they are. Students and parents sign in
with `BI-RM-8A-235-25-stu`, uppercase by design and about 6,266 of them, so
lowercasing those would break the logins this is meant to protect. The test is
simply whether the value looks like an address.
"""


def normalise_login(value):
    """Trim, and lowercase only if it is email-shaped."""
    text = (value or '').strip()
    return text.lower() if '@' in text else text


def login_exists(value):
    """Is this login already taken, ignoring case for addresses?

    The duplicate checks used to be exact, which is how `Foo@x.com` could be
    created while `foo@x.com` already existed -- two accounts one keystroke
    apart, and only one of them reachable.
    """
    from django.contrib.auth import get_user_model

    user_model = get_user_model()
    text = (value or '').strip()
    if not text:
        return False
    if '@' in text:
        return (user_model.objects.filter(username__iexact=text).exists()
                or user_model.objects.filter(email__iexact=text).exists())
    return user_model.objects.filter(username=text).exists()


def resolve_login(value):
    """The stored username for what someone typed, or None.

    Exact match first, so nothing that works today can start behaving
    differently. Only when that misses do we look again ignoring case, and
    only for addresses.

    Two rows differing only in case would make this ambiguous, so it gives up
    rather than pick one. `diagnose_access --sweep` reports such pairs; there
    are none on the live data.
    """
    from django.contrib.auth import get_user_model

    user_model = get_user_model()
    text = (value or '').strip()
    if not text:
        return None
    if user_model.objects.filter(username=text).exists():
        return text
    if '@' not in text:
        return None
    matches = list(
        user_model.objects.filter(username__iexact=text)
        .values_list('username', flat=True)[:2])
    return matches[0] if len(matches) == 1 else None
