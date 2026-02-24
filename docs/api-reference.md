# API Reference

Interactive API documentation powered by Swagger UI.

<div id="swagger-ui"></div>

<link rel="stylesheet" type="text/css" href="../swagger-ui.css" />
<script src="../swagger-ui-bundle.js"></script>
<script src="../swagger-ui-standalone-preset.js"></script>
<script>
window.onload = function() {
  const ui = SwaggerUIBundle({
    url: "../naas.yaml",
    dom_id: '#swagger-ui',
    deepLinking: true,
    presets: [
      SwaggerUIBundle.presets.apis,
      SwaggerUIStandalonePreset
    ],
    plugins: [
      SwaggerUIBundle.plugins.DownloadUrl
    ],
    layout: "StandaloneLayout"
  })
  window.ui = ui
}
</script>
