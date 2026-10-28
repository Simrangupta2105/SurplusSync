"""
Core views for SURPLUSSYNC Django project.
"""

from django.conf import settings
from django.http import JsonResponse
from django.db import connection
from django.utils import timezone


def health_check(request):
    """
    Health check endpoint for load balancers and container orchestration.
    
    Checks:
    - Database connectivity
    - Basic app functionality
    
    Returns 200 if healthy, 503 if unhealthy.
    """
    status = 200
    checks = {}
    
    # Check database
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        checks['database'] = 'ok'
    except Exception as e:
        checks['database'] = f'error: {str(e)}'
        status = 503
    
    # Check ML service if configured
    if hasattr(settings, 'ML_SERVICE_URL'):
        import urllib.request
        import urllib.error
        import socket
        
        try:
            url = f"{settings.ML_SERVICE_URL.rstrip('/')}/health"
            req = urllib.request.Request(url)
            req.add_header('X-Service-Token', getattr(settings, 'ML_SERVICE_TOKEN', 'surplussync-service-token-dev'))
            with urllib.request.urlopen(req, timeout=3) as response:
                ml_status = response.getcode()
                checks['ml_service'] = f'ok ({ml_status})' if ml_status == 200 else f'error ({ml_status})'
        except (urllib.error.URLError, socket.timeout, socket.gaierror):
            checks['ml_service'] = 'unreachable'
        except Exception as e:
            checks['ml_service'] = f'error: {str(e)}'
    
    # Check cache if configured
    if hasattr(settings, 'CACHES'):
        from django.core.cache import cache
        try:
            cache.set('health_check', True, timeout=5)
            cached = cache.get('health_check')
            checks['cache'] = 'ok' if cached else 'error'
        except Exception as e:
            checks['cache'] = f'error: {str(e)}'
    
    # Determine overall status
    if status == 200:
        overall_status = 'healthy'
    else:
        overall_status = 'unhealthy'
        status = 503
    
    return JsonResponse({
        'status': overall_status,
        'timestamp': timezone.now().isoformat(),
        'checks': checks,
    }, status=status)


def version(request):
    """
    Returns version information about the application.
    """
    import subprocess
    import os
    
    version_info = {
        'version': os.getenv('APP_VERSION', 'unknown'),
        'build_date': os.getenv('BUILD_DATE', 'unknown'),
        'commit': os.getenv('GIT_COMMIT', 'unknown')[:7] if os.getenv('GIT_COMMIT') else 'unknown',
        'python_version': subprocess.run(['python', '--version'], capture_output=True, text=True).stdout.strip(),
    }
    
    return JsonResponse(version_info)
