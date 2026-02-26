Fix job.get_id() → job.id (rq removed get_id() in a recent release); was causing 500 errors on all job submissions.
