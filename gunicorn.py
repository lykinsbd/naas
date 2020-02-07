from naas.library.selfsigned import generate_selfsigned_cert
from os import environ


# Setup basic attributes of our web-server
bind = f"0.0.0.0:443"
chdir = "/app"
workers = 8
worker_class = "gthread"
threads = 32
timeout = 300

# Configure access logging
accesslog = "-"  # "-" means log to stdout
# Format: date proc_name remote_addr X-Forwarded-For X-Request-ID method/path status_code response_length user_agent
access_log_format = '%(t)s %(p)s %(h)s %({X-Forwarded-For}i)s %({X-Request-ID}i)s "%(r)s" %(s)s %(b)s "%(a)s"'

# Gather the app environment and assign logging_level based on that
if "dev" in environ.get("APP_ENVIRONMENT", "dev"):
    logging_level = environ.get("LOG_LEVEL", "DEBUG")
else:
    logging_level = environ.get("LOG_LEVEL", "INFO")

# Push our log level up to an environment variable.
environ["LOG_LEVEL"] = logging_level

# Configure all other (error) logging
logconfig_dict = {
    "version": 1,
    "formatters": {
        "stderr_format": {
            "format": "[%(asctime)s] [%(process)d] [%(levelname)s] %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S %z",
        }
    },
    "handlers": {
        "NAAS_handler": {"class": "logging.StreamHandler", "level": logging_level, "formatter": "stderr_format"}
    },
    "loggers": {"NAAS": {"level": logging_level, "handlers": ["NAAS_handler"]}},
    "disable_existing_loggers": False,
    "root": {"level": logging_level, "handlers": ["NAAS_handler"]},  # Adding to handle bug in Gunicorn 20.0.4
}

# Try and find TLS cert/key/bundle in Environment variables
NAAS_CERT = environ.get("NAAS_CERT", None)
NAAS_KEY = environ.get("NAAS_KEY", None)
NAAS_CA_BUNDLE = environ.get("NAAS_CA_BUNDLE", None)

CERT_FILE = "/app/cert.pem"
KEY_FILE = "/app/key.pem"
CA_BUNDLE_FILE = "/app/ca_bundle.pem"

# If we can't find a cert or key lets make something up, otherwise print the cert into the files for Gunicorn
if NAAS_CERT is None or NAAS_KEY is None:
    cert, key, = generate_selfsigned_cert("naas.local")
    with open(CERT_FILE, "w") as c:
        c.write(cert.decode())
    with open(KEY_FILE, "w") as k:
        k.write(key.decode())
else:
    with open(CERT_FILE, "w") as c:
        c.write(NAAS_CERT + "\n")
    with open(KEY_FILE, "w") as k:
        k.write(NAAS_KEY + "\n")

if NAAS_CA_BUNDLE is None:
    CA_BUNDLE_FILE = None
else:
    with open(CA_BUNDLE_FILE, "w") as bundle:
        bundle.write(NAAS_CA_BUNDLE + "\n")

# Crypto configuration
keyfile = KEY_FILE
certfile = CERT_FILE
if CA_BUNDLE_FILE is not None:
    ca_certs = CA_BUNDLE_FILE
ssl_version = 5
ciphers = "HIGH:!aNULL:!eNULL:!EXPORT:!DES:!RC4:!3DES:!MD5:!PSK"
