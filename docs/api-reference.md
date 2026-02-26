# API Reference

Interactive API documentation is served directly by NAAS at runtime.

## Swagger UI

Browse and test all endpoints at [`/apidoc`](https://localhost:8443/apidoc).

Basic Auth is wired into the "Try it out" button — enter your device credentials and execute requests directly from the browser.

## OpenAPI Spec

The machine-readable spec is available at [`/apidoc/openapi.json`](https://localhost:8443/apidoc/openapi.json).

The spec is also committed to the repository at [`docs/swagger/openapi.json`](swagger/openapi.json) and kept in sync with the code by CI.
