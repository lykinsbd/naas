# API Resources

from flask import current_app, request
from flask_restful import Resource
from rq.job import Job
from rq.registry import FailedJobRegistry, FinishedJobRegistry, StartedJobRegistry

from naas import __base_response__
from naas.library.validation import Validate


class ListJobs(Resource):
    @staticmethod
    def get():
        """
        List jobs with pagination and filtering.
        Query parameters:
        - page: Page number (default: 1)
        - per_page: Results per page (default: 20, max: 100)
        - status: Filter by status (finished, failed, started, queued)
        :return: Dict with jobs list and pagination info
        """
        # Validate auth
        v = Validate()
        v.has_auth()

        # Parse query parameters
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 20, type=int)
        status_filter = request.args.get("status", type=str)

        # Validate parameters
        if page < 1:
            page = 1
        if per_page < 1 or per_page > 100:
            per_page = 20

        # Get queue and registries
        q = current_app.config["q"]
        redis_conn = current_app.config["redis"]

        # Collect job IDs based on status filter
        job_ids = []
        total_count = 0

        if status_filter == "finished":
            registry = FinishedJobRegistry(queue=q)
            total_count = registry.count
            start = (page - 1) * per_page
            end = start + per_page - 1
            job_ids = registry.get_job_ids(start=start, end=end)
        elif status_filter == "failed":
            registry = FailedJobRegistry(queue=q)
            total_count = registry.count
            start = (page - 1) * per_page
            end = start + per_page - 1
            job_ids = registry.get_job_ids(start=start, end=end)
        elif status_filter == "started":
            registry = StartedJobRegistry(queue=q)
            total_count = registry.count
            start = (page - 1) * per_page
            end = start + per_page - 1
            job_ids = registry.get_job_ids(start=start, end=end)
        elif status_filter == "queued":
            total_count = len(q)
            start = (page - 1) * per_page
            end = start + per_page
            job_ids = q.get_job_ids(offset=start, length=per_page)
        else:
            # No filter - get all jobs from all registries
            finished_reg = FinishedJobRegistry(queue=q)
            failed_reg = FailedJobRegistry(queue=q)
            started_reg = StartedJobRegistry(queue=q)

            all_job_ids = (
                finished_reg.get_job_ids() + failed_reg.get_job_ids() + started_reg.get_job_ids() + q.get_job_ids()
            )
            total_count = len(all_job_ids)
            start = (page - 1) * per_page
            end = start + per_page
            job_ids = all_job_ids[start:end]

        # Fetch job details
        jobs = []
        for job_id in job_ids:
            job = Job.fetch(job_id, connection=redis_conn)
            if job:
                jobs.append(
                    {
                        "job_id": job.id,
                        "status": job.get_status(),
                        "created_at": job.created_at.isoformat() if job.created_at else None,
                        "ended_at": job.ended_at.isoformat() if job.ended_at else None,
                    }
                )

        # Calculate pagination
        total_pages = (total_count + per_page - 1) // per_page if total_count > 0 else 0

        # Build response
        r_dict = {
            "jobs": jobs,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total_count,
                "pages": total_pages,
            },
        }
        r_dict.update(__base_response__)

        return r_dict
