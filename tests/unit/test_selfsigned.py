"""Unit tests for selfsigned certificate generation."""

from ipaddress import IPv4Address

from cryptography import x509
from cryptography.hazmat.backends import default_backend

from naas.library.selfsigned import generate_selfsigned_cert


class TestGenerateSelfsignedCert:
    """Tests for generate_selfsigned_cert function."""

    def test_basic_cert_generation(self):
        """Test basic certificate generation with hostname only."""
        cert_pem, key_pem = generate_selfsigned_cert("test.example.com")

        assert cert_pem.startswith(b"-----BEGIN CERTIFICATE-----")
        assert b"BEGIN RSA PRIVATE KEY" in key_pem  # pragma: allowlist secret

        # Verify cert can be loaded
        cert = x509.load_pem_x509_certificate(cert_pem, default_backend())
        assert cert.subject.get_attributes_for_oid(x509.oid.NameOID.COMMON_NAME)[0].value == "test.example.com"

    def test_cert_with_public_ip(self):
        """Test certificate generation with public IP."""
        public_ip = IPv4Address("203.0.113.1")
        cert_pem, key_pem = generate_selfsigned_cert("test.example.com", public_ip=public_ip)

        cert = x509.load_pem_x509_certificate(cert_pem, default_backend())
        san_ext = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName)

        # Check that IP is in SAN
        ip_addresses = [str(ip.value) for ip in san_ext.value if isinstance(ip, x509.IPAddress)]
        assert "203.0.113.1" in ip_addresses

    def test_cert_with_private_ip(self):
        """Test certificate generation with private IP."""
        private_ip = IPv4Address("192.168.1.1")
        cert_pem, key_pem = generate_selfsigned_cert("test.example.com", private_ip=private_ip)

        cert = x509.load_pem_x509_certificate(cert_pem, default_backend())
        san_ext = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName)

        # Check that IP is in SAN
        ip_addresses = [str(ip.value) for ip in san_ext.value if isinstance(ip, x509.IPAddress)]
        assert "192.168.1.1" in ip_addresses

    def test_cert_with_both_ips(self):
        """Test certificate generation with both public and private IPs."""
        public_ip = IPv4Address("203.0.113.1")
        private_ip = IPv4Address("192.168.1.1")
        cert_pem, key_pem = generate_selfsigned_cert("test.example.com", public_ip=public_ip, private_ip=private_ip)

        cert = x509.load_pem_x509_certificate(cert_pem, default_backend())
        san_ext = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName)

        # Check that both IPs are in SAN
        ip_addresses = [str(ip.value) for ip in san_ext.value if isinstance(ip, x509.IPAddress)]
        assert "203.0.113.1" in ip_addresses
        assert "192.168.1.1" in ip_addresses
