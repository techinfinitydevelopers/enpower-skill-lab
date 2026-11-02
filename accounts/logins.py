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


def sync_login_email(user, new_email, is_active=None):
    """Move an account's login to a new address when its profile moves.

    The edit forms for School Admins, Thinking Coaches and Coordinators write
    the new address onto the profile row and stopped there. The login lives on
    the User, so it stayed at the old address: the list on screen showed one
    address, the person signed in with it, and got "Invalid credentials" --
    the same words a wrong password gets, so nothing on either side said what
    had happened.

    That is how BKG Global School's principal spent two months unable to get
    in. Her profile read principal@bkgglobalschool.com; there was no account
    by that name at all, because the login was still the address she had been
    onboarded with.

    Only called for roles whose login *is* their address. Students sign in
    with a registration ID and Parents with a generated username, so changing
    their email must leave the login alone.

    Returns True when something moved. Raises ValueError if the address
    already belongs to somebody else, rather than letting the save fail on a
    unique constraint with a message nobody can act on.
    """
    if user is None:
        return False

    wanted = normalise_login(new_email)
    if not wanted or '@' not in wanted:
        return False

    moved = False
    if normalise_login(user.username) != wanted:
        from django.contrib.auth import get_user_model

        clash = (get_user_model().objects
                 .filter(username__iexact=wanted)
                 .exclude(pk=user.pk).first())
        if clash is not None:
            raise ValueError(
                f'{wanted} is already the login for another account '
                f'({clash.get_full_name() or clash.username}, '
                f'{clash.role}). Free that address first, or use a '
                f'different one.')
        user.username = wanted
        moved = True

    if normalise_login(user.email) != wanted:
        user.email = wanted
        moved = True

    # A profile switched off while its login stays on is not switched off:
    # sign-in reads User.is_active and has never looked at the profile row.
    if is_active is not None and user.is_active != bool(is_active):
        user.is_active = bool(is_active)
        moved = True

    if moved:
        user.save(update_fields=['username', 'email', 'is_active'])
    return moved
