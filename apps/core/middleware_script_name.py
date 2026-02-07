"""
Middleware to handle X-Script-Name header for subpath deployments.
This ensures Django correctly handles URLs when deployed under a path prefix like /kp-cfms.
"""


class ScriptNameMiddleware:
    """
    Set SCRIPT_NAME from X-Script-Name header sent by Apache/nginx proxy.
    This allows Django to generate correct URLs when app is deployed under a subpath.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Get X-Script-Name header from proxy (set by Apache RequestHeader)
        script_name = request.META.get('HTTP_X_SCRIPT_NAME', '')
        
        if script_name:
            # Set SCRIPT_NAME for this request
            request.META['SCRIPT_NAME'] = script_name
            
            # Remove script name from path_info if it's present
            # (some proxy configs pass it in the path)
            path_info = request.META.get('PATH_INFO', '')
            if path_info.startswith(script_name):
                request.META['PATH_INFO'] = path_info[len(script_name):]
                # Ensure PATH_INFO starts with /
                if not request.META['PATH_INFO'].startswith('/'):
                    request.META['PATH_INFO'] = '/' + request.META['PATH_INFO']
        
        response = self.get_response(request)
        return response
