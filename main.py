import getpass
import json
import os
import subprocess
import sys
import tempfile
import urllib.parse

import requests
from bs4 import BeautifulSoup

CA_CERTS_LOCATIONS = '/etc/ssl/certs/ca-certificates.crt'  # TODO hardcoded for debian
DEFAULT_BASE_URL = 'https://oauth-openshift.apps.ocp.dev.alticelabs.com'


def extract_input_value(html, input_name, response_content=None):
    """
    Extract the value of an input element from HTML.

    Args:
        html: BeautifulSoup object with parsed HTML
        input_name: name attribute of the input element to find
        response_content: optional response text for debugging

    Returns:
        The value of the input element

    Raises:
        SystemExit: if the input element is not found
    """
    element = html.find('input', {'name': input_name})
    if not element:
        print(f'Login failed, no {input_name} found in response', file=sys.stderr)
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(response_content)
            print(f'Full response saved to {tmp.name} for debugging', file=sys.stderr)
        sys.exit(1)
    return element['value']

def _load_build_config():
    """
    Load optional build-time configuration (base URL and username).

    Supports both running from source and from a PyInstaller onefile binary.
    Returns a dict with optional keys: 'base_url', 'username'.
    """
    # Determine possible paths for a bundled resource created at build time
    candidate_paths = []
    try:
        # PyInstaller onefile extracts to a temp dir referenced by _MEIPASS
        meipass = getattr(sys, '_MEIPASS', None)
        if meipass:
            candidate_paths.append(os.path.join(meipass, 'config.json'))
    except Exception:
        pass

    # Also support running from project root where config.json might live
    candidate_paths.append(os.path.join(os.path.dirname(__file__), 'config.json'))

    for path in candidate_paths:
        try:
            if os.path.isfile(path):
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        return data
        except Exception:
            # Ignore malformed or unreadable config and continue
            continue
    return {}


def main():
    os.environ['REQUESTS_CA_BUNDLE'] = CA_CERTS_LOCATIONS

    build_cfg = _load_build_config()

    # Resolve base URL and username with the following precedence:
    # 1) Environment variables
    # 2) Build-time config.json (passed as build arguments)
    # 3) Hardcoded defaults (base URL only)
    OPENSHIFT_BASE_URL = os.getenv(
        'OPENSHIFT_BASE_URL',
        build_cfg.get('base_url', DEFAULT_BASE_URL)
    )
    USERNAME = os.getenv('OPENSHIFT_USERNAME', build_cfg.get('username', ''))

    if not USERNAME:
        # Fallback to interactive prompt if not provided via build args or env
        USERNAME = input('Username: ')

    encoded_base_url = urllib.parse.quote_plus(OPENSHIFT_BASE_URL)

    # Get LDAP login page
    try:
        first_response = requests.get(
            f'{OPENSHIFT_BASE_URL}/login/LDAPS', # TODO support other authentication methods
            params={
                'then': f'/oauth/authorize?client_id=openshift-browser-client&idp=LDAPS&redirect_uri={encoded_base_url}%2Foauth%2Ftoken%2Fdisplay&response_type=code',
            }
        )
    except requests.exceptions.ConnectionError as ex:
        if "Name or service not known" in str(ex):
            print("Could not resolve OpenShift hostname. Is your VPN on?", file=sys.stderr)
            sys.exit(1)
        elif isinstance(ex, requests.exceptions.SSLError) and "Hostname mismatch" in str(ex):
            print("Hostname mismatch on certificate vs url. Did you connect to your company's firewall?", file=sys.stderr)
            sys.exit(1)
        raise

    # Extract CSRF token and redirect URL from login form
    html = BeautifulSoup(first_response.text, 'html.parser')

    login_form = html.find(id='co-login-form')
    if not login_form:
        print('Login failed, no login form found in response', file=sys.stderr)
        sys.exit(1)

    csrf_token = extract_input_value(login_form, 'csrf', first_response.text)
    then = extract_input_value(login_form, 'then', first_response.text)

    # Post login data
    while True:
        read_from_stdin = False
        if sys.stdin.isatty():
            password = getpass.getpass("Password: ")
        else:
            read_from_stdin = True
            password = sys.stdin.read().strip()

        login_response = requests.post(
            f'{OPENSHIFT_BASE_URL}/login/LDAPS',
            cookies=first_response.cookies,
            data={
                'then': then,
                'csrf': csrf_token,
                'username': USERNAME,
                'password': password
            },
            allow_redirects=True,
        )

        if login_response.status_code != 200:
            print('Login request failed', file=sys.stderr)
            sys.exit(1)

        if "Invalid login or password. Please try again." in login_response.text:
            print('Invalid password', file=sys.stderr)

            if read_from_stdin:
                # If we read the password from stdin, we can't prompt again, so we should exit
                sys.exit(1)
        else:
            break

    # Extract code and CSRF token from login post response (redirected)
    html = BeautifulSoup(login_response.text, 'html.parser')
    code = extract_input_value(html, 'code', login_response.text)
    csrf = extract_input_value(html, 'csrf', login_response.text)

    # Make request to display oc command
    token_display_response = requests.post(
        f'{OPENSHIFT_BASE_URL}/oauth/token/display',
        cookies=first_response.cookies,
        data={
            "code": code,
            "csrf": csrf,
        },
        allow_redirects=True,
    )

    if token_display_response.status_code != 200:
        print('Token display request failed', file=sys.stderr)
        sys.exit(1)

    # Extract oc command from response
    html = BeautifulSoup(token_display_response.text, 'html.parser')
    oc_command = html.find('pre').text
    #print('Executing oc command to log in: ', oc_command)

    # Execute oc command
    run = subprocess.run(
        oc_command.split(),
        capture_output=True,
    )
    print(run.stdout.decode('utf-8'))
    if run.returncode != 0:
        print(run.stderr.decode('utf-8'), file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
