import re
from django.contrib.auth.forms import AuthenticationForm


class CNICAuthenticationForm(AuthenticationForm):
    """Authentication form that normalizes CNIC input.

    Strips non-digit characters from the `username` field so users can
    enter CNIC with or without dashes/spaces.
    """

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if username:
            # Remove any non-digit characters (dashes, spaces) to match database
            normalized = re.sub(r"\D", "", username)
            return normalized
        return username
