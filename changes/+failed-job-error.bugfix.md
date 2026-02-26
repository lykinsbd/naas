Failed jobs now include error detail in the API response. Previously `GET /v1/send_command/{job_id}` returned no error information when a job had status `failed`.
