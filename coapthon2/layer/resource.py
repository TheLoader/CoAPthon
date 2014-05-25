from coapthon2 import defines
from coapthon2.resources.resource import Resource
from coapthon2.utils import Tree

__author__ = 'giacomo'


class ResourceLayer(object):
    def __init__(self, parent):
        self._parent = parent

    def create_resource(self, path, request, response):
        paths = path.split("/")
        lp = []
        old = self._parent.root
        for p in paths:
            res = old.find(p)
            lp.append(p)
            if res is None:
                if old.value.allow_children:
                    # If-Match
                    if request.has_if_match:
                        if str(old.value.etag) not in request.if_match:
                            return self._parent.send_error(request, response, 'PRECONDITION_FAILED')
                    method = getattr(old.value, "render_POST", None)
                    if hasattr(method, '__call__'):
                        new_payload = method(payload=request.payload, query=request.query)
                        if isinstance(new_payload, dict):
                            etag = new_payload.get("ETag")
                            location_path = new_payload.get("Location-Path")
                            location_query = new_payload.get("Location-Query")
                            new_payload = new_payload.get("Payload")
                        else:
                            etag = None
                            location_path = None
                            location_query = None
                        if new_payload is not None and new_payload != -1:
                            method = getattr(old.value, "new_resource", None)
                            resource = method()
                            resource.payload = new_payload
                            resource.path = p
                            if etag is not None:
                                response.etag = etag
                            if location_path is not None:
                                lppaths = location_path.split("/")
                                dad = self.create_subtree(lppaths[:-1])
                                resource.path = lppaths[-1]
                                dad.add_child(resource)
                                response.location_path = location_path
                            else:
                                old.add_child(resource)
                                response.location_path = lp

                            if location_query is not None:
                                response.location_query = location_query

                            response.code = defines.responses['CREATED']

                            response.payload = None
                            # Token
                            response.token = request.token
                            #TODO Blockwise
                            #Reliability
                            response = self._parent.reliability_response(request, response)
                            #Matcher
                            response = self._parent.matcher_response(response)
                            return response
                        elif new_payload == -1:
                            return self._parent.send_error(request, response, 'METHOD_NOT_ALLOWED')
                        else:
                            return self._parent.send_error(request, response, 'INTERNAL_SERVER_ERROR')
                    else:
                        return self._parent.send_error(request, response, 'METHOD_NOT_ALLOWED')
                else:
                    return self._parent.send_error(request, response, 'METHOD_NOT_ALLOWED')
            else:
                old = res

    def update_resource(self, path, request, response, resource, render_method="render_PUT"):
        path = path.strip("/")
        node = self._parent.root.find_complete(path)
        # If-Match
        if request.has_if_match:
            if None not in request.if_match and str(resource.etag) not in request.if_match:
                return self._parent.send_error(request, response, 'PRECONDITION_FAILED')
        # If-None-Match
        if request.has_if_none_match:
            return self._parent.send_error(request, response, 'PRECONDITION_FAILED')
        method = getattr(resource, render_method, None)
        if hasattr(method, '__call__'):
            new_payload = method(payload=request.payload, query=request.query)
            if isinstance(new_payload, dict):
                etag = new_payload.get("ETag")
                location_path = new_payload.get("Location-Path")
                location_query = new_payload.get("Location-Query")
                new_payload = new_payload.get("Payload")
            else:
                etag = None
                location_path = None
                location_query = None
            if new_payload is not None and new_payload != -1:
                if etag is not None:
                    response.etag = (etag + 1)
                if render_method == "render_PUT":
                    response.code = defines.responses['CHANGED']
                    node.value.payload = new_payload
                    # Observe
                    self._parent.notify(node)
                else:
                    response.code = defines.responses['CREATED']
                    method = getattr(resource, "new_resource", None)
                    if location_path is not None:
                        del response.etag
                        resource = method()
                        lp_paths = location_path.split("/")
                        resource.payload = new_payload
                        dad = self.create_subtree(lp_paths[:-1])
                        resource.path = lp_paths[-1]
                        dad.add_child(resource)
                        response.location_path = lp_paths
                        # Observe
                        self._parent.notify(self._parent.root.find_complete(location_path))
                    else:
                        p = path.split("/")
                        old_observe_count = node.value.observe_count
                        node.value = method()
                        node.value.path = p[-1]
                        node.value.payload = new_payload
                        node.value.observe_count = old_observe_count
                        response.etag = old_observe_count
                        response.location_path = p
                        # Observe
                        self._parent.notify(node)

                    if location_query is not None and len(location_query) > 0:
                        response.location_query = location_query

                response.payload = None
                # Token
                response.token = request.token

                #TODO Blockwise
                #Reliability
                response = self._parent.reliability_response(request, response)
                #Matcher
                response = self._parent.matcher_response(response)
                return response
            elif new_payload == -1:
                return self._parent.send_error(request, response, 'METHOD_NOT_ALLOWED')
            else:
                return self._parent.send_error(request, response, 'INTERNAL_SERVER_ERROR')
        else:
            return self._parent.send_error(request, response, 'METHOD_NOT_ALLOWED')

    def delete_resource(self, request, response, node):
        assert isinstance(node, Tree)
        method = getattr(node.value, 'render_DELETE', None)
        if hasattr(method, '__call__'):
            ret = method(query=request.query)
            if ret != -1:
                parent = node.parent
                assert isinstance(parent, Tree)
                # Observe
                self._parent.notify(parent)
                self._parent.remove_observers(node)

                parent.del_child(node)
                response.code = defines.responses['DELETED']
                response.payload = None
                # Token
                response.token = request.token

                #TODO Blockwise
                #Reliability
                response = self._parent.reliability_response(request, response)
                #Matcher
                response = self._parent.matcher_response(response)
                return response
            elif ret == -1:
                return self._parent.send_error(request, response, 'METHOD_NOT_ALLOWED')
            else:
                return self._parent.send_error(request, response, 'INTERNAL_SERVER_ERROR')
        else:
            return self._parent.send_error(request, response, 'METHOD_NOT_ALLOWED')

    def get_resource(self, request, response, resource):
        method = getattr(resource, 'render_GET', None)
        if hasattr(method, '__call__'):

            resource.required_content_type = None

            if request.content_type is not None:
                resource.required_content_type = request.content_type
                response.content_type = resource.required_content_type

            # Render_GET
            ret = method(query=request.query)
            if isinstance(ret, dict):
                etag = ret["ETag"]
                ret = ret["Payload"]
            else:
                etag = None
            if ret != -1:
                # handle ETAG
                if str(etag) in request.etag:
                    response.code = defines.responses['VALID']
                else:
                    response.code = defines.responses['CONTENT']
                    response.payload = ret
                response.token = request.token
                if etag is not None:
                    response.etag = etag

                # Observe
                if request.observe and resource.observable:
                    response, resource = self._parent.add_observing(resource, response)
                #TODO Blockwise
                response = self._parent.reliability_response(request, response)
                response = self._parent.matcher_response(response)
            else:
                response = self._parent.send_error(request, response, 'METHOD_NOT_ALLOWED')
        else:
            response = self._parent.send_error(request, response, 'METHOD_NOT_ALLOWED')
        return response

    def discover(self, request, response):
        node = self._parent.root
        assert isinstance(node, Tree)
        response.code = defines.responses['CONTENT']
        response.payload = node.corelinkformat()
        response.content_type = defines.inv_content_types["application/link-format"]
        response.token = request.token
        #TODO Blockwise
        response = self._parent.reliability_response(request, response)
        response = self._parent.matcher_response(response)
        return response

    def create_subtree(self, paths):
        node = self._parent.root
        assert isinstance(paths, list)
        assert isinstance(node, Tree)
        last = None
        while True:
            last, failed_resource = node.find_complete_last(paths)
            if failed_resource is None:
                break
            resource = Resource(name="subtree", visible=True, observable=False, allow_children=True)
            method = getattr(resource, "new_resource", None)
            resource = method()
            resource.payload = None
            resource.path = failed_resource
            last.add_child(resource)
        return last