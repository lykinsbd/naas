{{/*
Common labels applied to all resources.
*/}}
{{- define "naas.labels" -}}
app.kubernetes.io/name: naas
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
{{- end }}

{{/*
Container image with tag defaulting to appVersion.
*/}}
{{- define "naas.image" -}}
{{ .Values.image.repository }}:{{ .Values.image.tag | default .Chart.AppVersion }}
{{- end }}

{{/*
Secret name — use existing or generated.
*/}}
{{- define "naas.secretName" -}}
{{- if .Values.secrets.existingSecret -}}
{{ .Values.secrets.existingSecret }}
{{- else -}}
naas-secret
{{- end -}}
{{- end }}

{{/*
Redis host — bundled service name or external.
*/}}
{{- define "naas.redisHost" -}}
{{- if .Values.redis.enabled -}}
redis
{{- else -}}
{{ .Values.redis.external.host }}
{{- end -}}
{{- end }}

{{/*
Redis port.
*/}}
{{- define "naas.redisPort" -}}
{{- if .Values.redis.enabled -}}
{{ .Values.redis.port | quote }}
{{- else -}}
{{ .Values.redis.external.port | quote }}
{{- end -}}
{{- end }}
