# API Resources

from flask import current_app, request
from flask_restful import Resource
from rq.job import Job
from rq.registry import FailedJobRegistry, FinishedJobRegistry, StartedJobRegistry

from naas import __base_response__
from naas.library.validation import Validate
from naas.models import ListJobsQuery
from naas.spec import spec


class ListJobs(Resource):
    @staticmethod
    @spec.validate(query=ListJobsQuery)
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

        query: ListJobsQuery = request.context.query

        # Get queue and registries
        q = current_app.config["q"]
        redis_conn = current_app.config["redis"]

        # Collect job IDs based on status filter
        job_ids = []
        total_count = 0

        if query.status == "finished":
            registry = FinishedJobRegistry(queue=q)
            total_count = registry.count
            start = (query.page - 1) * query.per_page
            end = start + query.per_page - 1
            job_ids = registry.get_job_ids(start=start, end=end)
        elif query.status == "failed":
            registry = FailedJobRegistry(queue=q)
            total_count = registry.count
            start = (query.page - 1) * query.per_page
            end = start + query.per_page - 1
            job_ids = registry.get_job_ids(start=start, end=end)
        elif query.status == "started":
            registry = StartedJobRegistry(queue=q)
            total_count = registry.count
            start = (query.page - 1) * query.per_page
            end = start + query.per_page - 1
            job_ids = registry.get_job_ids(start=start, end=end)
        elif query.status == "queued":
            total_count = len(q)
            start = (query.page - 1) * query.per_page
            job_ids = q.get_job_ids(offset=start, length=query.per_page)
        else:
            # No filter - paginate across all registries without fetching all IDs
            finished_reg = FinishedJobRegistry(queue=q)
            failed_reg = FailedJobRegistry(queue=q)
            started_reg = StartedJobRegistry(queue=q)

            # (registry_or_queue, count, is_queue)
            sources: list[tuple] = [
                (finished_reg, finished_reg.count, False),
                (failed_reg, failed_reg.count, False),
                (started_reg, started_reg.count, False),
                (q, len(q), True),
            ]
            total_count = sum(c for _, c, _ in sources)

            # Walk sources in order, collecting IDs for the requested page
            start = (query.page - 1) * query.per_page
            remaining_skip = start
            remaining_take = query.per_page
            for source, count, is_queue in sources:
                if remaining_take == 0:
                    break
                if remaining_skip >= count:
                    remaining_skip -= count
                    continue
                reg_start = remaining_skip
                if is_queue:
                    chunk = source.get_job_ids(offset=reg_start, length=remaining_take)
                else:
                    chunk = source.get_job_ids(start=reg_start, end=reg_start + remaining_take - 1)
                job_ids.extend(chunk)
                remaining_take -= len(chunk)
                remaining_skip = 0

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
        total_pages = (total_count + query.per_page - 1) // query.per_page if total_count > 0 else 0

        # Build response
        r_dict = {
            "jobs": jobs,
            "pagination": {
                "page": query.page,
                "per_page": query.per_page,
                "total": total_count,
                "pages": total_pages,
            },
        }
        r_dict.update(__base_response__)

        return r_dict
