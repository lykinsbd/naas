from naas.library.selfsigned import generate_selfsigned_cert
from os import environ


bind = "0.0.0.0:5000"
chdir = "/app"

workers = 40
worker_class = "sync"
timeout = 300

accesslog = "-"
access_log_format = '%(t)s %(p)s %(h)s %({X-Forwarded-For}i)s %(l)s "%(r)s" %(s)s %(b)s "%(f)s"'

# Try and find TLS file names
KEY_FILE = environ.get("KEY_FILE", None)
CERT_FILE = environ.get("CERT_FILE", None)
BUNDLE_FILE = environ.get("BUNDLE_FILE", None)

# If we can't find a cert/key file, lets make something up
if KEY_FILE is None and CERT_FILE is None:
    KEY_FILE = "/app/key.pem"
    CERT_FILE = "/app/cert.pem"

    cert, key, = generate_selfsigned_cert("naas.local")
    with open(CERT_FILE, "w") as c:
        c.write(cert.decode())

    with open(KEY_FILE, "w") as k:
        k.write(key.decode())

# Crypto configuration
keyfile = KEY_FILE
certfile = CERT_FILE
ca_certs = BUNDLE_FILE
ssl_version = 5
ciphers = "HIGH:!aNULL:!eNULL:!EXPORT:!DES:!RC4:!3DES:!MD5:!PSK"
