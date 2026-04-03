# API Resource for listing active routing contexts

from flask import current_app
from flask_restful import Resource
from rq import Queue, Worker
from spectree import Response

from naas.config import NAAS_CONTEXTS
from naas.models import ContextInfo, ContextsResponse
from naas.spec import spec


class Contexts(Resource):
    @spec.validate(resp=Response(HTTP_200=ContextsResponse))
    def get(self):
        """
        List all configured contexts with active worker counts and queue depths.

        :return: ContextsResponse with per-context status
        """
        redis = current_app.config["redis"]
        all_workers = Worker.all(connection=redis)

        contexts = []
        for context_name in sorted(NAAS_CONTEXTS):
            queue_name = f"naas-{context_name}"
            q = Queue(queue_name, connection=redis)
            worker_count = sum(1 for w in all_workers if queue_name in w.queue_names())
            contexts.append(
                ContextInfo(
                    name=context_name,
                    workers=worker_count,
                    queue_depth=len(q),
                ).model_dump()
            )

        return ContextsResponse(contexts=contexts).model_dump(), 200
