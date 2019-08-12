from naas.library.selfsigned import generate_selfsigned_cert
from os import environ


# Setup basic attributes of our web-server
bind = f"0.0.0.0:{environ.get('NAAS_LOCAL_PORT', '443')}"
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
}

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
