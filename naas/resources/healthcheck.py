# API Resources

from flask_restful import Resource

from naas import __version__


class HealthCheck(Resource):
    def get(self):
        return {"status": "OK", "app": "naas", "version": __version__}
