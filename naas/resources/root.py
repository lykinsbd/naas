# API Resources

from flask_restful import Resource
from naas import __version__


class HelloWorld(Resource):
    def get(self):
        return {"hello": "world", "app": "naas", "version": __version__}
