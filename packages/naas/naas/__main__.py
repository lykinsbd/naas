#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

import ssl

from naas.app import app
from naas.config import CERT_BUNDLE_FILE, CERT_KEY_FILE


def main():
    """
    Main yo!
    :return:
    """

    # Setup SSL stuffz
    context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
    context.load_cert_chain(CERT_BUNDLE_FILE, CERT_KEY_FILE)

    # Start the webserver
    app.run(debug=True, host="0.0.0.0", port=5000, ssl_context=context, threaded=True)


if __name__ == "__main__":
    main()
