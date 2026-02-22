# Copyright 2019 Simon Davy, Brett Lykins
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
# Original Source: https://gist.github.com/bloodearnest/9017111a313777b9cce5
# Edited Source: https://gist.github.com/lykinsbd/588462f8f37b846c605c8dee477245c5

from datetime import datetime, timedelta
from ipaddress import IPv4Address, IPv4Network, IPv6Address, IPv6Network
from typing import TYPE_CHECKING

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

if TYPE_CHECKING:
    pass


def generate_selfsigned_cert(
    hostname: str,
    public_ip: "IPv4Address | IPv4Network | IPv6Address | IPv6Network | None" = None,
    private_ip: "IPv4Address | IPv4Network | IPv6Address | IPv6Network | None" = None,
) -> "tuple[bytes, bytes]":
    """
    Generate a self-signed X509 certificate.
    :param hostname:  Must provide a hostname
    :param public_ip:  Can optionally provide a public IP
    :param private_ip:  Can optionally provide a private IP
    :return: A tuple of the certificate PEM and the key PEM
    """

    # Generate our key
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048, backend=default_backend())

    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, hostname)])

    # Setup our alt names.
    alt_names_list = [
        # Best practice seem to be to include the hostname in the SAN, which *SHOULD* mean COMMON_NAME is ignored.
        x509.DNSName(hostname)
    ]

    # Allow addressing by IP, for when you don't have real DNS (common in most testing scenarios)
    if public_ip is not None:
        # openssl wants DNSnames for ips...
        alt_names_list.append(x509.DNSName(public_ip))
        # ... whereas golang's crypto/tls is stricter, and needs IPAddresses
        alt_names_list.append(x509.IPAddress(public_ip))
    if private_ip is not None:
        # openssl wants DNSnames for ips...
        alt_names_list.append(x509.DNSName(private_ip))
        # ... whereas golang's crypto/tls is stricter, and needs IPAddresses
        alt_names_list.append(x509.IPAddress(private_ip))

    alt_names = x509.SubjectAlternativeName(alt_names_list)

    # path_len=0 means this cert can only sign itself, not other certs.
    basic_contraints = x509.BasicConstraints(ca=True, path_length=0)

    now = datetime.utcnow()
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(1000)
        .not_valid_before(now)
        .not_valid_after(now + timedelta(days=10 * 365))
        .add_extension(basic_contraints, False)
        .add_extension(alt_names, False)
        .sign(key, hashes.SHA256(), default_backend())
    )

    cert_pem = cert.public_bytes(encoding=serialization.Encoding.PEM)

    key_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )

    return cert_pem, key_pem
